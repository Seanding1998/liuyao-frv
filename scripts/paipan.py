#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六爻自动排盘脚本 — 双轨干支计算

功能：
  - 三币摇卦法随机生成六爻（从初爻到上爻）
  - 双轨干支计算：sxtwl（优先，精确到节气）→ 纯 Python（回退，内嵌 2026-2086 年数据）
  - 定主卦/变卦/世应/六神/六亲/伏神
  - 输出结构化 JSON，匹配六爻解卦 Skill 的输入格式

用法：
  python paipan.py --subject "所问之事" [--intent "意图类别"] [--year YYYY --month MM --day DD --hour HH --minute MM] [--yao "111111"]

  --subject  所占之事（必填）
  --intent   意图类别：求财|官运|学业|感情|健康|孕产|出行|失物|词讼|天气|通用（默认通用）
  --yao      手动六爻编码（6位 1-4 字符串，自下而上），不提供则随机生成
  --year     公历年（默认当前）
  --month    公历月
  --day      公历日
  --hour     小时 0-23
  --minute   分钟

依赖：sxtwl（可选，`pip install sxtwl`；未安装时自动回退到纯 Python 计算）
"""

import sys
import json
import random
import argparse
from datetime import datetime, date

# ── 检测 sxtwl（可选依赖）────────────────────────────────────
_SXTWL_AVAILABLE = False
try:
    import sxtwl
    _SXTWL_AVAILABLE = True
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════
#  基础常量
# ═══════════════════════════════════════════════════════════════

TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

DIZHI_TO_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 六神：日干 → 起始索引
LIUSHEN_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3,
                 "庚": 4, "辛": 4, "壬": 5, "癸": 5}
LIUSHEN_NAMES = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]

# 旬空计算用
KONGWANG_ZU = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
DIZHI_INDEX = {dz: i + 1 for i, dz in enumerate(DIZHI)}   # 子=1 … 亥=12
TIANGAN_INDEX = {tg: i + 1 for i, tg in enumerate(TIANGAN)}  # 甲=1 … 癸=10

# 有效的 intent 类别
VALID_INTENTS = {"求财", "官运", "学业", "感情", "健康", "孕产", "出行", "失物", "词讼", "天气", "通用"}

# ── 宫→五行（用于变卦六亲按本卦宫重算）──────────────
_GONG_WUXING = {
    "乾宫": "金", "兑宫": "金",
    "离宫": "火",
    "震宫": "木", "巽宫": "木",
    "坎宫": "水",
    "艮宫": "土", "坤宫": "土",
}
_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_KE   = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# ── 地支关系常量（格局自动检测用）──────────────────────────
DIZHI_LIUHE_PAIRS = [
    ("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未"),
]
DIZHI_LIUCHONG_PAIRS = [
    ("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥"),
]
DIZHI_SANHUI_GROUPS = [
    ("亥", "子", "丑"),   # 北方水局
    ("寅", "卯", "辰"),   # 东方木局
    ("巳", "午", "未"),   # 南方火局
    ("申", "酉", "戌"),   # 西方金局
]
# 三合局（长生-帝旺-墓库 + 五行属性）
DIZHI_SANHE_GROUPS = [
    ("申", "子", "辰", "水"),   # 水局
    ("亥", "卯", "未", "木"),   # 木局
    ("寅", "午", "戌", "火"),   # 火局
    ("巳", "酉", "丑", "金"),   # 金局
]


# ── 八宫规则推断游魂/归魂（方案 C：不依赖 GUA64 第 10 列标签）──
# 八宫变化：纯(6世)→一世→二世→三世→四世(4爻变)→五世(5爻变)→游魂(4爻回退+下卦变反宫)→归魂(下卦回本宫)
# 关键区分：游魂=世4应1+4爻=纯卦4爻(回退了)；四世=世4应1+4爻≠纯卦4爻
#          归魂=世3应6+5爻≠纯卦5爻(五世保留了变化)；三世=世3应6+5爻=纯卦5爻

def _build_pure_guastr():
    """从 GUA64 表读取八纯卦 guastr（世爻=6）→ {宫名: guastr}"""
    return {v[10]: k for k, v in GUA64.items() if v[6] == 6}


_PURE_GUASTR = None  # lazy init after GUA64 is defined


def _infer_you_gui_hun(gua_name, gong_name, shi, ying, guastr):
    """用八宫变化规则推断游魂/归魂（不依赖 GUA64 第 10 列字符串标签）。

    规则：
    - 游魂 = 世4应1 + 4爻=纯卦4爻（回退到纯卦状态）
    - 归魂 = 世3应6 + 5爻≠纯卦5爻（五世的变化被保留）
    返回 (is_you_hun: bool, is_gui_hun: bool)。
    """
    global _PURE_GUASTR
    if _PURE_GUASTR is None:
        _PURE_GUASTR = _build_pure_guastr()
    pure = _PURE_GUASTR.get(gong_name, "")
    if not pure or len(guastr) != 6:
        return False, False
    yao4_back = (guastr[3] == pure[3])   # 4爻已回退→游魂候选
    yao5_changed = (guastr[4] != pure[4])  # 5爻保留变化→归魂候选
    if shi == 4 and ying == 1:
        return (yao4_back, False)
    if shi == 3 and ying == 6:
        return (False, yao5_changed)
    return False, False


def _liuqin_by_gong(gong_wuxing, yao_wuxing):
    """按本卦宫五行定爻的六亲（传统本卦宫法）"""
    if yao_wuxing == gong_wuxing:
        return "兄弟"
    if _SHENG.get(gong_wuxing) == yao_wuxing:
        return "子孙"
    if _KE.get(gong_wuxing) == yao_wuxing:
        return "妻财"
    if _KE.get(yao_wuxing) == gong_wuxing:
        return "官鬼"
    if _SHENG.get(yao_wuxing) == gong_wuxing:
        return "父母"
    return "?"


def detect_patterns(lines, ben_gua_attr, bian_gua_attr, month_branch="", ri_chen="",
                    ben_you_hun=False, ben_gui_hun=False,
                    bian_you_hun=False, bian_gui_hun=False):
    """特殊格局自动检测（规则化判断，非 AI 手动识别）

    从 lines 数据自动推断三会局 / 三合局 / 地支六合 / 地支六冲 / 伏吟 / 反吟 /
    独发 / 独静 / 本卦六冲卦 / 本卦六合卦。游魂/归魂由 _infer_you_gui_hun()
    用八宫变化规则推断后传入（不再依赖 GUA64 第 10 列字符串标签）。
    SKILL.md 第三步应直接读取 JSON 的 patterns 字段，不再让 AI 手动识别。

    参数：
      lines:          build_paipan_data 产出的 lines 数组
      ben_gua_attr:   本卦属性中文字符串（六合/六冲标记，不再用于游魂归魂判定）
      bian_gua_attr:  变卦属性，同上
      month_branch:   月建地支（用于判断日月补字 / 日月引动）
      ri_chen:         日辰地支（用于判断日月补字 / 日月引动）
      ben_you_hun:    本卦游魂 bool（build_paipan_data 规则推断传入）
      ben_gui_hun:    本卦归魂 bool（同上）
      bian_you_hun:   变卦游魂 bool（同上，无变卦时为 False）
      bian_gui_hun:   变卦归魂 bool（同上，无变卦时为 False）

    返回 dict。
    """
    dizhi_list = [l["di_zhi"] for l in lines]
    dizhi_set = set(dizhi_list)
    dong_lines = [l for l in lines if l["dong"]]
    dong_count = len(dong_lines)
    dong_set = {l["di_zhi"] for l in dong_lines}

    # ── 三会局：5 态（严格成局 / 成局 / 三会 / 三会之势）──
    # 激活源：动爻 或 日月入组 → 可成局。旬空是压制因子，暂时冻结状态，出空自动升级。
    sanhui = []
    for group in DIZHI_SANHUI_GROUPS:
        present = [dz for dz in group if dz in dizhi_set]
        if len(present) != 3:
            continue
        group_lines = [l for l in lines if l["di_zhi"] in group]
        dong_positions = [l["pos"] for l in group_lines if l["dong"]]
        sun_moon_in_group = (month_branch in group) or (ri_chen in group)
        kong_positions = [l["pos"] for l in group_lines if l.get("kong_wang")]
        has_kong = bool(kong_positions)

        # ── 有动爻：动则不空，直接判定 ──
        if len(dong_positions) == 3:
            status = "严格成局"
        elif len(dong_positions) == 2 and sun_moon_in_group:
            status = "严格成局"
        elif len(dong_positions) >= 1:
            status = "成局"
        # ── 全静：日月入组可激活（与三合局日月引动逻辑一致）──
        elif sun_moon_in_group:
            if has_kong:
                # 日月入组但旬空冻结 → 待出空成局
                status = "三会"
            else:
                status = "成局"
        # ── 全静 + 日月不在组：仅有气象，未激活 ──
        else:
            status = "三会之势"
            # 旬空暂压气象，出空后恢复为三会之势（状态名不变，kong_positions 标记供 Agent 查应期）

        # 补充待升级信息（出空条件由 Agent 读取 kong_positions 自行推算）
        sanhui.append({
            "group": "".join(group),
            "status": status,
            "dong_positions": dong_positions,
            "static_positions": static_positions,
            "kong_positions": kong_positions,
            "sun_moon_in_group": sun_moon_in_group,
            "has_kong": has_kong,
        })

    # ── 三合局：3 档 + 日月引动 + 半合子型 ──
    sanhe = []
    for g0, g1, g2, wx in DIZHI_SANHE_GROUPS:
        group_tuple = (g0, g1, g2)
        present_in_gua = [dz for dz in group_tuple if dz in dizhi_set]
        missing_in_gua = [dz for dz in group_tuple if dz not in dizhi_set]
        group_lines = [l for l in lines if l["di_zhi"] in group_tuple]
        dong_positions = [l["pos"] for l in group_lines if l["dong"]]
        kong_positions = [l["pos"] for l in group_lines if l.get("kong_wang")]
        has_dong = bool(dong_positions)
        sun_moon_fills = (
            len(missing_in_gua) == 1
            and missing_in_gua[0] in (month_branch, ri_chen)
        )

        if len(present_in_gua) == 3:
            # 日月引动：日辰或月建占其中一字，可代替动爻激活合局
            sun_moon_activates = (month_branch in group_tuple) or (ri_chen in group_tuple)
            if has_dong:
                status = "成局"
            elif sun_moon_activates:
                status = "成局"  # 日月引动
            else:
                status = "虚合"
            subtype = ""
            missing = ""
        elif len(present_in_gua) == 2:
            if sun_moon_fills:
                # 二字 + 日月补字 = 三字俱全
                status = "成局" if has_dong else "虚合"
                subtype = ""
                missing = missing_in_gua[0]
            elif has_dong:
                # 半合：二字现 + 含动爻
                status = "半合"
                present_set = set(present_in_gua)
                if present_set == {g0, g1}:
                    subtype = "长生帝旺"
                elif present_set == {g1, g2}:
                    subtype = "帝旺墓库"
                elif present_set == {g0, g2}:
                    subtype = "长生墓库"
                else:
                    subtype = ""
                missing = missing_in_gua[0] if missing_in_gua else ""
            else:
                continue  # 二字现 + 全静 + 无日月补 → 不记录
        else:
            continue  # 只 1 字 → 不记录

        sanhe.append({
            "group": g0 + g1 + g2,
            "wuxing": wx,
            "status": status,
            "subtype": subtype,
            "dong_positions": dong_positions,
            "kong_positions": kong_positions,
            "missing": missing,
            "sun_moon_fills": sun_moon_fills,
        })

    # ── 地支六合：卦中任意两爻地支成合 ──
    liuhe = []
    for a, b in DIZHI_LIUHE_PAIRS:
        if a in dizhi_set and b in dizhi_set:
            pos = [l["pos"] for l in lines if l["di_zhi"] in (a, b)]
            liuhe.append({"pair": f"{a}{b}", "positions": pos})

    # ── 地支六冲：卦中任意两爻地支相冲 ──
    liuchong = []
    for a, b in DIZHI_LIUCHONG_PAIRS:
        if a in dizhi_set and b in dizhi_set:
            pos = [l["pos"] for l in lines if l["di_zhi"] in (a, b)]
            liuchong.append({"pair": f"{a}{b}", "positions": pos})

    # ── 伏吟：动爻变爻同地支 ──
    fuyin = []
    for l in dong_lines:
        bian = l.get("bian_yao")
        if bian and bian["di_zhi"] == l["di_zhi"]:
            fuyin.append(l["pos"])

    # ── 反吟：动爻变爻相冲 ──
    chong_set = {frozenset(p) for p in DIZHI_LIUCHONG_PAIRS}
    fanyin = []
    for l in dong_lines:
        bian = l.get("bian_yao")
        if bian and frozenset((l["di_zhi"], bian["di_zhi"])) in chong_set:
            fanyin.append(l["pos"])

    # ── 独发 / 独静 ──
    # 独发：六爻中仅一爻发动    独静：六爻中仅一爻不发动
    dufa = (dong_count == 1)
    dujing = (dong_count == 5)

    # ── 本卦 / 变卦属性（六合卦、六冲卦）──
    # 游魂/归魂 bool 由 build_paipan_data 调用 _infer_you_gui_hun() 规则推断传入
    ben_attr = ben_gua_attr or ""
    bian_attr = bian_gua_attr or ""
    ben_liuchong_gua = "六冲" in ben_attr
    ben_liuhe_gua = "六合" in ben_attr

    return {
        "sanhui_ju": sanhui,
        "sanhe_ju": sanhe,
        "dizhi_liuhe": liuhe,
        "dizhi_liuchong": liuchong,
        "fuyin_positions": fuyin,
        "fanyin_positions": fanyin,
        "dufa": dufa,
        "dujing": dujing,
        "ben_gua_attr": ben_attr,
        "bian_gua_attr": bian_attr,
        "ben_liuchong_gua": ben_liuchong_gua,
        "ben_liuhe_gua": ben_liuhe_gua,
        "ben_you_hun": ben_you_hun,
        "ben_gui_hun": ben_gui_hun,
        "bian_you_hun": bian_you_hun,
        "bian_gui_hun": bian_gui_hun,
        "dong_count": dong_count,
    }


# ═══════════════════════════════════════════════════════════════
#  纯 Python 干支计算（备选方案，无需 sxtwl）
# ═══════════════════════════════════════════════════════════════

# 2026-2086 年干支 + 立春日期（getYearGZ False=立春分界，节气精确到日）
# 格式：year → (年干, 年支, 立春日)
YEAR_GZ_LICHUN = {
    2026: ("丙", "午", 4), 2027: ("丁", "未", 4), 2028: ("戊", "申", 4),
    2029: ("己", "酉", 3), 2030: ("庚", "戌", 4), 2031: ("辛", "亥", 4),
    2032: ("壬", "子", 4), 2033: ("癸", "丑", 3), 2034: ("甲", "寅", 4),
    2035: ("乙", "卯", 4), 2036: ("丙", "辰", 4), 2037: ("丁", "巳", 3),
    2038: ("戊", "午", 4), 2039: ("己", "未", 4), 2040: ("庚", "申", 4),
    2041: ("辛", "酉", 3), 2042: ("壬", "戌", 4), 2043: ("癸", "亥", 4),
    2044: ("甲", "子", 4), 2045: ("乙", "丑", 3), 2046: ("丙", "寅", 4),
    2047: ("丁", "卯", 4), 2048: ("戊", "辰", 4), 2049: ("己", "巳", 3),
    2050: ("庚", "午", 3), 2051: ("辛", "未", 4), 2052: ("壬", "申", 4),
    2053: ("癸", "酉", 3), 2054: ("甲", "戌", 3), 2055: ("乙", "亥", 4),
    2056: ("丙", "子", 4), 2057: ("丁", "丑", 3), 2058: ("戊", "寅", 3),
    2059: ("己", "卯", 4), 2060: ("庚", "辰", 4), 2061: ("辛", "巳", 3),
    2062: ("壬", "午", 3), 2063: ("癸", "未", 4), 2064: ("甲", "申", 4),
    2065: ("乙", "酉", 3), 2066: ("丙", "戌", 3), 2067: ("丁", "亥", 4),
    2068: ("戊", "子", 4), 2069: ("己", "丑", 3), 2070: ("庚", "寅", 3),
    2071: ("辛", "卯", 4), 2072: ("壬", "辰", 4), 2073: ("癸", "巳", 3),
    2074: ("甲", "午", 3), 2075: ("乙", "未", 4), 2076: ("丙", "申", 4),
    2077: ("丁", "酉", 3), 2078: ("戊", "戌", 3), 2079: ("己", "亥", 4),
    2080: ("庚", "子", 4), 2081: ("辛", "丑", 3), 2082: ("壬", "寅", 3),
    2083: ("癸", "卯", 3), 2084: ("甲", "辰", 4), 2085: ("乙", "巳", 3),
    2086: ("丙", "午", 3),
}

# 五虎遁：年干 → 正月（寅月）月干
WUHUDUN = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊",
           "丙": "庚", "辛": "庚", "丁": "壬", "壬": "壬",
           "戊": "甲", "癸": "甲"}

# 五鼠遁：日干 → 子时（23-1点）时干
WUSHUDUN = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙",
            "丙": "戊", "辛": "戊", "丁": "庚", "壬": "庚",
            "戊": "壬", "癸": "壬"}

# 月支固定表（每月的分界节气近似日期，±1天误差）
_MONTH_ZHI_BOUNDARIES = [
    (1, 6, "丑"),   # 小寒 ≈ 1月6日
    (2, 4, "寅"),   # 立春 ≈ 2月4日
    (3, 6, "卯"),   # 惊蛰 ≈ 3月6日
    (4, 5, "辰"),   # 清明 ≈ 4月5日
    (5, 6, "巳"),   # 立夏 ≈ 5月6日
    (6, 6, "午"),   # 芒种 ≈ 6月6日
    (7, 7, "未"),   # 小暑 ≈ 7月7日
    (8, 7, "申"),   # 立秋 ≈ 8月7日
    (9, 8, "酉"),   # 白露 ≈ 9月8日
    (10, 8, "戌"),  # 寒露 ≈ 10月8日
    (11, 7, "亥"),  # 立冬 ≈ 11月7日
    (12, 7, "子"),  # 大雪 ≈ 12月7日
]


def _get_month_zhi(month, day):
    """根据日期确定月支（基于节气近似边界，±1天误差）"""
    # 显式逐月判断，避免跨年边界问题
    if month == 1:
        return "子" if day < 6 else "丑"
    elif month == 2:
        return "丑" if day < 4 else "寅"
    elif month == 3:
        return "寅" if day < 6 else "卯"
    elif month == 4:
        return "卯" if day < 5 else "辰"
    elif month == 5:
        return "辰" if day < 6 else "巳"
    elif month == 6:
        return "巳" if day < 6 else "午"
    elif month == 7:
        return "午" if day < 7 else "未"
    elif month == 8:
        return "未" if day < 7 else "申"
    elif month == 9:
        return "申" if day < 8 else "酉"
    elif month == 10:
        return "酉" if day < 8 else "戌"
    elif month == 11:
        return "戌" if day < 7 else "亥"
    elif month == 12:
        return "亥" if day < 7 else "子"


def get_day_ganzhi(year, month, day):
    """
    纯 Python 日柱计算，以 2026-04-20 甲子日为基准点。
    包含：类型校验、范围限制、阴阳匹配校验。
    """
    base_date = date(2026, 4, 20)

    try:
        target_year = int(year)
        target_month = int(month)
        target_day = int(day)
    except (TypeError, ValueError):
        raise ValueError(f"日期参数必须为纯数字: year={year}, month={month}, day={day}")

    if not (1900 <= target_year <= 2100):
        raise ValueError(f"年份 {target_year} 超出支持范围(1900-2100)")

    try:
        target_date = date(target_year, target_month, target_day)
    except ValueError as e:
        raise ValueError(f"无效的日期组合: {target_year}-{target_month}-{target_day}")

    delta_days = (target_date - base_date).days
    gan_index = delta_days % 10
    zhi_index = delta_days % 12

    # 阴阳匹配校验：阳干必配阳支
    if gan_index % 2 != zhi_index % 2:
        raise SystemError("排盘错误：检测到阴阳错配！")

    gan = TIANGAN[gan_index]
    zhi = DIZHI[zhi_index]
    return {"day_gan": gan, "day_zhi": zhi, "day_ganzhi": f"{gan}{zhi}"}


def calc_ganzhi_pure(year, month, day, hour=0):
    """
    纯 Python 四柱计算（无需 sxtwl）。
    返回与 calc_ganzhi(sxtwl) 相同结构的 dict。
    适用范围：2026-2086 年；节气边界近似（±1 天）。
    """
    # 1. 年柱
    entry = YEAR_GZ_LICHUN.get(year)
    if entry is None:
        raise ValueError(f"年份 {year} 超出纯 Python 支持范围 (2026-2086)，请安装 sxtwl")

    year_gan, year_zhi, lichun_day = entry

    # 立春前 → 用上一年的年柱
    if month < 2 or (month == 2 and day < lichun_day):
        prev_entry = YEAR_GZ_LICHUN.get(year - 1)
        if prev_entry:
            year_gan, year_zhi, _ = prev_entry
        else:
            # year-1 不在表内（如 2025），从 60 年周期推算
            gan_idx = (TIANGAN.index(year_gan) - 1) % 10
            zhi_idx = (DIZHI.index(year_zhi) - 1) % 12
            year_gan, year_zhi = TIANGAN[gan_idx], DIZHI[zhi_idx]

    year_gz = f"{year_gan}{year_zhi}"

    # 2. 月柱
    month_zhi = _get_month_zhi(month, day)
    yin_gan = WUHUDUN[year_gan]  # 寅月月干
    # 月干从寅月起始，偏移量 = 月支对寅的偏移
    month_offset = (DIZHI.index(month_zhi) - DIZHI.index("寅")) % 12
    month_gan_idx = (TIANGAN.index(yin_gan) + month_offset) % 10
    month_gan = TIANGAN[month_gan_idx]
    month_gz = f"{month_gan}{month_zhi}"

    # 3. 日柱
    day_result = get_day_ganzhi(year, month, day)
    day_gz = day_result["day_ganzhi"]
    ri_gan = day_result["day_gan"]
    ri_zhi = day_result["day_zhi"]

    # 4. 时柱（五鼠遁）
    hour_zhi_idx = ((hour + 1) // 2) % 12  # 0-23 → 子丑寅...
    hour_zhi = DIZHI[hour_zhi_idx]
    zi_gan = WUSHUDUN[ri_gan]
    hour_gan_idx = (TIANGAN.index(zi_gan) + hour_zhi_idx) % 10
    hour_gz = f"{TIANGAN[hour_gan_idx]}{hour_zhi}"

    # 5. 旬空
    # 日空
    cha = DIZHI_INDEX[ri_zhi] - TIANGAN_INDEX[ri_gan]
    if cha < 0:
        cha += 12  # 用地支周期 12 补正，非天干周期 10
    kw1 = KONGWANG_ZU[cha - 2]
    kw2 = KONGWANG_ZU[cha - 1]

    # 月空（月柱旬空）
    cha_m = DIZHI_INDEX[month_zhi] - TIANGAN_INDEX[month_gan]
    if cha_m < 0:
        cha_m += 12
    mk1 = KONGWANG_ZU[cha_m - 2]
    mk2 = KONGWANG_ZU[cha_m - 1]

    # 农历日期（纯 Python 查表）
    lunar_info = _solar_to_lunar_pure(year, month, day)
    lunar_year_gz = _lunar_year_gz(lunar_info["year"])
    lunar_str = _format_lunar_cn(
        lunar_year_gz, lunar_info["month"], lunar_info["day"], lunar_info["is_leap"]
    )

    return {
        "year": year_gz, "month": month_gz, "day": day_gz, "hour": hour_gz,
        "month_branch": month_zhi,
        "ri_gan": ri_gan, "ri_zhi": ri_zhi,
        "xunkong": [kw1, kw2],
        "yue_xunkong": [mk1, mk2],
        "lunar": lunar_str,
    }


# ═══════════════════════════════════════════════════════════════
#  农历日期计算（双轨：sxtwl 直接取 / 纯 Python 查表）
# ═══════════════════════════════════════════════════════════════
# 消除 AI 在生成 HTML 报告 meta.lunar 字段时手算农历的环节 —— 既易错又费 token。
# sxtwl 分支直接调用库；纯 Python 分支用下面这张预生成的查找表。

# 查找表已拆到独立文件 scripts/lunar_data.py，让主脚本保持干净。
# 数据结构、来源、为什么不能算法推算（77.5% 错误率）等说明见该文件头注释。
from lunar_data import LUNAR_TABLE_2025_2086


def _solar_to_lunar_pure(year, month, day):
    """纯 Python 公历转农历（基于 LUNAR_TABLE_2025_2086 查找表）。

    返回 dict：{year, month, day, is_leap}（year 为农历年数字，月日按农历）。
    超出 2025-2086 范围抛 ValueError。
    """
    target = date(year, month, day)

    # 1. 确定 target 所在的农历年（以正月初一分界）
    if year in LUNAR_TABLE_2025_2086:
        ny_m, ny_d = LUNAR_TABLE_2025_2086[year][:2]
        if target < date(year, ny_m, ny_d):
            lunar_year = year - 1
        else:
            lunar_year = year
    else:
        lunar_year = year - 1

    if lunar_year not in LUNAR_TABLE_2025_2086:
        raise ValueError(
            f"农历数据超出纯 Python 支持范围 (2025-2086)，年份 {year} 对应农历年 {lunar_year} 无数据。"
            f"请安装 sxtwl：pip install sxtwl"
        )

    # 2. 计算 delta_days（从农历正月初一算起的偏移）
    ny_m, ny_d = LUNAR_TABLE_2025_2086[lunar_year][:2]
    delta_days = (target - date(lunar_year, ny_m, ny_d)).days

    if delta_days < 0:
        raise ValueError("农历计算错误：delta_days < 0")

    # 3. 遍历月找命中
    _, _, months_bits, num_months, leap = LUNAR_TABLE_2025_2086[lunar_year]

    days_acc = 0
    for i in range(num_months):
        bit_pos = num_months - 1 - i
        m_days = 30 if (months_bits >> bit_pos) & 1 else 29

        if days_acc + m_days > delta_days:
            lunar_day = delta_days - days_acc + 1

            # 确定月号与闰标志（leap 是"闰几月"，序号 i 是按时间顺序的第几个月）
            if leap > 0 and i == leap:
                lunar_month = leap
                is_leap = True
            elif leap > 0 and i > leap:
                lunar_month = i  # 闰月之后，序号 i 对应月号 i
                is_leap = False
            else:
                lunar_month = i + 1  # 闰月之前或无闰月
                is_leap = False

            return {
                "year": lunar_year,
                "month": lunar_month,
                "day": lunar_day,
                "is_leap": is_leap,
            }
        days_acc += m_days

    raise ValueError(f"农历计算失败：{year}-{month}-{day} 超出农历年 {lunar_year} 范围")


# 中文月日数字（用于农历显示）
_LUNAR_MONTH_CN = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "腊"]
_LUNAR_DAY_CN = [
    "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
]


def _lunar_year_gz(lunar_year_num):
    """取农历年（数字）对应的干支，如 2026 → '丙午'。

    优先查 YEAR_GZ_LICHUN 表（精确，2026-2086）；超出表范围用 60 甲子周期推算
    （如 2025 → 乙巳，用于 2026 年初跨年场景）。
    """
    if lunar_year_num in YEAR_GZ_LICHUN:
        gan, zhi, _ = YEAR_GZ_LICHUN[lunar_year_num]
        return gan + zhi
    # 60 甲子周期推算：2026 = 丙午（天干 idx 2，地支 idx 6）
    delta = lunar_year_num - 2026
    gan_idx = (2 + delta) % 10
    zhi_idx = (6 + delta) % 12
    return TIANGAN[gan_idx] + DIZHI[zhi_idx]


def _format_lunar_cn(lunar_year_gz, lunar_month, lunar_day, is_leap):
    """格式化农历日期为中文表示，如 '丙午年五月廿六' / '丙午年闰五月廿六'。"""
    month_str = ("闰" if is_leap else "") + _LUNAR_MONTH_CN[lunar_month - 1]
    day_str = _LUNAR_DAY_CN[lunar_day - 1]
    return f"{lunar_year_gz}年{month_str}月{day_str}"


# ═══════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════

# ── 神煞计算（日干/日支/月支 → 神煞表）───────────────
# ruff: noqa: E501

_SANHE = {
    "申": ("申","子","辰"),"子": ("申","子","辰"),"辰": ("申","子","辰"),
    "寅": ("寅","午","戌"),"午": ("寅","午","戌"),"戌": ("寅","午","戌"),
    "亥": ("亥","卯","未"),"卯": ("亥","卯","未"),"未": ("亥","卯","未"),
    "巳": ("巳","酉","丑"),"酉": ("巳","酉","丑"),"丑": ("巳","酉","丑"),
}
_SANHE_SHENSHA = {
    ("申","子","辰"): ("酉","寅","辰","巳","午","子","亥"),
    ("寅","午","戌"): ("卯","申","戌","亥","子","午","巳"),
    ("亥","卯","未"): ("子","巳","未","申","酉","卯","寅"),
    ("巳","酉","丑"): ("午","亥","丑","寅","卯","酉","申"),
}
_GAN_SHENSHA = {
    #       天乙         文昌   羊刃  禄    金舆  太极               学堂   词馆
    "甲": (("丑","未"), "巳", "卯", "寅", "辰", ("子","午"),       "亥", "巳"),
    "乙": (("子","申"), "午", "寅", "卯", "巳", ("子","午"),       "午", "子"),
    "丙": (("亥","酉"), "申", "午", "巳", "未", ("卯","酉"),       "寅", "申"),
    "丁": (("亥","酉"), "酉", "巳", "午", "申", ("卯","酉"),       "酉", "卯"),
    "戊": (("丑","未"), "申", "午", "巳", "未", ("丑","辰","未","戌"), "寅", "申"),
    "己": (("子","申"), "酉", "巳", "午", "申", ("丑","辰","未","戌"), "酉", "卯"),
    "庚": (("午","寅"), "亥", "酉", "申", "戌", ("寅","亥"),       "巳", "亥"),
    "辛": (("午","寅"), "子", "申", "酉", "亥", ("寅","亥"),       "子", "午"),
    "壬": (("卯","巳"), "寅", "子", "亥", "丑", ("巳","申"),       "申", "寅"),
    "癸": (("卯","巳"), "卯", "亥", "子", "寅", ("巳","申"),       "卯", "酉"),
}
_YUEDE  = {"寅":"丙","午":"丙","戌":"丙","亥":"甲","卯":"甲","未":"甲","申":"壬","子":"壬","辰":"壬","巳":"庚","酉":"庚","丑":"庚"}
_TIANDE = {"寅":"丁","卯":"申","辰":"壬","巳":"辛","午":"亥","未":"甲","申":"癸","酉":"寅","戌":"丙","亥":"乙","子":"巳","丑":"庚"}
_TIANCHU= {"甲":"巳","乙":"午","丙":"子","丁":"巳","戊":"午","己":"申","庚":"寅","辛":"午","壬":"酉","癸":"亥"}


def compute_shensha(ri_gan, ri_zhi, month_zhi):
    """返回 {神煞名: [命中地支列表]}"""
    result = {}
    gi = _GAN_SHENSHA.get(ri_gan, (("",""),"","","","",("",""),"",""))
    tianyi, wenchang, yangren, lushen, jinyu, taiji, xuetang, ciguan = gi[0], gi[1], gi[2], gi[3], gi[4], gi[5], gi[6], gi[7]
    result["天乙贵人"] = list(tianyi) if isinstance(tianyi, tuple) else [tianyi]
    result["文昌"] = [wenchang]; result["羊刃"] = [yangren]; result["禄神"] = [lushen]
    result["金舆"] = [jinyu]; result["太极贵人"] = list(taiji) if isinstance(taiji, tuple) else [taiji]
    result["学堂"] = [xuetang]; result["词馆"] = [ciguan]
    result["天厨"] = [_TIANCHU.get(ri_gan, "")]; result["干禄"] = [lushen]; result["日禄"] = [lushen]
    sk = _SANHE.get(ri_zhi)
    if sk:
        th, ym, hg, js, zs, jx, ws = _SANHE_SHENSHA[sk]
        result["桃花"] = [th]; result["驿马"] = [ym]; result["华盖"] = [hg]
        result["劫煞"] = [js]; result["灾煞"] = [zs]; result["将星"] = [jx]; result["亡神"] = [ws]
        # 谋星：冲尾（与三合局尾位相冲）
        _CHONG = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅",
                  "卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
        result["谋星"] = [_CHONG.get(sk[2], "")]
    result["月德"] = [_YUEDE.get(month_zhi, "")]; result["天德"] = [_TIANDE.get(month_zhi, "")]
    # 天医：月支退一位
    _mz_idx = DIZHI.index(month_zhi)
    result["天医"] = [DIZHI[(_mz_idx - 1) % 12]]
    # 天喜：按季节（春戌、夏丑、秋辰、冬未）
    _SEASON = {"寅":"春","卯":"春","辰":"春","巳":"夏","午":"夏","未":"夏",
               "申":"秋","酉":"秋","戌":"秋","亥":"冬","子":"冬","丑":"冬"}
    _TIANXI = {"春":"戌","夏":"丑","秋":"辰","冬":"未"}
    result["天喜"] = [_TIANXI.get(_SEASON.get(month_zhi, ""), "")]
    return result


# ── 辅助函数 ──────────────────────────────────────────────

def parse_line_str(s):
    """解析 '子孙子水' → ('子孙', '子', '水') 或 None"""
    if not s or not s.strip():
        return None
    s = s.strip()
    liu_qin = s[:2]
    di_zhi = s[2]
    wu_xing = s[3] if len(s) > 3 else DIZHI_TO_WUXING.get(di_zhi, "")
    return (liu_qin, di_zhi, wu_xing)


# ═══════════════════════════════════════════════════════════════
#  六十四卦数据（来自 data.py）
# ═══════════════════════════════════════════════════════════════

# 格式: [初爻,二爻,三爻,四爻,五爻,上爻, 世爻位,应爻位, 特殊属性, 额外, 宫位, 卦名]

# ── 乾宫八卦 ──
a1 = ["子孙子水", "妻财寅木", "父母辰土", "官鬼午火", "兄弟申金", "父母戌土",
      6, 3, "六冲", "", "乾宫", "乾为天"]
a2 = ["父母丑土", "子孙亥水", "兄弟酉金", "官鬼午火", "兄弟申金", "父母戌土",
      1, 4, "", "", "乾宫", "天风姤"]
a3 = ["父母辰土", "官鬼午火", "兄弟申金", "官鬼午火", "兄弟申金", "父母戌土",
      2, 5, "", "", "乾宫", "天山遁"]
a4 = ["父母未土", "官鬼巳火", "妻财卯木", "官鬼午火", "兄弟申金", "父母戌土",
      3, 6, "六合", "", "乾宫", "天地否"]
a5 = ["父母未土", "官鬼巳火", "妻财卯木", "父母未土", "官鬼巳火", "妻财卯木",
      4, 1, "", "", "乾宫", "风地观"]
a6 = ["父母未土", "官鬼巳火", "妻财卯木", "父母戌土", "子孙子水", "妻财寅木",
      5, 2, "", "", "乾宫", "山地剥"]
a7 = ["父母未土", "官鬼巳火", "妻财卯木", "兄弟酉金", "父母未土", "官鬼巳火",
      4, 1, "", "游魂卦", "乾宫", "火地晋"]
a8 = ["子孙子水", "妻财寅木", "父母辰土", "兄弟酉金", "父母未土", "官鬼巳火",
      3, 6, "", "归魂卦", "乾宫", "火天大有"]

# ── 兑宫八卦 ──
b1 = ["官鬼巳火", "妻财卯木", "父母丑土", "子孙亥水", "兄弟酉金", "父母未土",
      6, 3, "六冲", "", "兑宫", "兑为泽"]
b2 = ["妻财寅木", "父母辰土", "官鬼午火", "子孙亥水", "兄弟酉金", "父母未土",
      1, 4, "六合", "", "兑宫", "泽水困"]
b3 = ["父母未土", "官鬼巳火", "妻财卯木", "子孙亥水", "兄弟酉金", "父母未土",
      2, 5, "", "", "兑宫", "泽地萃"]
b4 = ["父母辰土", "官鬼午火", "兄弟申金", "子孙亥水", "兄弟酉金", "父母未土",
      3, 6, "", "", "兑宫", "泽山咸"]
b5 = ["父母辰土", "官鬼午火", "兄弟申金", "兄弟申金", "父母戌土", "子孙子水",
      4, 1, "", "", "兑宫", "水山蹇"]
b6 = ["父母辰土", "官鬼午火", "兄弟申金", "父母丑土", "子孙亥水", "兄弟酉金",
      5, 2, "", "", "兑宫", "地山谦"]
b7 = ["父母辰土", "官鬼午火", "兄弟申金", "官鬼午火", "兄弟申金", "父母戌土",
      4, 1, "", "游魂卦", "兑宫", "雷山小过"]
b8 = ["官鬼巳火", "妻财卯木", "父母丑土", "官鬼午火", "兄弟申金", "父母戌土",
      3, 6, "", "归魂卦", "兑宫", "雷泽归妹"]

# ── 离宫八卦 ──
c1 = ["父母卯木", "子孙丑土", "官鬼亥水", "妻财酉金", "子孙未土", "兄弟巳火",
      6, 3, "六冲", "", "离宫", "离为火"]
c2 = ["子孙辰土", "兄弟午火", "妻财申金", "妻财酉金", "子孙未土", "兄弟巳火",
      1, 4, "六合", "", "离宫", "火山旅"]
c3 = ["子孙丑土", "官鬼亥水", "妻财酉金", "妻财酉金", "子孙未土", "兄弟巳火",
      2, 5, "", "", "离宫", "火风鼎"]
c4 = ["父母寅木", "子孙辰土", "兄弟午火", "妻财酉金", "子孙未土", "兄弟巳火",
      3, 6, "", "", "离宫", "火水未济"]
c5 = ["父母寅木", "子孙辰土", "兄弟午火", "子孙戌土", "官鬼子水", "父母寅木",
      4, 1, "", "", "离宫", "山水蒙"]
c6 = ["父母寅木", "子孙辰土", "兄弟午火", "子孙未土", "兄弟巳火", "父母卯木",
      5, 2, "", "", "离宫", "风水涣"]
c7 = ["父母寅木", "子孙辰土", "兄弟午火", "兄弟午火", "妻财申金", "子孙戌土",
      4, 1, "", "游魂卦", "离宫", "天水讼"]
c8 = ["父母卯木", "子孙丑土", "官鬼亥水", "兄弟午火", "妻财申金", "子孙戌土",
      3, 6, "", "归魂卦", "离宫", "天火同人"]

# ── 震宫八卦 ──
d1 = ["父母子水", "兄弟寅木", "妻财辰土", "子孙午火", "官鬼申金", "妻财戌土",
      6, 3, "六冲", "", "震宫", "震为雷"]
d2 = ["妻财未土", "子孙巳火", "兄弟卯木", "子孙午火", "官鬼申金", "妻财戌土",
      1, 4, "六合", "", "震宫", "雷地豫"]
d3 = ["兄弟寅木", "妻财辰土", "子孙午火", "子孙午火", "官鬼申金", "妻财戌土",
      2, 5, "", "", "震宫", "雷水解"]
d4 = ["妻财丑土", "父母亥水", "官鬼酉金", "子孙午火", "官鬼申金", "妻财戌土",
      3, 6, "", "", "震宫", "雷风恒"]
d5 = ["妻财丑土", "父母亥水", "官鬼酉金", "妻财丑土", "父母亥水", "官鬼酉金",
      4, 1, "", "", "震宫", "地风升"]
d6 = ["妻财丑土", "父母亥水", "官鬼酉金", "官鬼申金", "妻财戌土", "父母子水",
      5, 2, "", "", "震宫", "水风井"]
d7 = ["妻财丑土", "父母亥水", "官鬼酉金", "父母亥水", "官鬼酉金", "妻财未土",
      4, 1, "", "游魂卦", "震宫", "泽风大过"]
d8 = ["父母子水", "兄弟寅木", "妻财辰土", "父母亥水", "官鬼酉金", "妻财未土",
      3, 6, "", "归魂卦", "震宫", "泽雷随"]

# ── 巽宫八卦 ──
e1 = ["妻财丑土", "父母亥水", "官鬼酉金", "妻财未土", "子孙巳火", "兄弟卯木",
      6, 3, "六冲", "", "巽宫", "巽为风"]
e2 = ["父母子水", "兄弟寅木", "妻财辰土", "妻财未土", "子孙巳火", "兄弟卯木",
      1, 4, "", "", "巽宫", "风天小畜"]
e3 = ["兄弟卯木", "妻财丑土", "父母亥水", "妻财未土", "子孙巳火", "兄弟卯木",
      2, 5, "", "", "巽宫", "风火家人"]
e4 = ["父母子水", "兄弟寅木", "妻财辰土", "妻财未土", "子孙巳火", "兄弟卯木",
      3, 6, "", "", "巽宫", "风雷益"]
e5 = ["父母子水", "兄弟寅木", "妻财辰土", "子孙午火", "官鬼申金", "妻财戌土",
      4, 1, "六冲", "", "巽宫", "天雷无妄"]
e6 = ["父母子水", "兄弟寅木", "妻财辰土", "官鬼酉金", "妻财未土", "子孙巳火",
      5, 2, "", "", "巽宫", "火雷噬嗑"]
e7 = ["父母子水", "兄弟寅木", "妻财辰土", "妻财戌土", "父母子水", "兄弟寅木",
      4, 1, "", "游魂卦", "巽宫", "山雷颐"]
e8 = ["妻财丑土", "父母亥水", "官鬼酉金", "妻财戌土", "父母子水", "兄弟寅木",
      3, 6, "", "归魂卦", "巽宫", "山风蛊"]

# ── 坎宫八卦 ──
f1 = ["子孙寅木", "官鬼辰土", "妻财午火", "父母申金", "官鬼戌土", "兄弟子水",
      6, 3, "六冲", "", "坎宫", "坎为水"]
f2 = ["妻财巳火", "子孙卯木", "官鬼丑土", "父母申金", "官鬼戌土", "兄弟子水",
      1, 4, "六合", "", "坎宫", "水泽节"]
f3 = ["兄弟子水", "子孙寅木", "官鬼辰土", "父母申金", "官鬼戌土", "兄弟子水",
      2, 5, "", "", "坎宫", "水雷屯"]
f4 = ["子孙卯木", "官鬼丑土", "兄弟亥水", "父母申金", "官鬼戌土", "兄弟子水",
      3, 6, "", "", "坎宫", "水火既济"]
f5 = ["子孙卯木", "官鬼丑土", "兄弟亥水", "兄弟亥水", "父母酉金", "官鬼未土",
      4, 1, "", "", "坎宫", "泽火革"]
f6 = ["子孙卯木", "官鬼丑土", "兄弟亥水", "妻财午火", "父母申金", "官鬼戌土",
      5, 2, "", "", "坎宫", "雷火丰"]
f7 = ["子孙卯木", "官鬼丑土", "兄弟亥水", "官鬼丑土", "兄弟亥水", "父母酉金",
      4, 1, "", "游魂卦", "坎宫", "地火明夷"]
f8 = ["子孙寅木", "官鬼辰土", "妻财午火", "官鬼丑土", "兄弟亥水", "父母酉金",
      3, 6, "", "归魂卦", "坎宫", "地水师"]

# ── 艮宫八卦 ──
g1 = ["兄弟辰土", "父母午火", "子孙申金", "兄弟戌土", "妻财子水", "官鬼寅木",
      6, 3, "六冲", "", "艮宫", "艮为山"]
g2 = ["官鬼卯木", "兄弟丑土", "妻财亥水", "兄弟戌土", "妻财子水", "官鬼寅木",
      1, 4, "六合", "", "艮宫", "山火贲"]
g3 = ["妻财子水", "官鬼寅木", "兄弟辰土", "兄弟戌土", "妻财子水", "官鬼寅木",
      2, 5, "", "", "艮宫", "山天大畜"]
g4 = ["父母巳火", "官鬼卯木", "兄弟丑土", "兄弟戌土", "妻财子水", "官鬼寅木",
      3, 6, "", "", "艮宫", "山泽损"]
g5 = ["父母巳火", "官鬼卯木", "兄弟丑土", "子孙酉金", "兄弟未土", "父母巳火",
      4, 1, "", "", "艮宫", "火泽睽"]
g6 = ["父母巳火", "官鬼卯木", "兄弟丑土", "父母午火", "子孙申金", "兄弟戌土",
      5, 2, "", "", "艮宫", "天泽履"]
g7 = ["父母巳火", "官鬼卯木", "兄弟丑土", "兄弟未土", "父母巳火", "官鬼卯木",
      4, 1, "", "游魂卦", "艮宫", "风泽中孚"]
g8 = ["兄弟辰土", "父母午火", "子孙申金", "兄弟未土", "父母巳火", "官鬼卯木",
      3, 6, "", "归魂卦", "艮宫", "风山渐"]

# ── 坤宫八卦 ──
h1 = ["兄弟未土", "父母巳火", "官鬼卯木", "兄弟丑土", "妻财亥水", "子孙酉金",
      6, 3, "六冲", "", "坤宫", "坤为地"]
h2 = ["妻财子水", "官鬼寅木", "兄弟辰土", "兄弟丑土", "妻财亥水", "子孙酉金",
      1, 4, "六合", "", "坤宫", "地雷复"]
h3 = ["父母巳火", "官鬼卯木", "兄弟丑土", "兄弟丑土", "妻财亥水", "子孙酉金",
      2, 5, "", "", "坤宫", "地泽临"]
h4 = ["妻财子水", "官鬼寅木", "兄弟辰土", "兄弟丑土", "妻财亥水", "子孙酉金",
      3, 6, "六合", "", "坤宫", "地天泰"]
h5 = ["妻财子水", "官鬼寅木", "兄弟辰土", "父母午火", "子孙申金", "兄弟戌土",
      4, 1, "六冲", "", "坤宫", "雷天大壮"]
h6 = ["妻财子水", "官鬼寅木", "兄弟辰土", "妻财亥水", "子孙酉金", "兄弟未土",
      5, 2, "", "", "坤宫", "泽天夬"]
h7 = ["妻财子水", "官鬼寅木", "兄弟辰土", "子孙申金", "兄弟戌土", "妻财子水",
      4, 1, "", "游魂卦", "坤宫", "水天需"]
h8 = ["兄弟未土", "父母巳火", "官鬼卯木", "子孙申金", "兄弟戌土", "妻财子水",
      3, 6, "", "归魂卦", "坤宫", "水地比"]

# 六十四卦字典（键: 6位 1/2 字符串，自下而上；1=阳 2=阴）
GUA64 = {
    "111111": a1, "211111": a2, "221111": a3, "222111": a4,
    "222211": a5, "222221": a6, "222121": a7, "111121": a8,
    "112112": b1, "212112": b2, "222112": b3, "221112": b4,
    "221212": b5, "221222": b6, "221122": b7, "112122": b8,
    "121121": c1, "221121": c2, "211121": c3, "212121": c4,
    "212221": c5, "212211": c6, "212111": c7, "121111": c8,
    "122122": d1, "222122": d2, "212122": d3, "211122": d4,
    "211222": d5, "211212": d6, "211112": d7, "122112": d8,
    "211211": e1, "111211": e2, "121211": e3, "122211": e4,
    "122111": e5, "122121": e6, "122221": e7, "211221": e8,
    "212212": f1, "112212": f2, "122212": f3, "121212": f4,
    "121112": f5, "121122": f6, "121222": f7, "212222": f8,
    "221221": g1, "121221": g2, "111221": g3, "112221": g4,
    "112121": g5, "112111": g6, "112211": g7, "221211": g8,
    "222222": h1, "122222": h2, "112222": h3, "111222": h4,
    "111122": h5, "111112": h6, "111212": h7, "222212": h8,
}

# ── 藏爻（伏神）数据 ──
A1 = ["", "", "", "", "", ""]
A2 = ["", "妻财寅木", "", "", "", ""]
A3 = ["子孙子水", "妻财寅木", "", "", "", ""]
A4 = ["子孙子水", "", "", "", "", ""]
A5 = ["子孙子水", "", "", "", "兄弟申金", ""]
A6 = ["", "", "", "", "兄弟申金", ""]
A7 = ["子孙子水", "", "", "", "", ""]
A8 = ["", "", "", "", "", ""]

B1 = ["", "", "", "", "", ""]
B2 = ["", "", "", "", "", ""]
B3 = ["", "", "", "", "", ""]
B4 = ["", "妻财卯木", "", "", "", ""]
B5 = ["", "妻财卯木", "", "", "", ""]
B6 = ["", "妻财卯木", "", "", "", ""]
B7 = ["", "妻财卯木", "", "子孙亥水", "", ""]
B8 = ["", "", "", "子孙亥水", "", ""]

C1 = ["", "", "", "", "", ""]
C2 = ["父母卯木", "", "官鬼亥水", "", "", ""]
C3 = ["父母卯木", "", "", "", "", ""]
C4 = ["", "", "官鬼亥水", "", "", ""]
C5 = ["", "", "", "妻财酉金", "", ""]
C6 = ["", "", "官鬼亥水", "妻财酉金", "", ""]
C7 = ["", "", "官鬼亥水", "", "", ""]
C8 = ["", "", "", "", "", ""]

D1 = ["", "", "", "", "", ""]
D2 = ["父母子水", "", "", "", "", ""]
D3 = ["父母子水", "", "", "", "", ""]
D4 = ["", "兄弟寅木", "", "", "", ""]
D5 = ["", "兄弟寅木", "", "子孙午火", "", ""]
D6 = ["", "兄弟寅木", "", "子孙午火", "", ""]
D7 = ["", "兄弟寅木", "", "子孙午火", "", ""]
D8 = ["", "", "", "子孙午火", "", ""]

E1 = ["", "", "", "", "", ""]
E2 = ["", "", "官鬼酉金", "", "", ""]
E3 = ["", "", "官鬼酉金", "", "", ""]
E4 = ["", "", "官鬼酉金", "", "", ""]
E5 = ["", "", "", "", "", ""]
E6 = ["", "", "", "", "", ""]
E7 = ["", "", "官鬼酉金", "", "子孙巳火", ""]
E8 = ["", "", "", "", "子孙巳火", ""]

F1 = ["", "", "", "", "", ""]
F2 = ["", "", "", "", "", ""]
F3 = ["", "", "妻财午火", "", "", ""]
F4 = ["", "", "妻财午火", "", "", ""]
F5 = ["", "", "妻财午火", "", "", ""]
F6 = ["", "", "", "", "", ""]
F7 = ["", "", "妻财午火", "", "", ""]
F8 = ["", "", "", "", "", ""]

G1 = ["", "", "", "", "", ""]
G2 = ["", "父母午火", "子孙申金", "", "", ""]
G3 = ["兄弟辰土", "父母午火", "", "", "", ""]
G4 = ["", "", "子孙申金", "", "", ""]
G5 = ["", "", "子孙申金", "", "妻财子水", ""]
G6 = ["", "", "", "", "妻财子水", ""]
G7 = ["", "", "子孙申金", "", "妻财子水", ""]
G8 = ["", "", "", "", "妻财子水", ""]

H1 = ["", "", "", "", "", ""]
H2 = ["", "父母巳火", "", "", "", ""]
H3 = ["", "", "", "", "", ""]
H4 = ["", "父母巳火", "", "", "", ""]
H5 = ["", "", "", "", "", ""]
H6 = ["", "父母巳火", "", "", "", ""]
H7 = ["", "父母巳火", "", "", "", ""]
H8 = ["", "", "", "", "", ""]

CANGYAO64 = {
    "111111": A1, "211111": A2, "221111": A3, "222111": A4,
    "222211": A5, "222221": A6, "222121": A7, "111121": A8,
    "112112": B1, "212112": B2, "222112": B3, "221112": B4,
    "221212": B5, "221222": B6, "221122": B7, "112122": B8,
    "121121": C1, "221121": C2, "211121": C3, "212121": C4,
    "212221": C5, "212211": C6, "212111": C7, "121111": C8,
    "122122": D1, "222122": D2, "212122": D3, "211122": D4,
    "211222": D5, "211212": D6, "211112": D7, "122112": D8,
    "211211": E1, "111211": E2, "121211": E3, "122211": E4,
    "122111": E5, "122121": E6, "122221": E7, "211221": E8,
    "212212": F1, "112212": F2, "122212": F3, "121212": F4,
    "121112": F5, "121122": F6, "121222": F7, "212222": F8,
    "221221": G1, "121221": G2, "111221": G3, "112221": G4,
    "112121": G5, "112111": G6, "112211": G7, "221211": G8,
    "222222": H1, "122222": H2, "112222": H3, "111222": H4,
    "111122": H5, "111112": H6, "111212": H7, "222212": H8,
}


# ═══════════════════════════════════════════════════════════════
#  排盘核心逻辑
# ═══════════════════════════════════════════════════════════════

class LiuYaoPaipan:
    """六爻排盘"""

    def __init__(self):
        self.gua64 = GUA64
        self.cangyao64 = CANGYAO64

    # ── 起卦 ────────────────────────────────────────────

    @staticmethod
    def toss_coins():
        """三币摇卦：同时掷 3 枚铜钱，观察正反组合定爻象。
        每枚：生成随机 int → 对 2 取余 → 奇数=阳(花), 偶数=阴(字)。
        两字一花 → 少阳(1)；两花一字 → 少阴(2)
        全字(全阴) → 老阴(4)；全花(全阳) → 老阳(3)
        """
        # 三枚铜钱同时抛出，每枚：randint → %2 → 判奇偶
        coins = [random.randint(0, 9999) % 2 for _ in range(3)]
        # 0=偶数→阴(字), 1=奇数→阳(花)
        yin = coins.count(0)    # 字面数（阴）
        yang = coins.count(1)   # 花面数（阳）

        if yin == 3:            # 全字 → 老阴，动爻
            return "4"
        elif yin == 2:          # 两字一花 → 少阳
            return "1"
        elif yin == 1:          # 一字两花 → 少阴
            return "2"
        else:                   # 全花 → 老阳，动爻
            return "3"

    @staticmethod
    def generate_ygua():
        """自动摇出六爻（从初爻到上爻），返回 6 位编码字符串列表"""
        return [LiuYaoPaipan.toss_coins() for _ in range(6)]

    # ── 干支计算 ────────────────────────────────────────

    @staticmethod
    def calc_ganzhi(year, month, day, hour=0, minute=0):
        """双轨四柱计算：sxtwl（优先）→ 纯 Python（回退）"""
        if _SXTWL_AVAILABLE:
            # ── sxtwl 精确计算（节气边界精确到时辰）───────────
            day_obj = sxtwl.fromSolar(year, month, day)
            ygz = day_obj.getYearGZ(False)  # False=立春分界（传统六爻标准）
            year_gz = TIANGAN[ygz.tg] + DIZHI[ygz.dz]
            mgz = day_obj.getMonthGZ()
            month_gz = TIANGAN[mgz.tg] + DIZHI[mgz.dz]
            dgz = day_obj.getDayGZ()
            day_gz = TIANGAN[dgz.tg] + DIZHI[dgz.dz]
            safe_hour = hour if hour is not None else 0
            hgz = day_obj.getHourGZ(safe_hour)
            hour_gz = TIANGAN[hgz.tg] + DIZHI[hgz.dz]

            ri_gan = day_gz[0]
            ri_zhi = day_gz[1]
            cha = DIZHI_INDEX[ri_zhi] - TIANGAN_INDEX[ri_gan]
            if cha < 0:
                cha += 12  # 用地支周期 12 补正，非天干周期 10
            xunkong = [KONGWANG_ZU[cha - 2], KONGWANG_ZU[cha - 1]]

            # 月空
            month_gan = month_gz[0]
            month_zhi2 = month_gz[1]
            cha_m = DIZHI_INDEX[month_zhi2] - TIANGAN_INDEX[month_gan]
            if cha_m < 0:
                cha_m += 12
            yue_xunkong = [KONGWANG_ZU[cha_m - 2], KONGWANG_ZU[cha_m - 1]]

            # 农历日期（sxtwl 直接取，消除 AI 手算环节）
            lunar_year_num = day_obj.getLunarYear()
            lunar_month = day_obj.getLunarMonth()
            lunar_day = day_obj.getLunarDay()
            lunar_is_leap = day_obj.isLunarLeap()
            lunar_year_gz = _lunar_year_gz(lunar_year_num)
            lunar_str = _format_lunar_cn(lunar_year_gz, lunar_month, lunar_day, lunar_is_leap)

            return {
                "year": year_gz, "month": month_gz, "day": day_gz, "hour": hour_gz,
                "month_branch": month_gz[1],
                "ri_gan": ri_gan, "ri_zhi": ri_zhi,
                "xunkong": xunkong,
                "yue_xunkong": yue_xunkong,
                "lunar": lunar_str,
                "backend": "sxtwl",
            }
        else:
            # ── 纯 Python 回退（节气边界 ±1 天近似）────────
            result = calc_ganzhi_pure(year, month, day, hour)
            result["backend"] = "pure"
            return result

    # ── 排盘 ────────────────────────────────────────────

    @staticmethod
    def build_paipan_data(ygua, year, month, day, hour, minute, subject, intent, seed=None):
        """
        主入口：输入 ygua（6 位 1-4 编码列表，自下而上），输出完整 JSON 数据。
        seed 非空时记录到 JSON 输出，便于复现。
        """
        # 1. 计算干支
        gz = LiuYaoPaipan.calc_ganzhi(year, month, day, hour, minute)

        # 2. 识别动爻，生成主卦键
        gua = ygua.copy()          # 静爻（3→1, 4→2）
        dgua_raw = []              # 动爻信息 [pos, changed_val, ...]
        for i in range(6):
            if ygua[i] == "3":
                gua[i] = "1"
                dgua_raw.append(i)
                dgua_raw.append("1")
            elif ygua[i] == "4":
                gua[i] = "2"
                dgua_raw.append(i)
                dgua_raw.append("2")
        guastr = "".join(gua)

        main_gua_arr = GUA64[guastr]
        main_gua_name = f"{main_gua_arr[10].replace('宫', '')}-{main_gua_arr[11]}"
        main_gua_attr = main_gua_arr[8] if main_gua_arr[8] else ""
        # 游魂/归魂标签
        if main_gua_arr[9]:
            main_gua_attr = (main_gua_attr + " " if main_gua_attr else "") + main_gua_arr[9]
        shi_yao_pos = main_gua_arr[6]   # 1-6
        ying_yao_pos = main_gua_arr[7]  # 1-6
        ben_gua_gong = main_gua_arr[10]
        # 方案 C：游魂/归魂用八宫变化规则推断（不再读 main_gua_arr[9] 标签）
        ben_you_hun, ben_gui_hun = _infer_you_gui_hun(
            main_gua_arr[11], ben_gua_gong, shi_yao_pos, ying_yao_pos, guastr)

        # 3. 计算变卦键
        bbgua = [int(x) for x in gua]
        for j in range(0, len(dgua_raw), 2):
            idx = dgua_raw[j]
            if dgua_raw[j + 1] == "1":
                bbgua[idx] = 2
            else:
                bbgua[idx] = 1
        bguastr = "".join(str(x) for x in bbgua)

        has_dong = len(dgua_raw) > 0
        if has_dong:
            bian_gua_arr = GUA64[bguastr]
            bian_gua_name = f"{bian_gua_arr[10].replace('宫', '')}-{bian_gua_arr[11]}"
            bian_gua_attr = bian_gua_arr[8] if bian_gua_arr[8] else ""
            if bian_gua_arr[9]:
                bian_gua_attr = (bian_gua_attr + " " if bian_gua_attr else "") + bian_gua_arr[9]
            bian_gua_gong = bian_gua_arr[10]
            # 方案 C：变卦游魂/归魂规则推断
            bian_you_hun, bian_gui_hun = _infer_you_gui_hun(
                bian_gua_arr[11], bian_gua_gong, bian_gua_arr[6], bian_gua_arr[7], bguastr)
        else:
            bian_gua_arr = None
            bian_gua_name = None
            bian_gua_attr = None
            bian_gua_gong = None
            bian_you_hun, bian_gui_hun = False, False

        # 4. 动爻标记（按爻位索引 0-5）
        dong_set = {}
        for j in range(0, len(dgua_raw), 2):
            dong_set[dgua_raw[j]] = True

        # 5. 六神
        liushen_start = LIUSHEN_START[gz["ri_gan"]]

        # 6. 藏爻
        cangyao_list = CANGYAO64.get(guastr, ["", "", "", "", "", ""])

        # 7. 旬空检查
        ri_xunkong_set = set(gz["xunkong"])
        yue_xunkong_set = set(gz.get("yue_xunkong", []))

        # 7b. 本卦宫五行（用于变卦六亲按本卦宫重算）
        ben_gong_wuxing = _GONG_WUXING.get(main_gua_arr[10], "")

        # 7c. 神煞计算
        shensha_map = compute_shensha(gz["ri_gan"], gz["ri_zhi"], gz["month_branch"])

        # 8. 构建各爻
        lines = []
        for i in range(6):
            pos = i + 1

            # 主卦行
            parsed = parse_line_str(main_gua_arr[i])
            liu_qin, di_zhi, _ = parsed if parsed else ("", "", "")
            wu_xing = DIZHI_TO_WUXING.get(di_zhi, "")

            # 世应
            shi_ying = ""
            if pos == shi_yao_pos:
                shi_ying = "世"
            if pos == ying_yao_pos:
                shi_ying += "应"

            # 动爻
            is_dong = i in dong_set

            # 变爻（六亲按本卦宫重算，遵循传统本卦宫法）
            # 无论是否动爻，只要存在变卦就计算变卦纳甲（非动爻也需要显示完整的变卦信息）
            bian_yao = None
            if bian_gua_arr is not None:
                b_parsed = parse_line_str(bian_gua_arr[i])
                if b_parsed:
                    b_di_zhi = b_parsed[1]
                    b_wx = DIZHI_TO_WUXING.get(b_di_zhi, "")
                    bian_yao = {
                        "liu_qin": _liuqin_by_gong(ben_gong_wuxing, b_wx),
                        "di_zhi": b_di_zhi,
                        "wu_xing": b_wx,
                    }

            # 六神：自下而上排列（初爻得起始神，依次至上爻）
            # 日干甲乙起青龙、丙丁起朱雀、戊起勾陈、己起腾蛇、庚辛起白虎、壬癸起玄武
            # 初爻 i=0 得起始索引 liushen_start，每上一爻 +1，模 6 循环
            ls_idx = (liushen_start + i) % 6
            liu_shou = LIUSHEN_NAMES[ls_idx]

            # 伏神
            fu_shen = None
            cang_str = cangyao_list[i] if i < len(cangyao_list) else ""
            c_parsed = parse_line_str(cang_str)
            if c_parsed:
                fu_shen = {
                    "liu_qin": c_parsed[0],
                    "di_zhi": c_parsed[1],
                    "wu_xing": DIZHI_TO_WUXING.get(c_parsed[1], ""),
                }

            # 旬空
            kong_parts = []
            if di_zhi in ri_xunkong_set:
                kong_parts.append("日空")
            if di_zhi in yue_xunkong_set:
                kong_parts.append("月空")
            is_kong = "".join(kong_parts) if kong_parts else ""

            lines.append({
                "pos": pos,
                "di_zhi": di_zhi,
                "wu_xing": wu_xing,
                "liu_qin": liu_qin,
                "shi_ying": shi_ying,
                "dong": is_dong,
                "bian_yao": bian_yao,
                "liu_shou": liu_shou,
                "fu_shen": fu_shen,
                "kong_wang": is_kong,
                "ben_yin_yang": "阳" if gua[i] == "1" else "阴",
                "shensha": [name for name, dzs in shensha_map.items() if di_zhi in dzs],
            })

        # 9. 组装结果
        result = {
            "date": {
                "year": year, "month": month, "day": day,
                "hour": hour, "minute": minute,
            },
            "ganzhi": {
                "year": gz["year"], "month": gz["month"],
                "day": gz["day"], "hour": gz["hour"],
            },
            "backend": gz.get("backend", "unknown"),
            "lunar": gz.get("lunar", ""),
            "month_branch": gz["month_branch"],
            "ri_chen": gz["ri_zhi"],
            "kong_wang": gz["xunkong"],
            "yue_xunkong": gz.get("yue_xunkong", []),
            "question": subject,
            "intent": intent,
            "shensha": shensha_map,
            "ben_gua": main_gua_name,
            "ben_gua_gong": main_gua_arr[10],
            "ben_gua_attr": main_gua_attr or None,
            "bian_gua": bian_gua_name,
            "bian_gua_gong": bian_gua_gong,
            "bian_gua_attr": bian_gua_attr or None,
            "guastr": guastr,
            "bguastr": bguastr if has_dong else None,
            "ygua": "".join(ygua),
            "lines": lines,
            "patterns": detect_patterns(lines, main_gua_attr, bian_gua_attr,
                                       gz["month_branch"], gz["ri_zhi"],
                                       ben_you_hun, ben_gui_hun,
                                       bian_you_hun, bian_gui_hun),
            "seed": seed,
        }

        return result


# ═══════════════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="六爻自动排盘 — 三币摇卦 + 四柱 + 定卦 + 伏神",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python paipan.py --subject "下个月的工作运势" --intent "官运"
  python paipan.py --subject "遗失物品能否找回" --intent "失物" --yao "121314"
  python paipan.py --subject "感情发展" --year 2026 --month 6 --day 8 --hour 14
        """,
    )
    parser.add_argument("--subject", required=True, help="所占之事（必填）")
    parser.add_argument("--intent", default="通用",
                        help="意图类别：求财|官运|学业|感情|健康|孕产|出行|失物|词讼|天气|通用")
    parser.add_argument("--yao", default=None,
                        help="手动六爻编码（6位1-4，自下而上；不提供则三币随机）")
    parser.add_argument("--manual", action="store_true",
                        help="标记为手动排盘（配合 --yao 使用，在 JSON 中添加 mode: manual）")
    parser.add_argument("--from-json", default=None,
                        help="从已有排盘 JSON 文件导入（跳过摇卦和定卦，直接标准化输出）")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument("--day", type=int, default=None)
    parser.add_argument("--hour", type=int, default=None)
    parser.add_argument("--minute", type=int, default=0)
    parser.add_argument("--seed", type=int, default=None,
                        help="随机数种子（指定后摇卦结果可复现，不指定则真随机）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出 JSON 到文件（推荐，避免终端编码问题）")
    args = parser.parse_args()

    # seed 植入（仅影响自动摇卦；--yao 手动模式不受影响）
    if args.seed is not None and not args.yao:
        random.seed(args.seed)

    # 校验 intent
    if args.intent not in VALID_INTENTS:
        print(f"错误：无效的 intent 类别 '{args.intent}'。" 
              f"有效值：{'|'.join(sorted(VALID_INTENTS))}", file=sys.stderr)
        sys.exit(1)

    # 时间
    now = datetime.now()
    year = args.year if args.year is not None else now.year
    month = args.month if args.month is not None else now.month
    day = args.day if args.day is not None else now.day
    hour = args.hour if args.hour is not None else now.hour
    minute = args.minute

    # --from-json 模式：直接导入已有排盘数据，标准化输出
    if args.from_json:
        try:
            with open(args.from_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"错误：无法读取或解析 JSON 文件：{e}", file=sys.stderr)
            sys.exit(1)
        # 补全 subject / intent
        if "meta" in data:
            data["meta"]["question"] = data["meta"].get("question", args.subject)
            data["meta"]["intent"] = data["meta"].get("intent", args.intent)
            data["meta"]["mode"] = "import"
        else:
            data["meta"] = {"question": args.subject, "intent": args.intent, "mode": "import"}
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ JSON 已写入: {args.output}", file=sys.stderr)
        else:
            json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        return

    # 六爻编码
    if args.yao:
        yao_str = args.yao.strip()
        if len(yao_str) != 6 or not all(c in "1234" for c in yao_str):
            print("错误：--yao 必须是 6 位 1-4 的字符串（如 121314）", file=sys.stderr)
            sys.exit(1)
        ygua = list(yao_str)
    else:
        ygua = LiuYaoPaipan.generate_ygua()

    # 排盘
    try:
        data = LiuYaoPaipan.build_paipan_data(
            ygua, year, month, day, hour, minute, args.subject, args.intent,
            seed=args.seed,
        )
    except ValueError as e:
        msg = str(e)
        if "2026-2086" in msg:
            # 纯 Python 回退的年份越界——给用户更友好的提示
            print(f"错误：{msg}", file=sys.stderr)
            print("提示：请安装 sxtwl 以支持其他年份：pip install sxtwl", file=sys.stderr)
        else:
            print(f"错误：{msg}", file=sys.stderr)
        sys.exit(1)

    # 标记排盘模式
    if args.manual and args.yao:
        data["mode"] = "manual"

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 已写入: {args.output}", file=sys.stderr)
    else:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()