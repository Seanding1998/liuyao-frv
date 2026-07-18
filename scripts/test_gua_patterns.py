"""六十四卦特殊格局检测单元测试

验证 detect_patterns() 对 GUA64 表全部 64 卦的 you_hun/gui_hun/liuchong_gua/liuhe_gua
检测是否正确，防止中文 token 依赖（"游魂"/"归魂"/"六合"/"六冲" in attr 字符串）
因 GUA64 表改动而静默失败。

另覆盖：
- GUA64 表 6 卦静态数据正确性（纳甲/六亲/世应）—— 修 v1.5.x 数据 bug 的回归保护
- lines 数组驱动格局：三合局/三会局/六合/六冲/伏吟/反吟/独发/独静
- 三合三会的 3 档状态（成局/半合/虚合；严格成局/三会之势/虚势）
- 日月补字逻辑

用法：
    python scripts/test_gua_patterns.py

退出码：
    0 = 全部通过
    1 = 有失败项
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paipan import (
    GUA64,
    detect_patterns,
    DIZHI_LIUHE_PAIRS,
    DIZHI_LIUCHONG_PAIRS,
    DIZHI_SANHUI_GROUPS,
    DIZHI_SANHE_GROUPS,
)


def build_attr_from_gua_entry(entry):
    """复刻 build_paipan_data 第 972-974 行的 attr 拼接逻辑"""
    attr = entry[8] if entry[8] else ""
    if entry[9]:
        attr = (attr + " " if attr else "") + entry[9]
    return attr


def make_line(pos, di_zhi, dong=False, kong_wang=False, bian_di_zhi=None):
    """构造 detect_patterns 所需的 line dict"""
    line = {
        "pos": pos,
        "di_zhi": di_zhi,
        "dong": dong,
        "kong_wang": kong_wang,
    }
    if dong and bian_di_zhi is not None:
        line["bian_yao"] = {"di_zhi": bian_di_zhi}
    return line


# ═══════════════════════════════════════════════════════════════
#  测试 1：GUA64 表全量 you_hun/gui_hun/liuhe/liuchong
# ═══════════════════════════════════════════════════════════════
def test_gua64_table(failures):
    stats = {"you_hun": 0, "gui_hun": 0, "liuhe_gua": 0, "liuchong_gua": 0}
    total = 0

    for gua_key, entry in GUA64.items():
        total += 1
        gua_name = f"{entry[10]}-{entry[11]}"
        attr = build_attr_from_gua_entry(entry)

        expected_you_hun = "游魂" in (entry[9] or "")
        expected_gui_hun = "归魂" in (entry[9] or "")
        expected_liuhe = "六合" in (entry[8] or "")
        expected_liuchong = "六冲" in (entry[8] or "")

        result = detect_patterns([], attr, "")
        actual_you_hun = result["ben_you_hun"]
        actual_gui_hun = result["ben_gui_hun"]
        actual_liuhe = result["ben_liuhe_gua"]
        actual_liuchong = result["ben_liuchong_gua"]

        if actual_you_hun:
            stats["you_hun"] += 1
        if actual_gui_hun:
            stats["gui_hun"] += 1
        if actual_liuhe:
            stats["liuhe_gua"] += 1
        if actual_liuchong:
            stats["liuchong_gua"] += 1

        checks = [
            ("ben_you_hun", expected_you_hun, actual_you_hun),
            ("ben_gui_hun", expected_gui_hun, actual_gui_hun),
            ("ben_liuhe_gua", expected_liuhe, actual_liuhe),
            ("ben_liuchong_gua", expected_liuchong, actual_liuchong),
        ]
        for field, exp, act in checks:
            if exp != act:
                failures.append(
                    f"  ✗ [GUA64表] {gua_name}（attr={attr!r}）{field}: expected={exp} actual={act}"
                )

    print(f"=== 测试 1：GUA64 表全量检测（{total} 卦）===")
    print(f"  游魂卦: {stats['you_hun']}（期望 8）")
    print(f"  归魂卦: {stats['gui_hun']}（期望 8）")
    print(f"  六合卦: {stats['liuhe_gua']}")
    print(f"  六冲卦: {stats['liuchong_gua']}")

    if stats["you_hun"] != 8:
        failures.append(f"  ✗ 游魂卦数量异常：期望 8，实际 {stats['you_hun']}")
    if stats["gui_hun"] != 8:
        failures.append(f"  ✗ 归魂卦数量异常：期望 8，实际 {stats['gui_hun']}")


# ═══════════════════════════════════════════════════════════════
#  测试 1B：GUA64 表 6 卦静态数据正确性（纳甲/世应）
# ═══════════════════════════════════════════════════════════════
def test_gua64_correctness(failures):
    """核对 v1.5.x 修复过的 6 卦：天火同人/地雷复/水风井/地风升/火山旅/坤为地

    每卦核对：1-6 爻的六亲+地支+五行 + 世应位置 + 卦宫
    防止笔误再次回归。
    """
    print(f"\n=== 测试 1B：GUA64 表 6 卦静态数据正确性 ===")

    # 期望数据：每个卦的 1-6 爻 [六亲+地支+五行]，世位，应位，宫位
    expected_data = {
        "121111": {  # c8 天火同人
            "name": "天火同人",
            "lines": ["父母卯木", "子孙丑土", "官鬼亥水", "兄弟午火", "妻财申金", "子孙戌土"],
            "shi": 3, "ying": 6, "gong": "离宫",
        },
        "221121": {  # c2 火山旅
            "name": "火山旅",
            "lines": ["子孙辰土", "兄弟午火", "妻财申金", "妻财酉金", "子孙未土", "兄弟巳火"],
            "shi": 1, "ying": 4, "gong": "离宫",
        },
        "211222": {  # d5 地风升
            "name": "地风升",
            "lines": ["妻财丑土", "父母亥水", "官鬼酉金", "妻财丑土", "父母亥水", "官鬼酉金"],
            "shi": 4, "ying": 1, "gong": "震宫",
        },
        "211212": {  # d6 水风井
            "name": "水风井",
            "lines": ["妻财丑土", "父母亥水", "官鬼酉金", "官鬼申金", "妻财戌土", "父母子水"],
            "shi": 5, "ying": 2, "gong": "震宫",
        },
        "222222": {  # h1 坤为地
            "name": "坤为地",
            "lines": ["兄弟未土", "父母巳火", "官鬼卯木", "兄弟丑土", "妻财亥水", "子孙酉金"],
            "shi": 6, "ying": 3, "gong": "坤宫",
        },
        "122222": {  # h2 地雷复
            "name": "地雷复",
            "lines": ["妻财子水", "官鬼寅木", "兄弟辰土", "兄弟丑土", "妻财亥水", "子孙酉金"],
            "shi": 1, "ying": 4, "gong": "坤宫",
        },
    }

    for gua_key, exp in expected_data.items():
        if gua_key not in GUA64:
            failures.append(f"  ✗ {exp['name']}（key={gua_key}）不在 GUA64 表中")
            continue
        entry = GUA64[gua_key]
        # entry 结构：[爻1, 爻2, 爻3, 爻4, 爻5, 爻6, 世位, 应位, 六合六冲, 游魂归魂, 宫, 卦名]
        for i in range(6):
            if entry[i] != exp["lines"][i]:
                failures.append(
                    f"  ✗ {exp['name']} 第 {i+1} 爻错误：期望 {exp['lines'][i]!r}，"
                    f"实际 {entry[i]!r}"
                )
        if entry[6] != exp["shi"]:
            failures.append(
                f"  ✗ {exp['name']} 世位错误：期望 {exp['shi']}，实际 {entry[6]}"
            )
        if entry[7] != exp["ying"]:
            failures.append(
                f"  ✗ {exp['name']} 应位错误：期望 {exp['ying']}，实际 {entry[7]}"
            )
        if entry[10] != exp["gong"]:
            failures.append(
                f"  ✗ {exp['name']} 宫位错误：期望 {exp['gong']}，实际 {entry[10]}"
            )
        if entry[11] != exp["name"]:
            failures.append(
                f"  ✗ {exp['name']} 卦名字段错误：期望 {exp['name']}，实际 {entry[11]}"
            )

    print(f"  6 卦 × (6 爻 + 世应 + 宫 + 名) 字段核对，共 {len(expected_data)} 卦")


# ═══════════════════════════════════════════════════════════════
#  测试 2：三会局（sanhui_ju）— 3 档 + 动爻条件
# ═══════════════════════════════════════════════════════════════
def test_sanhui_ju(failures):
    print(f"\n=== 测试 2：三会局（sanhui_ju）— 3 档状态 ===")

    all_dz = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

    case_count = 0
    for group in DIZHI_SANHUI_GROUPS:
        leftovers = [dz for dz in all_dz if dz not in group][:3]
        # (动爻位列表, 期望状态, 描述)
        cases = [
            ([1, 2, 3], "严格成局", "三支都动"),
            ([1, 2],    "三会之势", "2 动 1 静"),
            ([1],       "三会之势", "1 动 2 静"),
            ([],        "虚势",     "三支全静"),
        ]
        for dong_positions, expected_status, desc in cases:
            lines = [
                make_line(1, group[0], dong=(1 in dong_positions)),
                make_line(2, group[1], dong=(2 in dong_positions)),
                make_line(3, group[2], dong=(3 in dong_positions)),
                make_line(4, leftovers[0]),
                make_line(5, leftovers[1]),
                make_line(6, leftovers[2]),
            ]
            result = detect_patterns(lines, "", "")
            matched = [s for s in result["sanhui_ju"] if s["group"] == "".join(group)]
            if not matched:
                failures.append(
                    f"  ✗ 三会局 {group}（{desc}）未被检测到"
                )
            elif matched[0]["status"] != expected_status:
                failures.append(
                    f"  ✗ 三会局 {group}（{desc}）状态错误：期望 {expected_status}，"
                    f"实际 {matched[0]['status']}"
                )
            case_count += 1

    # 日月补字：3 支俱全 + 2 动 + 日月补第三字 → 严格成局
    # 寅卯辰：1爻寅动、2爻卯动、3爻辰静；日辰=辰
    lines_sm = [
        make_line(1, "寅", dong=True),
        make_line(2, "卯", dong=True),
        make_line(3, "辰", dong=False),
        make_line(4, "午"),
        make_line(5, "申"),
        make_line(6, "戌"),
    ]
    result = detect_patterns(lines_sm, "", "", month_branch="", ri_chen="辰")
    matched = [s for s in result["sanhui_ju"] if s["group"] == "寅卯辰"]
    if not matched:
        failures.append("  ✗ 日月补字三会局（寅卯辰 + 日辰辰）未检测到")
    elif matched[0]["status"] != "严格成局":
        failures.append(
            f"  ✗ 日月补字三会局状态错误：期望 严格成局，实际 {matched[0]['status']}"
        )
    case_count += 1

    # 反例：缺一支不应记录
    lines_partial = [
        make_line(1, "亥"),
        make_line(2, "子"),
        make_line(3, "寅"),  # 缺丑
        make_line(4, "卯"),
        make_line(5, "巳"),
        make_line(6, "午"),
    ]
    result = detect_patterns(lines_partial, "", "")
    if result["sanhui_ju"]:
        failures.append(
            f"  ✗ 三会局反例失败：缺一支不应记录，实际 {result['sanhui_ju']}"
        )
    case_count += 1

    print(f"  4 组 × 4 种动爻组合 + 日月补字 + 缺支反例，共 {case_count} 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 2B：三合局（sanhe_ju）— 3 档 + 半合子型 + 日月补字
# ═══════════════════════════════════════════════════════════════
def test_sanhe_ju(failures):
    print(f"\n=== 测试 2B：三合局（sanhe_ju）— 3 档 + 半合子型 ===")

    all_dz = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    case_count = 0

    # 正例 A：3 字全现 + 1 字动 → 成局（每组）
    for g0, g1, g2, wx in DIZHI_SANHE_GROUPS:
        leftovers = [dz for dz in all_dz if dz not in (g0, g1, g2)][:3]
        lines = [
            make_line(1, g0, dong=True),
            make_line(2, g1),
            make_line(3, g2),
            make_line(4, leftovers[0]),
            make_line(5, leftovers[1]),
            make_line(6, leftovers[2]),
        ]
        result = detect_patterns(lines, "", "")
        matched = [s for s in result["sanhe_ju"] if s["group"] == g0 + g1 + g2]
        if not matched:
            failures.append(f"  ✗ 三合局 {g0}{g1}{g2}（1字动）未检测到")
        elif matched[0]["status"] != "成局":
            failures.append(
                f"  ✗ 三合局 {g0}{g1}{g2}（1字动）状态错误：期望 成局，"
                f"实际 {matched[0]['status']}"
            )
        case_count += 1

    # 正例 B：3 字全现 + 0 字动 → 虚合
    lines_xuhe = [
        make_line(1, "申"),
        make_line(2, "子"),
        make_line(3, "辰"),
        make_line(4, "寅"),
        make_line(5, "卯"),
        make_line(6, "巳"),
    ]
    result = detect_patterns(lines_xuhe, "", "")
    matched = [s for s in result["sanhe_ju"] if s["group"] == "申子辰"]
    if not matched:
        failures.append("  ✗ 三合局 申子辰（全静）未检测到")
    elif matched[0]["status"] != "虚合":
        failures.append(
            f"  ✗ 三合局 申子辰（全静）状态错误：期望 虚合，实际 {matched[0]['status']}"
        )
    case_count += 1

    # 正例 C：3 字全现 + 0 字动 + 日月占其中一字 → 成局（日月引动合局）
    lines_sm = [
        make_line(1, "申"),
        make_line(2, "子"),
        make_line(3, "辰"),
        make_line(4, "寅"),
        make_line(5, "卯"),
        make_line(6, "巳"),
    ]
    result = detect_patterns(lines_sm, "", "", month_branch="申", ri_chen="")
    matched = [s for s in result["sanhe_ju"] if s["group"] == "申子辰"]
    if not matched:
        failures.append("  ✗ 三合局 申子辰（全静+月建申）未检测到")
    elif matched[0]["status"] != "成局":
        failures.append(
            f"  ✗ 三合局 申子辰（全静+月建申）状态错误：期望 成局（日月引动），"
            f"实际 {matched[0]['status']}"
        )
    case_count += 1

    # 正例 D：2 字现 + 1 字动 + 日月补缺字 → 成局
    # 巳酉（缺丑），1爻巳动，日辰=丑
    lines_bh_sm = [
        make_line(1, "巳", dong=True),
        make_line(2, "酉"),
        make_line(3, "寅"),
        make_line(4, "卯"),
        make_line(5, "辰"),
        make_line(6, "午"),
    ]
    result = detect_patterns(lines_bh_sm, "", "", month_branch="", ri_chen="丑")
    matched = [s for s in result["sanhe_ju"] if s["group"] == "巳酉丑"]
    if not matched:
        failures.append("  ✗ 三合局 巳酉丑（半合+日月补字）未检测到")
    elif matched[0]["status"] != "成局":
        failures.append(
            f"  ✗ 三合局 巳酉丑（半合+日月补字）状态错误：期望 成局，"
            f"实际 {matched[0]['status']}"
        )
    case_count += 1

    # 正例 E：2 字现 + 1 字动 + 无日月补 → 半合（subtype 三型各测）
    banhe_cases = [
        (["申", "子"], "辰", "长生帝旺"),
        (["子", "辰"], "申", "帝旺墓库"),
        (["申", "辰"], "子", "长生墓库"),
    ]
    for present_pair, missing, expected_subtype in banhe_cases:
        lines = [
            make_line(1, present_pair[0], dong=True),
            make_line(2, present_pair[1]),
            make_line(3, "寅"),
            make_line(4, "卯"),
            make_line(5, "巳"),
            make_line(6, "午"),
        ]
        result = detect_patterns(lines, "", "")
        matched = [s for s in result["sanhe_ju"] if s["group"] == "申子辰"]
        if not matched:
            failures.append(
                f"  ✗ 半合 申子辰（{present_pair}）未检测到"
            )
        elif matched[0]["status"] != "半合":
            failures.append(
                f"  ✗ 半合 申子辰（{present_pair}）状态错误：期望 半合，"
                f"实际 {matched[0]['status']}"
            )
        elif matched[0]["subtype"] != expected_subtype:
            failures.append(
                f"  ✗ 半合 申子辰（{present_pair}）subtype 错误："
                f"期望 {expected_subtype}，实际 {matched[0]['subtype']}"
            )
        elif matched[0]["missing"] != missing:
            failures.append(
                f"  ✗ 半合 申子辰（{present_pair}）missing 错误："
                f"期望 {missing}，实际 {matched[0]['missing']}"
            )
        case_count += 1

    # 反例 A：2 字现 + 全静 → 不记录
    lines_bh_static = [
        make_line(1, "申"),
        make_line(2, "子"),
        make_line(3, "寅"),
        make_line(4, "卯"),
        make_line(5, "巳"),
        make_line(6, "午"),
    ]
    result = detect_patterns(lines_bh_static, "", "")
    matched = [s for s in result["sanhe_ju"] if s["group"] == "申子辰"]
    if matched:
        failures.append(
            f"  ✗ 半合反例失败：2 字全静不应记录，实际 {matched}"
        )
    case_count += 1

    # 反例 B：只 1 字现 → 不记录
    lines_1zi = [
        make_line(1, "申", dong=True),
        make_line(2, "寅"),
        make_line(3, "卯"),
        make_line(4, "巳"),
        make_line(5, "午"),
        make_line(6, "未"),
    ]
    result = detect_patterns(lines_1zi, "", "")
    matched = [s for s in result["sanhe_ju"] if s["group"] == "申子辰"]
    if matched:
        failures.append(
            f"  ✗ 1 字反例失败：只 1 字不应记录，实际 {matched}"
        )
    case_count += 1

    print(f"  成局 + 虚合 + 日月代动 + 半合日月补 + 3 种半合子型 + "
          f"2 反例，共 {case_count} 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 3：地支六合（dizhi_liuhe）
# ═══════════════════════════════════════════════════════════════
def test_dizhi_liuhe(failures):
    print(f"\n=== 测试 3：地支六合（dizhi_liuhe）===")

    for a, b in DIZHI_LIUHE_PAIRS:
        all_dz = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        used = {a, b}
        fillers = []
        for dz in all_dz:
            if dz in used:
                continue
            conflict = False
            for fa, fb in DIZHI_LIUHE_PAIRS:
                if (dz == fa and fb in used) or (dz == fb and fa in used):
                    conflict = True
                    break
            if not conflict:
                fillers.append(dz)
                used.add(dz)
                if len(fillers) == 4:
                    break

        if len(fillers) < 4:
            fillers = [dz for dz in all_dz if dz not in {a, b}][:4]

        lines = [
            make_line(1, a),
            make_line(2, b),
            make_line(3, fillers[0]),
            make_line(4, fillers[1]),
            make_line(5, fillers[2]),
            make_line(6, fillers[3]),
        ]
        result = detect_patterns(lines, "", "")
        pair_str = f"{a}{b}"
        if pair_str not in [p["pair"] for p in result["dizhi_liuhe"]]:
            failures.append(
                f"  ✗ 六合 {pair_str} 未被检测到（actual={result['dizhi_liuhe']}）"
            )

    # 反例：两支不相合
    lines_no_he = [
        make_line(1, "子"),
        make_line(2, "午"),  # 子午冲
        make_line(3, "寅"),
        make_line(4, "申"),
        make_line(5, "卯"),
        make_line(6, "酉"),
    ]
    result = detect_patterns(lines_no_he, "", "")
    if result["dizhi_liuhe"]:
        failures.append(
            f"  ✗ 六合反例失败：全冲不应有合，实际 {result['dizhi_liuhe']}"
        )

    print(f"  六对六合正例 + 全冲反例，共 {6 + 1} 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 4：地支六冲（dizhi_liuchong）
# ═══════════════════════════════════════════════════════════════
def test_dizhi_liuchong(failures):
    print(f"\n=== 测试 4：地支六冲（dizhi_liuchong）===")

    for a, b in DIZHI_LIUCHONG_PAIRS:
        all_dz = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        used = {a, b}
        fillers = []
        for dz in all_dz:
            if dz in used:
                continue
            conflict = False
            for fa, fb in DIZHI_LIUCHONG_PAIRS:
                if (dz == fa and fb in used) or (dz == fb and fa in used):
                    conflict = True
                    break
            if not conflict:
                fillers.append(dz)
                used.add(dz)
                if len(fillers) == 4:
                    break

        if len(fillers) < 4:
            fillers = [dz for dz in all_dz if dz not in {a, b}][:4]

        lines = [
            make_line(1, a),
            make_line(2, b),
            make_line(3, fillers[0]),
            make_line(4, fillers[1]),
            make_line(5, fillers[2]),
            make_line(6, fillers[3]),
        ]
        result = detect_patterns(lines, "", "")
        pair_str = f"{a}{b}"
        if pair_str not in [p["pair"] for p in result["dizhi_liuchong"]]:
            failures.append(
                f"  ✗ 六冲 {pair_str} 未被检测到（actual={result['dizhi_liuchong']}）"
            )

    # 反例：全合无冲
    lines_no_chong = [
        make_line(1, "子"),
        make_line(2, "丑"),
        make_line(3, "寅"),
        make_line(4, "亥"),
        make_line(5, "卯"),
        make_line(6, "戌"),
    ]
    result = detect_patterns(lines_no_chong, "", "")
    if result["dizhi_liuchong"]:
        failures.append(
            f"  ✗ 六冲反例失败：全合不应有冲，实际 {result['dizhi_liuchong']}"
        )

    print(f"  六对六冲正例 + 全合反例，共 {6 + 1} 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 5：伏吟（fuyin_positions）
# ═══════════════════════════════════════════════════════════════
def test_fuyin(failures):
    print(f"\n=== 测试 5：伏吟（fuyin_positions）===")

    lines_fuyin = [
        make_line(1, "子", dong=True, bian_di_zhi="子"),
        make_line(2, "丑"),
        make_line(3, "寅"),
        make_line(4, "卯"),
        make_line(5, "辰"),
        make_line(6, "巳"),
    ]
    result = detect_patterns(lines_fuyin, "", "")
    if result["fuyin_positions"] != [1]:
        failures.append(
            f"  ✗ 伏吟检测错误：期望 [1]，实际 {result['fuyin_positions']}"
        )

    lines_no_fuyin = [
        make_line(1, "子", dong=True, bian_di_zhi="丑"),
        make_line(2, "寅"),
        make_line(3, "卯"),
        make_line(4, "辰"),
        make_line(5, "巳"),
        make_line(6, "午"),
    ]
    result = detect_patterns(lines_no_fuyin, "", "")
    if result["fuyin_positions"]:
        failures.append(
            f"  ✗ 伏吟反例失败：动变不同支不应有伏吟，实际 {result['fuyin_positions']}"
        )

    print(f"  动变同支正例 + 动变异支反例，共 2 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 6：反吟（fanyin_positions）
# ═══════════════════════════════════════════════════════════════
def test_fanyin(failures):
    print(f"\n=== 测试 6：反吟（fanyin_positions）===")

    lines_fanyin = [
        make_line(1, "子", dong=True, bian_di_zhi="午"),
        make_line(2, "丑"),
        make_line(3, "寅"),
        make_line(4, "卯"),
        make_line(5, "辰"),
        make_line(6, "巳"),
    ]
    result = detect_patterns(lines_fanyin, "", "")
    if result["fanyin_positions"] != [1]:
        failures.append(
            f"  ✗ 反吟检测错误：期望 [1]，实际 {result['fanyin_positions']}"
        )

    lines_no_fanyin = [
        make_line(1, "子", dong=True, bian_di_zhi="寅"),
        make_line(2, "丑"),
        make_line(3, "卯"),
        make_line(4, "辰"),
        make_line(5, "巳"),
        make_line(6, "午"),
    ]
    result = detect_patterns(lines_no_fanyin, "", "")
    if result["fanyin_positions"]:
        failures.append(
            f"  ✗ 反吟反例失败：动变相生不应有反吟，实际 {result['fanyin_positions']}"
        )

    print(f"  动变相冲正例 + 动变相生反例，共 2 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 7：独发（dufa）/ 独静（dujing）
# ═══════════════════════════════════════════════════════════════
def test_dufa_dujing(failures):
    print(f"\n=== 测试 7：独发（dufa）/ 独静（dujing）===")

    lines_dufa = [
        make_line(1, "子", dong=True),
        make_line(2, "丑"),
        make_line(3, "寅"),
        make_line(4, "卯"),
        make_line(5, "辰"),
        make_line(6, "巳"),
    ]
    result = detect_patterns(lines_dufa, "", "")
    if not result["dufa"]:
        failures.append("  ✗ 独发检测错误：1 动期望 dufa=True")
    if result["dujing"]:
        failures.append("  ✗ 独发误判 dujing：1 动不应触发 dujing")

    lines_dujing = [
        make_line(1, "子", dong=True),
        make_line(2, "丑", dong=True),
        make_line(3, "寅", dong=True),
        make_line(4, "卯", dong=True),
        make_line(5, "辰", dong=True),
        make_line(6, "巳"),
    ]
    result = detect_patterns(lines_dujing, "", "")
    if not result["dujing"]:
        failures.append("  ✗ 独静检测错误：5 动期望 dujing=True")
    if result["dufa"]:
        failures.append("  ✗ 独静误判 dufa：5 动不应触发 dufa")

    for dong_count, label in [(0, "全静"), (2, "二动"), (3, "三动"), (6, "全动")]:
        lines = [make_line(i + 1, ["子", "丑", "寅", "卯", "辰", "巳"][i],
                           dong=(i < dong_count)) for i in range(6)]
        result = detect_patterns(lines, "", "")
        if dong_count == 1 and not result["dufa"]:
            failures.append(f"  ✗ {label}：期望 dufa=True")
        elif dong_count != 1 and result["dufa"]:
            failures.append(f"  ✗ {label}：dufa 应为 False")
        if dong_count == 5 and not result["dujing"]:
            failures.append(f"  ✗ {label}：期望 dujing=True")
        elif dong_count != 5 and result["dujing"]:
            failures.append(f"  ✗ {label}：dujing 应为 False")

    print(f"  独发正例 + 独静正例 + 4 个边界反例，共 6 用例")


# ═══════════════════════════════════════════════════════════════
#  测试 8：build_paipan_data 集成 — attr 拼接逻辑 + JSON patterns 字段
# ═══════════════════════════════════════════════════════════════
def test_build_paipan_attr_integration(failures):
    print(f"\n=== 测试 8：build_paipan_data attr 拼接集成 ===")

    from paipan import LiuYaoPaipan

    target_guas = {}
    for gua_key, entry in GUA64.items():
        attr = build_attr_from_gua_entry(entry)
        name = f"{entry[10]}-{entry[11]}"
        if "游魂" in (entry[9] or "") and "游魂" not in [t.get("tag") for t in target_guas.values()]:
            target_guas["游魂"] = {"key": gua_key, "name": name, "attr": attr, "tag": "游魂"}
        elif "归魂" in (entry[9] or "") and "归魂" not in [t.get("tag") for t in target_guas.values()]:
            target_guas["归魂"] = {"key": gua_key, "name": name, "attr": attr, "tag": "归魂"}
        elif "六合" in (entry[8] or "") and "六合" not in [t.get("tag") for t in target_guas.values()]:
            target_guas["六合"] = {"key": gua_key, "name": name, "attr": attr, "tag": "六合"}
        elif "六冲" in (entry[8] or "") and "六冲" not in [t.get("tag") for t in target_guas.values()]:
            target_guas["六冲"] = {"key": gua_key, "name": name, "attr": attr, "tag": "六冲"}
        if len(target_guas) >= 4:
            break

    if len(target_guas) < 4:
        failures.append(
            f"  ✗ 测试 8 准备失败：未找到 4 种代表卦（仅 {list(target_guas.keys())}）"
        )
        return

    for tag, info in target_guas.items():
        gua_key = info["key"]
        ygua = list(gua_key)
        try:
            data = LiuYaoPaipan.build_paipan_data(
                ygua=ygua,
                year=2026,
                month=7,
                day=17,
                hour=14,
                minute=30,
                subject="测试",
                intent="通用",
                seed=42,
            )
        except Exception as e:
            failures.append(f"  ✗ {tag} 卦 build_paipan_data 异常：{e}")
            continue

        patterns = data.get("patterns", {})
        for field in ("ben_you_hun", "ben_gui_hun",
                      "bian_you_hun", "bian_gui_hun"):
            if field not in patterns:
                failures.append(
                    f"  ✗ {tag} 卦 JSON patterns 缺字段：{field}"
                )

        expected = {
            "游魂": "ben_you_hun",
            "归魂": "ben_gui_hun",
            "六合": "ben_liuhe_gua",
            "六冲": "ben_liuchong_gua",
        }
        field = expected[tag]
        if not patterns.get(field):
            failures.append(
                f"  ✗ {tag} 卦（{info['name']}）期望 {field}=True，实际 False（attr={info['attr']!r}）"
            )

    print(f"  4 种代表卦（游魂/归魂/六合/六冲）build_paipan_data 集成，共 4 用例")


# ── 测试 9：游魂归魂规则校验（防 GUA64 第 10 列错标）──
# 规则定义（不依赖 GUA64 表标签）：
#   游魂卦 = 八宫第 7 卦，世爻 4 应爻 1
#   归魂卦 = 八宫第 8 卦，世爻 3 应爻 6
# 期望清单：从公开纳甲筮法表硬编码（(宫, 卦名) 二元组）

EXPECTED_YOU_HUN = [
    ("乾宫", "火地晋"), ("兑宫", "雷山小过"),
    ("离宫", "天水讼"), ("震宫", "泽风大过"),
    ("巽宫", "山雷颐"), ("坎宫", "地火明夷"),
    ("艮宫", "风泽中孚"), ("坤宫", "水天需"),
]
EXPECTED_GUI_HUN = [
    ("乾宫", "火天大有"), ("兑宫", "雷泽归妹"),
    ("离宫", "天火同人"), ("震宫", "泽雷随"),
    ("巽宫", "山风蛊"), ("坎宫", "地水师"),
    ("艮宫", "风山渐"), ("坤宫", "水地比"),
]


def test_you_gui_hun_rule_consistency(failures):
    """用'世应位置 + 宫名硬编码'反推校验 GUA64 表第 10 列标签无误标。

    防止 detect_patterns 第 285-288 行 `"游魂" in ben_attr` 子串匹配
    因 GUA64 表某行漏标/错标而静默失败。
    """
    case_count = 0
    you_hun_in_table = []   # [(gong, name, shi, ying, guastr), ...]
    gui_hun_in_table = []
    other_tag_in_table = []  # 第 10 列非空但既不是游魂也不是归魂

    for guastr, arr in GUA64.items():
        tag = arr[9] or ""
        gong = arr[10]
        name = arr[11]
        shi = arr[6]
        ying = arr[7]
        if "游魂" in tag:
            you_hun_in_table.append((gong, name, shi, ying, guastr))
        elif "归魂" in tag:
            gui_hun_in_table.append((gong, name, shi, ying, guastr))
        elif tag:
            other_tag_in_table.append((gong, name, tag, guastr))
        case_count += 1

    # 校验 1：数量必须是 8/8（八宫各 1 个）
    if len(you_hun_in_table) != 8:
        failures.append(
            f"  ✗ 游魂卦数量异常：期望 8 个，实际 {len(you_hun_in_table)} 个"
        )
    if len(gui_hun_in_table) != 8:
        failures.append(
            f"  ✗ 归魂卦数量异常：期望 8 个，实际 {len(gui_hun_in_table)} 个"
        )

    # 校验 2：(宫, 名) 与期望完全一致
    you_hun_actual_pairs = [(g, n) for g, n, s, y, k in you_hun_in_table]
    gui_hun_actual_pairs = [(g, n) for g, n, s, y, k in gui_hun_in_table]
    for g, n in EXPECTED_YOU_HUN:
        if (g, n) not in you_hun_actual_pairs:
            failures.append(
                f"  ✗ 游魂卦缺失：期望 {g}-{n}，GUA64 表未标'游魂卦'"
            )
    for g, n in EXPECTED_GUI_HUN:
        if (g, n) not in gui_hun_actual_pairs:
            failures.append(
                f"  ✗ 归魂卦缺失：期望 {g}-{n}，GUA64 表未标'归魂卦'"
            )
    for g, n in you_hun_actual_pairs:
        if (g, n) not in EXPECTED_YOU_HUN:
            failures.append(
                f"  ✗ 游魂卦误标：{g}-{n} 不在期望的 8 个游魂卦清单内"
            )
    for g, n in gui_hun_actual_pairs:
        if (g, n) not in EXPECTED_GUI_HUN:
            failures.append(
                f"  ✗ 归魂卦误标：{g}-{n} 不在期望的 8 个归魂卦清单内"
            )

    # 校验 3：游魂世爻 4 应爻 1；归魂世爻 3 应爻 6
    for g, n, s, y, k in you_hun_in_table:
        if s != 4 or y != 1:
            failures.append(
                f"  ✗ 游魂 {g}-{n} 世应位置错：世{s}应{y}（期望 世4应1）"
            )
    for g, n, s, y, k in gui_hun_in_table:
        if s != 3 or y != 6:
            failures.append(
                f"  ✗ 归魂 {g}-{n} 世应位置错：世{s}应{y}（期望 世3应6）"
            )

    # 校验 4：八宫各有 1 游魂 + 1 归魂（防同宫出现两个或缺失）
    you_hun_gongs = {g for g, n, s, y, k in you_hun_in_table}
    gui_hun_gongs = {g for g, n, s, y, k in gui_hun_in_table}
    all_gongs = {"乾宫", "兑宫", "离宫", "震宫",
                 "巽宫", "坎宫", "艮宫", "坤宫"}
    if you_hun_gongs != all_gongs:
        missing = all_gongs - you_hun_gongs
        failures.append(f"  ✗ 游魂卦宫位缺失：{missing}")
    if gui_hun_gongs != all_gongs:
        missing = all_gongs - gui_hun_gongs
        failures.append(f"  ✗ 归魂卦宫位缺失：{missing}")

    # 校验 5：第 10 列若有其他标签（既不是游魂也不是归魂）→ 报告
    for g, n, t, k in other_tag_in_table:
        failures.append(
            f"  ✗ GUA64[{k}] {g}-{n} 第 10 列有未知标签：{t!r}"
        )

    print(f"=== 测试 9：游魂归魂规则一致性（防 GUA64 表错标）===")
    print(f"  8 游魂 + 8 归魂 × (宫名 + 世应 + 数量) 校验，共 {case_count} 卦扫描")


def main():
    failures = []

    test_gua64_table(failures)
    test_gua64_correctness(failures)
    test_sanhui_ju(failures)
    test_sanhe_ju(failures)
    test_dizhi_liuhe(failures)
    test_dizhi_liuchong(failures)
    test_fuyin(failures)
    test_fanyin(failures)
    test_dufa_dujing(failures)
    test_build_paipan_attr_integration(failures)
    test_you_gui_hun_rule_consistency(failures)

    if failures:
        print(f"\n❌ 失败 {len(failures)} 项:")
        for f in failures:
            print(f)
        sys.exit(1)
    else:
        print(f"\n✅ 全部 11 类测试通过。")
        sys.exit(0)


if __name__ == "__main__":
    main()
