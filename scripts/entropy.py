#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""entropy.py — 起卦熵源（Windows / macOS / Linux 三平台）

设计目标
--------
让"摇卦"这一步的随机性来自**可核查的物理熵**，而不是一个 64 位整数异或纳秒时钟。

旧实现是：

    seed = time.time_ns() ^ int.from_bytes(os.urandom(8), "big")
    random.Random(seed)

它在密码学上其实不算弱（异或一个真随机数，结果仍是真随机），但有三处不舒服：

1. **天时是假的说法**。seed 的熵全部来自 urandom 的 64 bit，纳秒时钟贡献 0 bit——
   它相当于一次性密码本里的明文，异或之后完全被掩盖。所谓"锁在起卦那一刻"
   在数学上不成立。
2. **终端算法是 MT19937**。`random.Random` 是梅森旋转，状态可由 624 个输出还原；
   单卦只取 18 个数，实战无法利用，但它不是为"不可预测"设计的。
3. **来源不可见**。事后无法回答"这一卦的随机数是哪来的"。

分层结构
--------
    L1 硬件熵   RDSEED / RDRAND（x86_64，Windows / Linux / macOS-Intel）
    L2 平台熵   macOS: SecRandomCopyBytes / getentropy / arc4random_buf
                Linux: getrandom(2)、/dev/hwrng
                Windows: BCryptGenRandom
    L3 系统熵   os.urandom —— 三平台通用兜底
    L4 时序抖动 perf_counter_ns 差分 + 调度边界（永远可用，熵率低）
    L5 环境噪声 pid / tid / 单调时钟 / 进程状态（只作搅拌，不当熵）
        ↓
    L6 健康检测 RCT + APT（SP 800-90B），失败即拒绝出数
        ↓
    L7 条件化   HKDF-SHA256-Extract（天时作为 salt，不当熵）
        ↓
    L8 扩展     HMAC-SHA256 计数器模式 + 拒绝采样，输出均匀整数

用法
----
    import entropy
    rng = entropy.divination_rng()     # 每次起卦新建，禁止复用
    rng.randint(0, 9999)               # 与 random.Random 接口兼容
    rng.provenance                     # 可写入 JSON 的来源记录

    entropy.seeded_rng(42)             # --seed 复现路径，逐位等同 random.Random(42)

自带自检：

    python entropy.py --selftest
"""

from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import hmac
import math
import os
import platform
import sys
import threading
import time

__all__ = [
    "divination_rng",
    "seeded_rng",
    "DivinationRng",
    "harvest",
    "describe",
    "DOMAIN",
]

DOMAIN = b"liuyao/entropy/v1"
_DRBG_DOMAIN = b"liuyao/drbg/v1"

_IS_WIN = sys.platform == "win32"
_IS_MAC = sys.platform == "darwin"
_IS_LINUX = sys.platform.startswith("linux")
_MACHINE = (platform.machine() or "").lower()
_IS_X86_64 = _MACHINE in ("amd64", "x86_64", "x64")

#  是否允许执行自备机器码（RDSEED / CPUID）：
#    macOS 一律关闭 —— Apple Silicon 没有 RDRAND/RDSEED，且 arm64 上匿名可执行映射
#    被 W^X 挡住；Intel Mac 由 Rosetta 运行时 CPUID 可能被透传，执行真指令有 SIGILL 风险。
#    macOS 走 SecRandomCopyBytes（内核 CSPRNG，已由硬件 TRNG 播种）即可。
#   x86_64 的 Windows / Linux 正常开启；可用环境变量强制关闭以便排障。
_ALLOW_ASM = _IS_X86_64 and not _IS_MAC
if os.environ.get("LIUYAO_ENTROPY_DISABLE_HW", "").strip() not in ("", "0", "false", "False"):
    _ALLOW_ASM = False


# ═══════════════════════════════════════════════════════════════
#  可执行代码块：在纯 Python 里跑 RDSEED / CPUID
# ───────────────────────────────────────────────────────────────
#  目标机器上没有 C 编译器也能用——把 18 字节机器码写进一块内存页执行即可。
#  Windows x64 首个参数在 RCX；System V（Linux / macOS）在 RDI。
#  RBX 在两种 ABI 里都是非易失寄存器，CPUID 会踩它，所以必须 push/pop。
# ═══════════════════════════════════════════════════════════════

_MEM_COMMIT = 0x1000
_MEM_RESERVE = 0x2000
_PAGE_READWRITE = 0x04
_PAGE_EXECUTE_READ = 0x20
_PAGE_EXECUTE_READWRITE = 0x40

_PROT_READ = 0x1
_PROT_WRITE = 0x2
_PROT_EXEC = 0x4
_MAP_PRIVATE = 0x02
_MAP_ANONYMOUS_LINUX = 0x20
_MAP_ANONYMOUS_DARWIN = 0x1000


def _asm_rdseed() -> bytes:
    """bool fn(uint64_t *out)  —— 成功写入并返回 1"""
    if _IS_WIN:
        return bytes([
            0x31, 0xC0,                    # xor  eax, eax
            0x48, 0x0F, 0xC7, 0xF8,        # rdseed rax
            0x0F, 0x92, 0xC2,              # setc dl
            0x73, 0x03,                    # jnc  +3
            0x48, 0x89, 0x01,              # mov  [rcx], rax
            0x0F, 0xB6, 0xC2,              # movzx eax, dl
            0xC3,                          # ret
        ])
    return bytes([
        0x31, 0xC0,                        # xor  eax, eax
        0x48, 0x0F, 0xC7, 0xF8,            # rdseed rax
        0x0F, 0x92, 0xC2,                  # setc dl
        0x73, 0x03,                        # jnc  +3
        0x48, 0x89, 0x07,                  # mov  [rdi], rax
        0x0F, 0xB6, 0xC2,                  # movzx eax, dl
        0xC3,                              # ret
    ])


def _asm_rdrand() -> bytes:
    """RDRAND 只是把 ModRM 的 /7 换成 /6（F8 → F0）。"""
    code = bytearray(_asm_rdseed())
    # rdseed rax = 48 0F C7 F8；rdrand rax = 48 0F C7 F0
    for i in range(len(code) - 3):
        if code[i] == 0x48 and code[i + 1] == 0x0F and code[i + 2] == 0xC7:
            code[i + 3] = 0xF0
            break
    return bytes(code)


def _asm_cpuid_leaf7() -> bytes:
    """void fn(uint32_t *out) —— out[0] = CPUID.07H:EBX"""
    if _IS_WIN:
        return bytes([
            0x53,                          # push rbx
            0x49, 0x89, 0xC8,              # mov  r8, rcx
            0xB8, 0x07, 0x00, 0x00, 0x00,  # mov  eax, 7
            0x31, 0xC9,                    # xor  ecx, ecx
            0x0F, 0xA2,                    # cpuid
            0x41, 0x89, 0x58, 0x00,        # mov  [r8], ebx
            0x5B,                          # pop  rbx
            0xC3,                          # ret
        ])
    return bytes([
        0x53,                              # push rbx
        0xB8, 0x07, 0x00, 0x00, 0x00,      # mov  eax, 7
        0x31, 0xC9,                        # xor  ecx, ecx
        0x0F, 0xA2,                        # cpuid
        0x89, 0x1F,                        # mov  [rdi], ebx
        0x5B,                              # pop  rbx
        0xC3,                              # ret
    ])


class _ExecPage(object):
    """把一段机器码放进可执行内存，返回可调用的 ctypes 函数。"""

    def __init__(self, code, prototype):
        self.addr = 0
        self.size = max(4096, len(code) + 16)
        self._alloc(code)
        self.fn = prototype(self.addr)

    # -- 分配 ---------------------------------------------------
    def _alloc(self, code):
        if _IS_WIN:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.VirtualAlloc.restype = ctypes.c_void_p
            k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32, ctypes.c_uint32]
            addr = k32.VirtualAlloc(None, self.size,
                                    _MEM_COMMIT | _MEM_RESERVE,
                                    _PAGE_EXECUTE_READWRITE)
            if not addr:
                raise OSError("VirtualAlloc 失败")
            self.addr = addr
            ctypes.memmove(ctypes.c_void_p(self.addr), code, len(code))
            return

        libc = ctypes.CDLL(None, use_errno=True)
        libc.mmap.restype = ctypes.c_void_p
        libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.c_long]
        libc.mprotect.restype = ctypes.c_int
        libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]

        anon = _MAP_ANONYMOUS_DARWIN if _IS_MAC else _MAP_ANONYMOUS_LINUX
        addr = libc.mmap(None, self.size, _PROT_READ | _PROT_WRITE,
                         _MAP_PRIVATE | anon, -1, 0)
        if addr in (None, 0, ctypes.c_void_p(-1).value):
            raise OSError("mmap 失败")
        self.addr = addr
        ctypes.memmove(ctypes.c_void_p(self.addr), code, len(code))
        # W^X：写完再改成可读可执行（比一直 RWX 干净）
        if libc.mprotect(ctypes.c_void_p(self.addr), self.size,
                         _PROT_READ | _PROT_EXEC) != 0:
            raise OSError("mprotect(PROT_EXEC) 被拒绝 errno=%d" % ctypes.get_errno())

    def __call__(self):
        return self.fn


def _probe_rdseed_support():
    """执行 CPUID.07H:EBX[18] 判断硬件是否声明 RDSEED。"""
    if not _ALLOW_ASM:
        return False, "本平台不启用自备机器码（%s-%s）" % (sys.platform, _MACHINE or "?")
    proto = (ctypes.WINFUNCTYPE(None, ctypes.POINTER(ctypes.c_uint32)) if _IS_WIN
             else ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_uint32)))
    try:
        page = _ExecPage(_asm_cpuid_leaf7(), proto)
    except Exception as exc:                       # noqa: BLE001
        return False, "CPUID 探针不可用：%s" % exc
    out = (ctypes.c_uint32 * 1)()
    try:
        page.fn(out)
    except Exception as exc:                       # noqa: BLE001
        return False, "CPUID 执行失败：%s" % exc
    return bool(out[0] & (1 << 18)), "CPUID.07H:EBX[18]=%d" % ((out[0] >> 18) & 1)


# ═══════════════════════════════════════════════════════════════
#  L1 硬件熵
# ═══════════════════════════════════════════════════════════════

_HW_CACHE = {}
_HW_LOCK = threading.Lock()


def _hw_source():
    """惰性构建 RDSEED/RDRAND 调用器；不可用则返回 None。"""
    with _HW_LOCK:
        if "fn" in _HW_CACHE:
            return _HW_CACHE["fn"]
        fn = None
        note = ""
        ok, why = _probe_rdseed_support()
        if ok:
            proto = (ctypes.WINFUNCTYPE(ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint64)) if _IS_WIN
                     else ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint64)))
            try:
                page = _ExecPage(_asm_rdseed(), proto)
                holder = (ctypes.c_uint64 * 1)()
                hits = sum(1 for _ in range(16) if page.fn(holder) != 0)
                if hits:
                    fn = ("rdseed", page, holder)
                    note = "RDSEED 可用（16 次试探成功 %d 次）" % hits
                else:
                    note = "RDSEED 指令被拒绝执行（可能被 hypervisor 拦截）"
            except Exception as exc:               # noqa: BLE001
                note = "RDSEED 代码页不可用：%s" % exc
        else:
            note = "未声明 RDSEED：%s" % why
        _HW_CACHE["fn"] = fn
        _HW_CACHE["note"] = note
        return fn


def hw_bytes(n):
    """从 RDSEED 取 n 字节；不可用或失败返回 None。"""
    src = _hw_source()
    if src is None:
        return None
    _, page, holder = src
    out = bytearray()
    while len(out) < n:
        got = 0
        for _ in range(16):                        # RDSEED 偶发 CF=0，重试
            if page.fn(holder):
                got = 1
                break
        if not got:
            return None
        out += int(holder[0]).to_bytes(8, "little")
    return bytes(out[:n])


# ═══════════════════════════════════════════════════════════════
#  L2 平台熵
# ═══════════════════════════════════════════════════════════════

def macos_bytes(n):
    """SecRandomCopyBytes；失败再退 getentropy / arc4random_buf。"""
    if not _IS_MAC:
        return None
    buf = (ctypes.c_ubyte * n)()
    try:
        sec = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        sec.SecRandomCopyBytes.restype = ctypes.c_int32
        sec.SecRandomCopyBytes.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
        if sec.SecRandomCopyBytes(None, n, buf) == 0:
            return bytes(bytearray(buf))
    except Exception:                              # noqa: BLE001
        pass
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.getentropy.restype = ctypes.c_int
        libc.getentropy.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        if n <= 256 and libc.getentropy(buf, n) == 0:
            return bytes(bytearray(buf))
    except Exception:                              # noqa: BLE001
        pass
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.arc4random_buf.restype = None
        libc.arc4random_buf.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        libc.arc4random_buf(buf, n)
        return bytes(bytearray(buf))
    except Exception:                              # noqa: BLE001
        return None


def linux_bytes(n):
    """getrandom(2) → getentropy(3) → /dev/hwrng（树莓派等板载 TRNG）。"""
    if not _IS_LINUX:
        return None
    buf = (ctypes.c_ubyte * n)()
    for libname in (None, "libc.so.6"):
        try:
            libc = ctypes.CDLL(libname, use_errno=True)
            libc.getrandom.restype = ctypes.c_ssize_t
            libc.getrandom.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint]
            if libc.getrandom(buf, n, 0) == n:
                return bytes(bytearray(buf))
            break
        except Exception:                          # noqa: BLE001
            continue
    if n <= 256:
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            libc.getentropy.restype = ctypes.c_int
            libc.getentropy.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            if libc.getentropy(buf, n) == 0:
                return bytes(bytearray(buf))
        except Exception:                          # noqa: BLE001
            pass
    try:
        with open("/dev/hwrng", "rb") as fh:
            data = fh.read(n)
        if len(data) == n:
            return data
    except Exception:                              # noqa: BLE001
        pass
    return None


def windows_bytes(n):
    """BCryptGenRandom 系统首选 RNG（os.urandom 的底层，此处显式命名）。"""
    if not _IS_WIN:
        return None
    try:
        bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
        bcrypt.BCryptGenRandom.restype = ctypes.c_int32
        bcrypt.BCryptGenRandom.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_uint32, ctypes.c_uint32]
        buf = (ctypes.c_ubyte * n)()
        if bcrypt.BCryptGenRandom(None, buf, n, 0x00000002) == 0:
            return bytes(bytearray(buf))
    except Exception:                              # noqa: BLE001
        pass
    return None


# ═══════════════════════════════════════════════════════════════
#  L4 / L5 抖动与环境
# ═══════════════════════════════════════════════════════════════

def jitter_bytes(n):
    """计数器差分。熵率很低（实测约 0.96 bit/byte），只作补充，绝不当主源。"""
    out = bytearray()
    prev = time.perf_counter_ns()
    while len(out) < n:
        acc = 0
        for i in range(8):
            if (i & 3) == 0:
                time.sleep(0)                      # 让出时间片，采集调度抖动
            now = time.perf_counter_ns()
            delta = now - prev
            prev = now
            acc = ((acc << 7) ^ delta ^ (delta >> 17)) & 0xFFFFFFFFFFFFFFFF
        out += acc.to_bytes(8, "little")
    return bytes(out[:n])


def env_bytes():
    """进程/线程/时钟状态。信息量小，仅用于把 seed 绑定到这一次起卦。"""
    parts = [
        str(os.getpid()).encode(),
        str(threading.get_ident()).encode(),
        str(time.time_ns()).encode(),
        str(time.perf_counter_ns()).encode(),
        str(time.monotonic_ns()).encode(),
        str(sys.getrecursionlimit()).encode(),
    ]
    return b"|".join(parts)


# ═══════════════════════════════════════════════════════════════
#  L6 健康检测：SP 800-90B 的 RCT + APT
# ═══════════════════════════════════════════════════════════════

class HealthMonitor(object):
    def __init__(self, h_bits=4.0, window=1024):
        h_bits = max(h_bits, 0.1)
        self.rct_cutoff = int(math.ceil(20.0 / h_bits)) + 1
        self.window = window
        p = 2.0 ** (-h_bits)
        self.apt_cutoff = int(math.ceil(window * p + 2.576 * math.sqrt(window * p * (1 - p))))
        self._last = None
        self._repeat = 0
        self.alarm = None

    def feed(self, data):
        counts = {}
        order = []
        for b in data:
            if b == self._last:
                self._repeat += 1
            else:
                self._repeat = 1
                self._last = b
            if self._repeat >= self.rct_cutoff:
                self.alarm = "RCT：连续 %d 次出现同一字节 0x%02X" % (self._repeat, b)
                return False
            counts[b] = counts.get(b, 0) + 1
            order.append(b)
            if len(order) > self.window:
                old = order.pop(0)
                counts[old] -= 1
                if counts[old] <= 0:
                    counts.pop(old, None)
            if counts[b] >= self.apt_cutoff:
                self.alarm = "APT：%d 字节窗口内 0x%02X 出现 %d 次" % (self.window, b, counts[b])
                return False
        return True


# ═══════════════════════════════════════════════════════════════
#  L7 条件化：HKDF-SHA256
# ═══════════════════════════════════════════════════════════════

def hkdf_sha256(ikm, salt, info, length=32):
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm, block, counter = b"", b"", 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


# ═══════════════════════════════════════════════════════════════
#  L8 扩展：HMAC-SHA256 计数器模式 + 拒绝采样
# ═══════════════════════════════════════════════════════════════

class DivinationRng(object):
    """起卦用随机源，接口与 random.Random 的常用子集兼容。

    与 MT19937 的区别：输出由 256-bit 种子的 HMAC-SHA256 计数器模式产生，
    不存在"观测到足够多输出就能反推内部状态"的路径；计数器单调递增，
    因此不可回退（compromise 后无法重放之前的卦）。单卦只取 18 个数，够用。
    """

    __slots__ = ("_key", "_ctr", "_buf", "provenance")

    def __init__(self, seed, provenance=None):
        if len(seed) < 32:
            raise ValueError("种子至少 32 字节")
        self._key = bytes(seed[:32])
        self._ctr = 0
        self._buf = b""
        self.provenance = provenance or {}

    # -- 字节流 -------------------------------------------------
    def _block(self):
        self._ctr += 1
        msg = _DRBG_DOMAIN + self._ctr.to_bytes(8, "big")
        return hmac.new(self._key, msg, hashlib.sha256).digest()

    def read(self, n):
        while len(self._buf) < n:
            self._buf += self._block()
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    # -- 均匀整数 -----------------------------------------------
    def randbelow(self, n):
        if n <= 0:
            raise ValueError("n 必须为正")
        if n == 1:
            return 0
        k = n.bit_length()
        while True:
            v = int.from_bytes(self.read(8), "big") >> (64 - k)
            if v < n:
                return v

    def randint(self, a, b):
        if a > b:
            raise ValueError("空区间：%d > %d" % (a, b))
        return a + self.randbelow(b - a + 1)

    def getrandbits(self, k):
        if k <= 0:
            return 0
        out = 0
        got = 0
        while got < k:
            take = min(64, k - got)
            out = (out << take) | (int.from_bytes(self.read(8), "big") >> (64 - take))
            got += take
        return out

    def random(self):
        return self.randbelow(1 << 53) / float(1 << 53)

    def choice(self, seq):
        return seq[self.randbelow(len(seq))]


# ═══════════════════════════════════════════════════════════════
#  采集 + 条件化
# ═══════════════════════════════════════════════════════════════

def harvest(nbytes=64):
    """采集所有可用源，做健康检测与条件化，返回 (32 字节种子, 来源记录)。"""
    used = []
    parts = []

    hw = hw_bytes(nbytes)
    if hw:
        used.append("rdseed")
        parts.append(hw)

    for name, getter in (
        ("macos-secrandom", macos_bytes),
        ("linux-getrandom", linux_bytes),
        ("win-bcrypt", windows_bytes),
    ):
        blob = getter(nbytes)
        if blob:
            used.append(name)
            parts.append(blob)

    try:
        osb = os.urandom(nbytes)
        used.append("os-urandom")
        parts.append(osb)
    except Exception:                              # noqa: BLE001
        osb = None

    parts.append(jitter_bytes(nbytes))
    used.append("jitter")
    parts.append(env_bytes())
    used.append("env")

    raw = b"".join(parts)

    # 健康检测：只看主源（RDSEED 或系统熵），抖动的低熵分布会误报
    monitor = HealthMonitor(h_bits=4.0)
    primary = hw if hw else (osb if osb else jitter_bytes(nbytes))
    healthy = monitor.feed(primary)
    if not healthy:
        raise RuntimeError("熵源健康检测失败：" + (monitor.alarm or "未知"))

    # 天时作 salt（不当熵）：让这一卦在派生层面与此刻绑定
    salt = DOMAIN + b"|" + env_bytes()
    seed = hkdf_sha256(raw, salt, DOMAIN + b"|seed", 32)

    provenance = {
        "sources": used,
        "primary": "rdseed" if hw else ("os-urandom" if osb else "jitter"),
        "platform": "%s-%s" % (sys.platform, _MACHINE or "?"),
        "health": "pass",
        "seed_sha256": hashlib.sha256(seed).hexdigest()[:16],
        "timestamp_ns": time.time_ns(),
        "hw_note": _HW_CACHE.get("note", ""),
    }
    return seed, provenance


def divination_rng():
    """本卦专用随机源。每次起卦都新建，禁止缓存复用。"""
    seed, prov = harvest()
    return DivinationRng(seed, prov)


def seeded_rng(seed_int):
    """--seed 复现路径：与 random.Random(seed) 完全等价，保证历史卦例可重放。"""
    import random
    return random.Random(seed_int)


# ═══════════════════════════════════════════════════════════════
#  诊断
# ═══════════════════════════════════════════════════════════════

def describe():
    _hw_source()                                   # 触发探针，让 note 有值
    lines = [
        "平台        : %s (%s)" % (sys.platform, _MACHINE or "?"),
        "Python      : %s" % sys.version.split()[0],
        "RDSEED 探针 : %s" % _HW_CACHE.get("note", "未探测"),
        "os.urandom  : %s" % ("可用" if os.urandom(8) else "不可用"),
    ]
    for name, getter in (("macOS SecRandom", macos_bytes),
                         ("Linux getrandom", linux_bytes),
                         ("Windows Bcrypt", windows_bytes)):
        try:
            lines.append("%-14s: %s" % (name, "可用" if getter(16) else "不适用/失败"))
        except Exception as exc:                   # noqa: BLE001
            lines.append("%-14s: 失败 %s" % (name, exc))
    return "\n".join(lines)


def _selftest():
    import collections

    print("=" * 64)
    print(describe())
    print("=" * 64)

    hw = hw_bytes(64)
    hwnote = _HW_CACHE.get("note", "")
    print("RDSEED 取数 : %s  %s" % ("成功" if hw else "回退", hwnote))

    seed, prov = harvest()
    print("来源        : %s" % ", ".join(prov["sources"]))
    print("主源        : %s" % prov["primary"])
    print("种子指纹    : %s" % prov["seed_sha256"])

    # 均匀性：0..9999 取 20 万次，卡方检验 df=9999
    rng = DivinationRng(seed)
    N, M = 200000, 10000
    bucket = [0] * M
    for _ in range(N):
        bucket[rng.randint(0, M - 1)] += 1
    exp = N / M
    chi2 = sum((c - exp) ** 2 / exp for c in bucket)
    df = M - 1
    z = (chi2 - df) / math.sqrt(2 * df)
    print("卡方 0..9999: χ²=%.1f df=%d z=%+.2f  %s" % (chi2, df, z, "OK" if abs(z) < 4 else "偏差可疑"))

    # 立币概率：edge_prob=1/6000 → 10000 格取 2 格
    hits = sum(1 for _ in range(600000) if rng.randint(0, 9999) < 2)
    print("立币 2/10000: 实测 %.6f%%（期望 %.6f%%）" % (hits / 6000.0, 0.02))

    # 独立性：两次起卦的种子不应相同
    s1, _ = harvest()
    s2, _ = harvest()
    print("两次种子相同: %s" % (s1 == s2))

    # 与 random.Random 的可复现路径一致性
    a = [seeded_rng(42).randint(0, 9999) for _ in range(1)]
    b = [__import__("random").Random(42).randint(0, 9999) for _ in range(1)]
    print("--seed 42 首抽: %s == %s → %s" % (a[0], b[0], a[0] == b[0]))


if __name__ == "__main__":
    if "--selftest" in sys.argv or len(sys.argv) == 1:
        _selftest()
    elif "--describe" in sys.argv:
        print(describe())
