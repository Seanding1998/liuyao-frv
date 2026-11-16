# 起卦熵源设计说明

> 适用版本：v2.0.9+
> 相关文件：`scripts/entropy.py`（实现）、`scripts/paipan.py`（调用方）
> 本文回答三个问题：**这一卦的随机数从哪来？为什么这样取？出了问题怎么看？**

---

## 一、为什么改

v2.0.8 及之前，`paipan.py` 的摇卦随机源只有三行：

```python
def make_time_rng():
    seed_int = time.time_ns() ^ int.from_bytes(os.urandom(8), "big")
    return random.Random(seed_int)
```

这段代码**在密码学上并不弱**——异或一个真随机的 64 位数，结果仍然是均匀随机的。但它有三处说不通：

| # | 问题 | 说明 |
|---|---|---|
| 1 | **天时不提供熵** | 异或只是把明文藏进一次性密码本。`time.time_ns()` 的全部信息被 `urandom` 完全掩盖，对种子的熵贡献是 **0 bit**。而注释写的是「以纳秒时钟混合操作系统物理熵」，这句话在数学上不成立 |
| 2 | **终端原语选错** | `random.Random` 是 MT19937，状态可由 624 个连续输出还原。单卦只取 18 个数，实战无法利用，但它不是为「不可预测」设计的 |
| 3 | **来源不可见** | JSON 里只有一个 `seed: null`。事后无法回答「这一卦的随机数到底从哪来」 |

第 3 条是关键：占卜这件事本身要求**可追溯**。一次起卦若无法说明它的随机性来源，它在方法上就是不完整的。

---

## 二、分层结构

```
┌─ L1 硬件熵 ────────────────────────────────────────────────┐
│  RDSEED  ← 片上热噪声（x86_64 的 Windows / Linux）           │
│  RDRAND  ← 硬件 DRBG 输出（同一段机器码，换一个 ModRM 字节）  │
├─ L2 平台熵 ────────────────────────────────────────────────┤
│  macOS   SecRandomCopyBytes → getentropy → arc4random_buf   │
│  Linux   getrandom(2) → getentropy(3) → /dev/hwrng          │
│  Windows BCryptGenRandom（系统首选 RNG）                     │
├─ L3 系统熵 ────────────────────────────────────────────────┤
│  os.urandom —— 三平台通用兜底                                │
├─ L4 时序抖动 ──────────────────────────────────────────────┤
│  perf_counter_ns 差分 + 调度边界（实测 ≈0.96 bit/byte，补充）│
├─ L5 环境噪声 ──────────────────────────────────────────────┤
│  pid / tid / 单调时钟 / 递归限制（只搅拌，不当熵）            │
└───────────────────────┬────────────────────────────────────┘
                        ↓ 原始字节
┌─ L6 健康检测（SP 800-90B）──────────────────────────────────┐
│  RCT 重复计数检验 + APT 自适应比例检验                       │
│  失败 → 抛异常，拒绝出数（绝不降级输出）                      │
└───────────────────────┬────────────────────────────────────┘
                        ↓
┌─ L7 条件化 ────────────────────────────────────────────────┐
│  HKDF-SHA256-Extract(salt = 域标签 ‖ 天时, IKM = 全部源)     │
│  → 256-bit 种子。天时作 salt，不作熵。                       │
└───────────────────────┬────────────────────────────────────┘
                        ↓
┌─ L8 扩展 ──────────────────────────────────────────────────┐
│  HMAC-SHA256 计数器模式 + 拒绝采样 → 区间严格均匀的整数       │
└────────────────────────────────────────────────────────────┘
```

### 为什么保留「天时」

起卦观是**以天时定卦**——同一件事此刻问与明日问，应当是不同的卦。要让这一点成立，有两种做法：

- ✗ 把时钟**当成熵**（旧做法）：既不成立，又制造了「看起来很强」的错觉；
- ✓ 把时钟**当成绑定坐标**（现做法）：作为 HKDF 的 salt，让这一次派生唯一地绑定到此刻，同时诚实地声明它不提供熵。

第二天的卦必然不同，因为来源本身就是新的物理熵——不需要时钟来"凑"这一点。

---

## 三、三平台实现矩阵

| 层 | Windows | macOS | Linux |
|---|---|---|---|
| L1 RDSEED/RDRAND | ✅ x86_64，机器码执行 | ❌ **主动关闭** | ✅ x86_64，机器码执行 |
| L2 平台熵 | `BCryptGenRandom` | `SecRandomCopyBytes` → `getentropy` → `arc4random_buf` | `getrandom(2)` → `getentropy(3)` → `/dev/hwrng` |
| L3 系统熵 | `os.urandom` | `os.urandom` | `os.urandom` |
| L4/L5 | ✅ | ✅ | ✅ |
| arm64 | 自动跳过 L1（Win on ARM） | 自动跳过 L1（Apple Silicon） | 自动跳过 L1（aarch64） |

降级是**分层**的：任何一层不可用都不影响其他层，最终一定落到 L3 `os.urandom`（三平台都有的系统级 CSPRNG）。

### macOS 为什么主动关掉机器码

```python
_ALLOW_ASM = _IS_X86_64 and not _IS_MAC
```

三个理由：

1. **Apple Silicon 没有 RDRAND/RDSEED**——那是 x86 指令，arm64 上根本不存在。
2. **arm64 macOS 的 W^X 强制**：匿名可执行映射会被拒绝，`mprotect(PROT_EXEC)` 直接失败。
3. **Rosetta 的陷阱**：Intel 程序跑在 Apple Silicon 上时，`platform.machine()` 返回 `x86_64`，CPUID 可能被透传成「支持 RDSEED」，但真执行就 SIGILL。与其赌，不如不用。

macOS 走 `SecRandomCopyBytes` 完全够用——它背后是内核 CSPRNG，早已被硬件 TRNG（Apple 的安全隔区）播种。

---

## 四、实现细节

### 4.1 没有 C 编译器，怎么跑 RDSEED

把 18 字节机器码写进一块可执行内存页，再用 `ctypes` 调用。两种调用约定只差一个字节：

```asm
; Windows x64（第一个参数在 RCX）
31 C0              xor  eax, eax
48 0F C7 F8        rdseed rax
0F 92 C2           setc dl          ; CF=1 表示成功
73 03              jnc  +3
48 89 01           mov  [rcx], rax
0F B6 C2           movzx eax, dl
C3                 ret

; System V（Linux / macOS x86_64，第一个参数在 RDI）
31 C0              xor  eax, eax
48 0F C7 F8        rdseed rax
0F 92 C2           setc dl
73 03              jnc  +3
48 89 07           mov  [rdi], rax   ; ← 只有这一行不同
0F B6 C2           movzx eax, dl
C3                 ret
```

`RDRAND` 与 `RDSEED` 的差别只在 ModRM 的 `/6` 与 `/7`：`F0` 换 `F8`。

**CPUID 探针**同样用机器码实现（`CPUID.07H:EBX[18]` = RDSEED）。这里有个 ABI 坑：`RBX` 在两种调用约定里都是**非易失寄存器**，`CPUID` 会踩它，所以必须 `push rbx` / `pop rbx`——漏了就会悄悄破坏调用者的寄存器。

内存页分配：

- Windows：`VirtualAlloc(MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE)`
- Unix：`mmap(PROT_READ|PROT_WRITE)` 写入 → `mprotect(PROT_READ|PROT_EXEC)` 改成 RX（W^X 友好，不长期保持 RWX）

任何一步失败（SELinux 的 `execmem` 拒绝、hvci、沙箱）都会**优雅降级**，不会崩。

### 4.2 健康检测参数

按 SP 800-90B 的两个最常用的连续检验实现，假设最小熵 `H = 4 bit/byte`（保守估计，实测 RDSEED 约 7.9）：

| 检验 | 公式 | H=4 时的判据 |
|---|---|---|
| RCT（重复计数） | `C = 1 + ⌈20/H⌉` | 连续 6 次相同字节 → 报警 |
| APT（自适应比例，窗宽 1024） | `C = ⌈W·2⁻ᴴ + 2.576·√(W·2⁻ᴴ(1−2⁻ᴴ))⌉` | 窗口内同一字节出现 ≥84 次 → 报警 |

报警即 `raise`，不返回任何字节。**宁可起不了卦，也不出一个来历可疑的卦。**

### 4.3 条件化与扩展

- **条件化**：`HKDF-SHA256-Extract`，salt = `b"liuyao/entropy/v1" ‖ env_bytes()`，IKM = 各层原始字节拼接。输出 32 字节种子。
- **扩展**：`HMAC-SHA256(key=seed, msg=domain ‖ counter)` 计数器模式，`counter` 单调递增。因此**不可回退**——即使进程状态泄漏，也无法重放此前的输出。
- **取整数**：拒绝采样。`randbelow(n)` 取 `k = n.bit_length()` 位，`v < n` 才接受，保证严格均匀（`random.Random.randint` 也是这个思路，但底层是 MT19937）。

### 4.4 立币三态的口径不变

每枚硬币**一次抽取**同时决定「正 / 反 / 立」，抽 0..9999，落在最小 `slots` 格判立起，否则按 `v % 2` 定阴阳。`slots = round(edge_prob × 10000)`，默认 `1/6000 → 2 格`（实际约 1/5000，与文献区间同量级）。

**本次没有改动这个口径**——换的只是底层随机源，摇卦逻辑一个字没动。

---

## 五、实测数据

测试机：AMD Ryzen AI 9 H 365（Zen 5）/ Windows 11 / Python 3.13；另用 WSL2 Fedora（Python 3.14.8, x86_64）验证 Linux 路径。

### 熵源可用性

| 项 | Windows | Linux (WSL2) |
|---|---|---|
| CPUID 声明 RDSEED | 是 | 是 |
| RDSEED 执行试探 | 16/16 成功 | 16/16 成功 |
| 主源 | `rdseed` | `rdseed` |
| 全部启用层 | rdseed + win-bcrypt + os-urandom + jitter + env | rdseed + linux-getrandom + os-urandom + jitter + env |

### 各源最小熵（MVC 估计器，8 bit/byte 上界）

| 源 | 最小熵 | 说明 |
|---|---|---|
| RDSEED | **7.967 / 8** | 硬件真熵，唯一接近满值的物理源 |
| RDRAND | 7.574 / 8 | 硬件 DRBG 输出 |
| 系统 CSPRNG | 7.608 / 8 | 内核已混合硬件熵与中断时序 |
| **计时抖动** | **0.962 / 8** | 只有 12% 信息量，且强相关——**不能当主源** |

这张表就是「为什么抖动只能作补充」的依据。

### 均匀性

| 检验 | Windows | Linux |
|---|---|---|
| 0..9999 取 20 万次 卡方（df=9999） | χ²=10075.4，z=+0.54 | χ²=10019.8，z=+0.15 |
| 立币 2/10000 实测（60 万次） | 0.019333%（期望 0.020000%） | 0.020667% |
| 两次起卦种子是否相同 | 否 | 否 |

### 跨平台一致性

`--seed 42` 在 Windows 与 Linux 上摇出**完全相同**的卦：`ygua = 112413`。

同一 `--seed` 在 v2.0.8 与 v2.0.9 上、在两个平台、在 main 与 frv 两条分支上，结果逐位一致——历史卦例可以无差别重放。

---

## 六、和 `--seed` 的关系

| 模式 | 随机源 | 用途 |
|---|---|---|
| **默认**（不指定 `--seed`） | 本文件描述的分层熵管线 | 正常起卦 |
| `--seed N` | `random.Random(N)`，**原样保留** | 「重看同一卦」，要求逐位复现 |

`--seed` 分支**故意不改**。复现性优先于熵质量——它存在的意义就是可重放，换成就不可复现了。

> ⚠️ 常规起卦不要用 `--seed`。用固定种子等于绕过天时，起卦这件事本身就失去意义。

---

## 七、使用与排障

### 自检

```bash
python scripts/entropy.py --selftest     # 探针 + 卡方 + 立币概率 + 种子独立性 + seed 一致性
python scripts/entropy.py --describe     # 只看当前平台能用哪些层
```

典型输出（Windows）：

```
平台        : win32 (amd64)
Python      : 3.13.15
RDSEED 探针 : RDSEED 可用（16 次试探成功 16 次）
os.urandom  : 可用
macOS SecRandom: 不适用/失败
Linux getrandom: 不适用/失败
Windows Bcrypt: 可用
```

### 每次起卦的溯源

排盘时会向 stderr 打一行，并写入 JSON 的 `entropy` 字段：

```
[熵源] rdseed ← rdseed+win-bcrypt+os-urandom+jitter+env  seed:9cbfb9a2bf274be5
```

```json
"entropy": {
  "sources": ["rdseed", "win-bcrypt", "os-urandom", "jitter", "env"],
  "primary": "rdseed",
  "platform": "win32-amd64",
  "health": "pass",
  "seed_sha256": "9cbfb9a2bf274be5",
  "timestamp_ns": 1763316587304821900,
  "hw_note": "RDSEED 可用（16 次试探成功 16 次）"
}
```

`seed_sha256` 是种子指纹（前 16 位）。同一个种子指纹意味着同一次摇卦——可以用来核对两个副本是否同源。

### 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| `primary` 是 `os-urandom` 而非 `rdseed` | CPU 未声明 RDSEED（老 CPU / ARM / macOS） | 正常降级，安全性由系统 CSPRNG 保证 |
| `hw_note` 提示「指令被拒绝执行」 | 虚拟机或沙箱拦截了 RDSEED | 正常，已降级 |
| `hw_note` 提示「代码页不可用」 | SELinux `execmem` / hvci / W^X 拦截 | 正常，已降级 |
| 抛出「熵源健康检测失败」 | 熵源持续输出重复字节（真故障） | 这就是它该干的事——不要绕过，报障 |
| 想强制关掉机器码路径 | 排障、审计、受限环境 | `set LIUYAO_ENTROPY_DISABLE_HW=1` |
| `entropy.py` 不存在 | 旧副本 / 裁剪安装 | 自动回退旧版时间随机源，stderr 会警告 |

---

## 八、威胁模型：它防什么、不防什么

**防：**

- 种子空间可穷举。旧实现的种子空间是 `2⁶⁴` 且实际受时钟影响；新实现是 256-bit，且来自物理源。
- 输出序列被反推。MT19937 的 624 输出攻击路径在新实现里不存在。
- 单点熵源故障（退化、卡死、返回全 1）。五源混合 + 健康检测兜住。
- 事后无法审计。`entropy` 字段把来源钉在每一卦上。

**不防：**

- **卦本身的解释**。熵源再强，解卦仍是一套规则体系，不是预测学。
- **有人偷看你的屏幕**。随机性与保密性无关。
- **物理层被完全控制**。如果攻击者掌握整台机器，他尽可以伪造一切——包括卦。
- **无限算力的对手**。256-bit 种子在密码学假设下安全；这是计算安全，不是信息论安全。

**一句实话**：这次升级换来的是**可核查性 + 正确的原语 + 诚实的语义**，不是「更准的卦」。之前的 `os.urandom(8)` 本来就穷举不了；变的是我们能不能说清楚它从哪来、以及代码注释是否在骗人。

---

## 九、变更记录

| 版本 | 变更 |
|---|---|
| v2.0.9 | 新增 `scripts/entropy.py`，八层熵管线；`paipan.py` 改调 `entropy.divination_rng()`；JSON 新增 `entropy` 字段；`--seed` 逐位保持 |
| v2.0.8 及之前 | `random.Random(time.time_ns() ^ os.urandom(8))` |
