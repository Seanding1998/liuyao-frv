#!/usr/bin/env python3
"""六爻卦象 HTML 报告生成器 v1.4。

新增:
- 本卦/变卦/互卦 三栏盘面展示
- 错卦/综卦 切换按钮
- 变卦完整阴阳爻显示

用法:
    python generate_report.py --input data.json --output report.html
    python generate_report.py --input data.json               # 默认输出 liuyao-report.html
"""

import argparse
import json
import os
import sys
from datetime import datetime

# ── 卦符映射 ────────────────────────────────────────────────
GUA_FU = {"阳": "▅▅▅▅▅", "阴": "▅▅\u3000▅▅"}
GUA_FU_CLASS = {"阳": "fu-yang", "阴": "fu-yin"}

# ── 八卦数据库 ────────────────────────────────────────────────
# key: (初爻yang, 二爻yang, 三爻yang)  1=阳 0=阴
TRIGRAM_BY_LINES = {
    (1, 1, 1): "乾",
    (1, 1, 0): "兑",
    (1, 0, 1): "离",
    (1, 0, 0): "震",
    (0, 1, 1): "巽",
    (0, 1, 0): "坎",
    (0, 0, 1): "艮",
    (0, 0, 0): "坤",
}

TRIGRAM_SYMBOL = {
    "乾": "☰", "兑": "☱", "离": "☲", "震": "☳",
    "巽": "☴", "坎": "☵", "艮": "☶", "坤": "☷",
}

# ── 六十四卦名数据库 ──────────────────────────────────────────
# key: (上卦名, 下卦名)
GUA_NAMES = {
    ("乾", "乾"): "乾为天", ("乾", "巽"): "天风姤", ("乾", "艮"): "天山遁", ("乾", "坤"): "天地否",
    ("巽", "坤"): "风地观", ("艮", "坤"): "山地剥", ("离", "坤"): "火地晋", ("离", "乾"): "火天大有",
    ("兑", "兑"): "兑为泽", ("兑", "坎"): "泽水困", ("兑", "坤"): "泽地萃", ("兑", "艮"): "泽山咸",
    ("坎", "艮"): "水山蹇", ("坤", "艮"): "地山谦", ("震", "艮"): "雷山小过", ("震", "兑"): "雷泽归妹",
    ("离", "离"): "离为火", ("离", "艮"): "火山旅", ("离", "巽"): "火风鼎", ("离", "坎"): "火水未济",
    ("艮", "坎"): "山水蒙", ("巽", "坎"): "风水涣", ("乾", "坎"): "天水讼", ("乾", "离"): "天火同人",
    ("震", "震"): "震为雷", ("震", "坤"): "雷地豫", ("震", "坎"): "雷水解", ("震", "巽"): "雷风恒",
    ("坤", "巽"): "地风升", ("坎", "巽"): "水风井", ("兑", "巽"): "泽风大过", ("兑", "震"): "泽雷随",
    ("巽", "巽"): "巽为风", ("巽", "乾"): "风天小畜", ("巽", "离"): "风火家人", ("巽", "震"): "风雷益",
    ("乾", "震"): "天雷无妄", ("离", "震"): "火雷噬嗑", ("艮", "震"): "山雷颐", ("艮", "巽"): "山风蛊",
    ("坎", "坎"): "坎为水", ("坎", "兑"): "水泽节", ("坎", "震"): "水雷屯", ("坎", "离"): "水火既济",
    ("兑", "离"): "泽火革", ("震", "离"): "雷火丰", ("坤", "离"): "地火明夷", ("坤", "坎"): "地水师",
    ("艮", "艮"): "艮为山", ("艮", "离"): "山火贲", ("艮", "乾"): "山天大畜", ("艮", "兑"): "山泽损",
    ("离", "兑"): "火泽睽", ("乾", "兑"): "天泽履", ("巽", "兑"): "风泽中孚", ("巽", "艮"): "风山渐",
    ("坤", "坤"): "坤为地", ("坤", "震"): "地雷复", ("坤", "兑"): "地泽临", ("坤", "乾"): "地天泰",
    ("震", "乾"): "雷天大壮", ("兑", "乾"): "泽天夬", ("坎", "乾"): "水天需", ("坎", "坤"): "水地比",
}

# ── 辅助计算 ────────────────────────────────────────────────

def get_trigram(lines):
    """lines: (初爻, 二爻, 三爻) 每个 1=阳 0=阴"""
    return TRIGRAM_BY_LINES.get(tuple(lines), "?")


def get_gua_name(upper_name, lower_name):
    return GUA_NAMES.get((upper_name, lower_name), f"?{upper_name}{lower_name}?")


def ben_lines_from_yao(yao_list):
    """从 yao 列表提取本卦阴阳线 (1→6, bottom to top), 1=阳 0=阴"""
    sorted_yao = sorted(yao_list, key=lambda y: y["pos"])
    lines = []
    for y in sorted_yao:
        byy = y.get("ben_yin_yang")
        if byy not in ("阳", "阴"):
            raise ValueError(
                f"第{y['pos']}爻缺少有效的 ben_yin_yang 字段（当前值: {byy!r}），"
                f"必须为 '阳' 或 '阴'。请检查 JSON 中 yao 数组的每爻是否包含此字段。"
            )
        lines.append(1 if byy == "阳" else 0)
    return lines


def compute_bian_lines(ben_lines, yao_list):
    """计算变卦阴阳线。仅动爻翻转，其余不变。"""
    sorted_yao = sorted(yao_list, key=lambda y: y["pos"])
    bian = []
    for i, y in enumerate(sorted_yao):
        if y.get("dong", False):
            bian.append(1 - ben_lines[i])
        else:
            bian.append(ben_lines[i])
    return bian


def compute_hu_gua(ben_lines):
    """计算互卦。上卦取本卦 3-4-5 爻, 下卦取本卦 2-3-4 爻。"""
    # ben_lines: index 0=初爻, 1=二爻, ..., 5=上爻
    lower = (ben_lines[1], ben_lines[2], ben_lines[3])  # 二、三、四
    upper = (ben_lines[2], ben_lines[3], ben_lines[4])  # 三、四、五
    lname = get_trigram(lower)
    uname = get_trigram(upper)
    name = get_gua_name(uname, lname)
    # 互卦六爻 (1→6 从下到上): 初=本卦二爻,二=本卦三爻,三=本卦四爻,四=本卦三爻,五=本卦四爻,上=本卦五爻
    lines = [ben_lines[1], ben_lines[2], ben_lines[3],
             ben_lines[2], ben_lines[3], ben_lines[4]]
    return {"name": name, "lines": lines, "upper": uname, "lower": lname}


def compute_cuo_gua(ben_lines):
    """计算错卦：全部阴阳翻转。"""
    flipped = [1 - x for x in ben_lines]
    lname = get_trigram((flipped[0], flipped[1], flipped[2]))
    uname = get_trigram((flipped[3], flipped[4], flipped[5]))
    name = get_gua_name(uname, lname)
    return {"name": name, "lines": flipped, "upper": uname, "lower": lname}


def compute_zong_gua(ben_lines):
    """计算综卦：六爻上下颠倒。"""
    rev = list(reversed(ben_lines))
    lname = get_trigram((rev[0], rev[1], rev[2]))
    uname = get_trigram((rev[3], rev[4], rev[5]))
    name = get_gua_name(uname, lname)
    return {"name": name, "lines": rev, "upper": uname, "lower": lname}


def lines_to_fu_html(lines):
    """将 [1,0,1,0,1,0] (上→下) 转为卦符 HTML"""
    fu = [GUA_FU["阳"] if l else GUA_FU["阴"] for l in lines]
    cls = [GUA_FU_CLASS["阳"] if l else GUA_FU_CLASS["阴"] for l in lines]
    return "\n".join(
        f'<span class="gua-line {cls[i]}">{fu[i]}</span>'
        for i in range(6)
    )


# ── 地支→五行映射 ──────────────────────────────────────────
DI_ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}


def di_zhi_to_wuxing(dz: str) -> str:
    return DI_ZHI_WUXING.get(dz, "?")


def build_gua_panels(ben_lines, yao_list, bian_gua_name, ben_gua_name=None):
    """构建三栏卦象面板 + 错卦综卦切换 HTML。
    ben_gua_name: JSON meta 中的 ben_gua，用于面板显示（与标题/信息条保持一致）"""
    has_dong = any(y.get("dong", False) for y in yao_list)
    bian_lines = compute_bian_lines(ben_lines, yao_list)
    hu_gua = compute_hu_gua(ben_lines)
    cuo_gua = compute_cuo_gua(ben_lines)
    zong_gua = compute_zong_gua(ben_lines)

    # 重新计算变卦名（从阴阳线推算，确保准确）
    computed_bian_name = ""
    if has_dong:
        lname = get_trigram((bian_lines[0], bian_lines[1], bian_lines[2]))
        uname = get_trigram((bian_lines[3], bian_lines[4], bian_lines[5]))
        computed_bian_name = get_gua_name(uname, lname)
    else:
        computed_bian_name = "静卦（无变卦）"

    # 本卦名从 ben_lines 计算
    ben_lname = get_trigram((ben_lines[0], ben_lines[1], ben_lines[2]))
    ben_uname = get_trigram((ben_lines[3], ben_lines[4], ben_lines[5]))
    ben_name_from_lines = get_gua_name(ben_uname, ben_lname)

    parts = []
    # 三栏主面板
    parts.append('<div class="gua-panels">')

    # 本卦
    parts.append('<div class="gua-panel main">')
    parts.append(f'<div class="gua-panel-title">本卦</div>')
    parts.append(f'<div class="gua-panel-name">{ben_gua_name or ben_name_from_lines}</div>')
    parts.append(f'<div class="gua-panel-fu">{lines_to_fu_html(list(reversed(ben_lines)))}</div>')
    parts.append(f'<div class="gua-panel-trigram">{TRIGRAM_SYMBOL.get(ben_uname,"")}{TRIGRAM_SYMBOL.get(ben_lname,"")}</div>')
    parts.append('</div>')

    # 互卦
    parts.append('<div class="gua-panel main">')
    parts.append(f'<div class="gua-panel-title">互卦</div>')
    parts.append(f'<div class="gua-panel-name">{hu_gua["name"]}</div>')
    parts.append(f'<div class="gua-panel-fu">{lines_to_fu_html(list(reversed(hu_gua["lines"])))}</div>')
    parts.append(f'<div class="gua-panel-trigram">{TRIGRAM_SYMBOL.get(hu_gua["upper"],"")}{TRIGRAM_SYMBOL.get(hu_gua["lower"],"")}</div>')
    parts.append('</div>')

    # 变卦
    parts.append('<div class="gua-panel main">')
    parts.append(f'<div class="gua-panel-title">变卦</div>')
    parts.append(f'<div class="gua-panel-name">{computed_bian_name}</div>')
    parts.append(f'<div class="gua-panel-fu">{lines_to_fu_html(list(reversed(bian_lines)))}</div>')
    if has_dong:
        bl = get_trigram((bian_lines[0], bian_lines[1], bian_lines[2]))
        bu = get_trigram((bian_lines[3], bian_lines[4], bian_lines[5]))
        parts.append(f'<div class="gua-panel-trigram">{TRIGRAM_SYMBOL.get(bu,"")}{TRIGRAM_SYMBOL.get(bl,"")}</div>')
    parts.append('</div>')

    parts.append('</div>')  # end gua-panels

    # 切换按钮（一键同时展示错卦/综卦）
    parts.append('<div class="gua-toggle-bar">')
    parts.append(f'<button class="gua-toggle-btn" id="btn-cuozong" onclick="toggleCuoZong()">▸ 显示错卦 / 综卦</button>')
    parts.append('</div>')

    # 错卦+综卦面板（默认隐藏，并排展示）
    parts.append('<div class="gua-panels" id="cuozong-gua-panel" style="display:none;">')
    parts.append('<div class="gua-panel extra">')
    parts.append(f'<div class="gua-panel-title">错卦</div>')
    parts.append(f'<div class="gua-panel-name">{cuo_gua["name"]}</div>')
    parts.append(f'<div class="gua-panel-fu">{lines_to_fu_html(list(reversed(cuo_gua["lines"])))}</div>')
    parts.append(f'<div class="gua-panel-trigram">{TRIGRAM_SYMBOL.get(cuo_gua["upper"],"")}{TRIGRAM_SYMBOL.get(cuo_gua["lower"],"")}</div>')
    parts.append('</div>')
    parts.append('<div class="gua-panel extra">')
    parts.append(f'<div class="gua-panel-title">综卦</div>')
    parts.append(f'<div class="gua-panel-name">{zong_gua["name"]}</div>')
    parts.append(f'<div class="gua-panel-fu">{lines_to_fu_html(list(reversed(zong_gua["lines"])))}</div>')
    parts.append(f'<div class="gua-panel-trigram">{TRIGRAM_SYMBOL.get(zong_gua["upper"],"")}{TRIGRAM_SYMBOL.get(zong_gua["lower"],"")}</div>')
    parts.append('</div>')
    parts.append('</div>')

    return "\n".join(parts)


# ── HTML 模板 ────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>六爻卦象报告 — {ben_gua}变{bian_gua}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: "Noto Serif SC", "Source Han Serif SC", "SimSun", "宋体", serif;
  background: #f5f0e8; color: #3a3226; line-height: 1.8;
}}
.container {{ max-width: 860px; margin: 0 auto; padding: 40px 24px 60px; }}

/* 标题区 */
.report-header {{ text-align: center; padding: 32px 0 24px; border-bottom: 2px solid #8b7355; margin-bottom: 32px; }}
.report-header h1 {{ font-size: 28px; color: #5c3d2e; letter-spacing: 4px; margin-bottom: 8px; }}
.report-header .subtitle {{ font-size: 18px; color: #8b7355; }}
.report-header .question {{ font-size: 15px; color: #6b5a4e; margin-top: 12px; }}
.report-header .date {{ font-size: 13px; color: #9e8b7a; margin-top: 4px; }}

/* 信息条 */
.info-bar {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 32px; }}
.info-item {{ background: #fff; border: 1px solid #d4c5b2; border-radius: 6px; padding: 8px 16px; }}
.info-item .label {{ font-size: 12px; color: #9e8b7a; display: block; }}
.info-item .value {{ font-size: 16px; color: #5c3d2e; font-weight: bold; }}

/* ── 卦象面板 ── */
.gua-panels {{ display: flex; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; justify-content: center; }}
.gua-panel {{ 
  flex: 1; min-width: 130px; max-width: 180px;
  background: #fff; border: 1px solid #d4c5b2; border-radius: 8px;
  padding: 14px 10px; text-align: center;
  transition: box-shadow 0.2s;
}}
.gua-panel:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
.gua-panel.main {{ border-top: 3px solid #8b7355; }}
.gua-panel.extra {{ border-top: 3px solid #c49a3c; }}
.gua-panel-title {{ font-size: 12px; color: #9e8b7a; margin-bottom: 4px; letter-spacing: 1px; }}
.gua-panel-name {{ font-size: 15px; font-weight: bold; color: #5c3d2e; margin-bottom: 8px; letter-spacing: 1px; }}
.gua-panel-fu {{ display: flex; flex-direction: column; align-items: center; gap: 4px; margin-bottom: 10px; }}
.gua-line {{ 
  font-family: "SimSun", "KaiTi", "Microsoft YaHei", serif;
  font-size: 14px; letter-spacing: 0; line-height: 1.2;
}}
.fu-yang {{ color: #a07860; }}
.fu-yin {{ color: #6e8a90; }}
.gua-panel-trigram {{ font-size: 20px; color: #8b7355; letter-spacing: 2px; }}
.gua-panel-note {{ font-size: 12px; color: #9e8b7a; margin-top: 10px; line-height: 1.6; text-align: left; }}

/* 切换按钮 */
.gua-toggle-bar {{ display: flex; gap: 10px; justify-content: center; margin: 12px 0 32px; flex-wrap: wrap; }}
.gua-toggle-btn {{
  padding: 8px 20px; border: 1px solid #c49a3c; border-radius: 20px;
  background: #fff; color: #8b6914; cursor: pointer; font-size: 14px;
  font-family: inherit; transition: all 0.2s;
}}
.gua-toggle-btn:hover {{ background: #fdf2e0; border-color: #8b6914; }}
.gua-toggle-btn.active {{ background: #c49a3c; color: #fff; border-color: #c49a3c; }}

.badge {{ font-size: 11px; background: #fdf2e0; color: #8b6914; padding: 1px 8px; border-radius: 10px; margin-left: 6px; }}

/* 爻表 */
.yao-table {{ width: 100%; border-collapse: collapse; margin-bottom: 32px; font-size: 14px; }}
.yao-table th {{ background: #5c3d2e; color: #f5f0e8; padding: 10px 6px; white-space: nowrap; }}
.yao-table td {{ padding: 10px 6px; text-align: center; border-bottom: 1px solid #d4c5b2; vertical-align: middle; }}
.yao-table tr.dong {{ background: #fdf2e0; font-weight: bold; }}
.yao-table tr.dong td:first-child::before {{ content: "▶ "; color: #c49a3c; }}
.yao-table .gua-fu {{ font-family: "SimSun", "KaiTi", serif; font-size: 13px; letter-spacing: 0; color: #5c3d2e; white-space: nowrap; }}
.yao-table .gua-fu-grey {{ color: #b0a090; }}
/* 爻象横向对齐 */
.yao-lq {{ display: inline-block; width: 2.8em; }}
.yao-dz {{ display: inline-block; width: 1.8em; }}
.yao-gf {{ display: inline-block; width: 6em; text-align: center; font-family: "SimSun","KaiTi",serif; font-size: 14px; }}
.yao-sy {{ display: inline-block; width: 1.4em; text-align: center; font-weight: bold; }}
.yao-dm {{ display: inline-block; width: 1.2em; text-align: center; color: #c49a3c; font-weight: bold; }}
.yao-tag {{ display: inline-block; width: 3.4em; font-size: 12px; white-space: nowrap; }}
.yao-shou {{ white-space: nowrap; padding-right: 10px; }}
.yao-shou {{ white-space: nowrap; padding-right: 10px; }}
.yao-ben, .yao-bian {{ white-space: nowrap; }}
.bian-sub td {{ border-bottom: 1px dotted #d4c5b2; }}

/* 特殊标签徽章 */
.tag {{ display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; margin-left: 4px; font-weight: normal; }}
.tag-kong {{ background: #fce4ec; color: #c62828; border: 1px solid #ef9a9a; }}
.tag-po {{ background: #fce4ec; color: #c62828; border: 1px solid #ef9a9a; }}
.tag-an {{ background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }}
.tag-mu {{ background: #fff3e0; color: #e65100; border: 1px solid #ffcc80; }}

/* 五行色 */
.wx-金 {{ color: #c9a84c; }}
.wx-木 {{ color: #4c8b5c; }}
.wx-水 {{ color: #4c6b8b; }}
.wx-火 {{ color: #c94c4c; }}
.wx-土 {{ color: #8b7355; }}

/* 定性框 */
.verdict-box {{ padding: 20px; border-radius: 8px; margin-bottom: 32px; text-align: center; }}
.verdict-box.ji {{ background: #e8f5e9; border: 1px solid #81c784; }}
.verdict-box.xiong {{ background: #fbe9e7; border: 1px solid #e57373; }}
.verdict-box.ping {{ background: #fff8e1; border: 1px solid #ffb74d; }}
.verdict {{ font-size: 20px; font-weight: bold; }}

/* 通用标题 */
h2 {{ font-size: 20px; color: #5c3d2e; border-left: 4px solid #8b7355; padding-left: 12px; margin: 32px 0 16px; }}
h3 {{ font-size: 16px; color: #6b5a4e; margin: 16px 0 8px; }}

/* 动爻卡片 */
.dong-yao-card {{ background: #fdf2e0; border-left: 4px solid #c49a3c; padding: 16px; margin-bottom: 12px; border-radius: 0 6px 6px 0; }}

/* 生克链条可视化 */
.chain-box {{ background: #fff; border: 1px solid #d4c5b2; border-radius: 8px; padding: 20px; margin-bottom: 12px; font-family: "SimSun", "KaiTi", serif; font-size: 15px; text-align: center; line-height: 2.4; letter-spacing: 1px; }}
.chain-box .arrow {{ color: #c49a3c; font-weight: bold; }}
.chain-box .arrow-back {{ color: #c62828; font-weight: bold; }}

/* 趋势 + 建议双栏 */
.split-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
@media (max-width: 600px) {{ .split-grid {{ grid-template-columns: 1fr; }} }}
.trend-card {{ background: #f1f8e9; border: 1px solid #aed581; border-radius: 8px; padding: 20px; }}
.advice-card {{ background: #fff3e0; border: 1px solid #ffb74d; border-radius: 8px; padding: 20px; }}
.trend-card h3 {{ color: #558b2f; margin-top: 0; }}
.advice-card h3 {{ color: #e65100; margin-top: 0; }}
.trend-card p, .advice-card p {{ white-space: pre-wrap; }}

/* 综合断语 */
.final-verdict {{ background: #fff; border: 1px solid #d4c5b2; border-radius: 8px; padding: 24px; font-size: 15px; line-height: 2; white-space: pre-wrap; }}

/* 页脚 */
.report-footer {{ margin-top: 48px; padding-top: 24px; border-top: 1px solid #d4c5b2; text-align: center; font-size: 12px; color: #9e8b7a; }}
.verify-stamp {{ font-size: 14px; color: #5c8a5c; margin-bottom: 8px; }}
.disclaimer {{ margin-top: 12px; font-style: italic; }}

/* 旺衰标记 */
.ws-wang {{ color: #2e7d32; font-weight: bold; }}
.ws-zhong {{ color: #e65100; font-weight: bold; }}
.ws-xiu {{ color: #c62828; font-weight: bold; }}
.ws-kong {{ color: #9e9e9e; font-weight: bold; text-decoration: line-through; }}

@media print {{
  body {{ background: #fff; }}
  .container {{ max-width: 100%; padding: 20px; }}
  .yao-table th {{ background: #5c3d2e !important; color: #fff !important; -webkit-print-color-adjust: exact; }}
  .dong-yao-card, .chain-box, .trend-card, .advice-card, .gua-panel {{ -webkit-print-color-adjust: exact; }}
  #cuozong-gua-panel {{ display: flex !important; }}
  .gua-toggle-btn {{ display: none; }}
}}
</style>
<script>
function toggleCuoZong() {{
  var panel = document.getElementById('cuozong-gua-panel');
  var btn = document.getElementById('btn-cuozong');
  if (panel.style.display === 'none' || panel.style.display === '') {{
    panel.style.display = 'flex';
    btn.classList.add('active');
    btn.textContent = btn.textContent.replace('▸', '▾');
  }} else {{
    panel.style.display = 'none';
    btn.classList.remove('active');
    btn.textContent = btn.textContent.replace('▾', '▸');
  }}
}}
</script>
</head>
<body>
<div class="container">

<!-- 1. 标题区 -->
<header class="report-header">
  <h1>六爻卦象报告</h1>
  <p class="subtitle">本卦《{ben_gua}》　变卦《{bian_gua}》</p>
  <p class="question">所问：{question}</p>
  <p class="date">占卦时间：{date}　农历{lunar}</p>
</header>

<!-- 2. 卦象信息条 -->
<div class="info-bar">
  <div class="info-item"><span class="label">本卦</span><span class="value">{ben_gua}</span></div>
  <div class="info-item"><span class="label">变卦</span><span class="value">{bian_gua}</span></div>
  <div class="info-item"><span class="label">月建</span><span class="value">{yue_jian}</span></div>
  <div class="info-item"><span class="label">日辰</span><span class="value">{ri_chen}</span></div>
  <div class="info-item"><span class="label">旬空</span><span class="value">{kong_wang}</span></div>
</div>

<!-- 3. 六爻盘面（三栏本变互 + 错综切换） -->
<h2>六爻盘面</h2>
{gua_panels_html}

<!-- 3b. 详细爻表 -->
<h2>爻象详表</h2>
<table class="yao-table">
  <thead><tr><th>六神</th><th>本卦</th><th>变卦</th></tr></thead>
  <tbody>
{yao_rows}
  </tbody>
</table>

<!-- 3c. 特殊格局 -->
{patterns_block}

<!-- 3d. 神煞 -->
{shensha_block}

<!-- 4. 定性总览 -->
<h2>定性总览</h2>
<div class="verdict-box {verdict_class}">
  <p class="verdict">{qualitative}</p>
  <p class="verdict-detail">{basis}</p>
</div>

<!-- 5. 用神分析 -->
<h2>用神分析</h2>
{yong_shen_block}

<!-- 6. 动变解析 -->
<h2>动变解析</h2>
{dong_bian_block}

<!-- 6b. 生克链条 -->
{chain_block}

<!-- 7. 世应关系 -->
<h2>世应关系</h2>
{shi_ying_block}

<!-- 8. 六神兽提点 -->
<h2>六神兽提点</h2>
{liu_shou_block}

<!-- 9. 应期推断 -->
<h2>应期推断</h2>
{ying_qi_block}

<!-- 10. 综合断语 -->
<h2>综合断语</h2>
{final_block}

<!-- 11. 校验印记 -->
<footer class="report-footer">
  <p class="verify-stamp">{verify_result}</p>
  <p class="generate-time">报告生成时间：{generate_time}</p>
  <p class="disclaimer">此报告由 AI 六爻解卦 Skill 自动生成，供参考之用。六爻为传统决策辅助工具，不替代理性判断。</p>
</footer>

</div>
</body>
</html>"""


# ── 表格构建（保留原有逻辑）─────────────────────────────────

def wang_shuai_class(verdict: str) -> str:
    if "旺相" in verdict: return "ws-wang"
    if "中和" in verdict: return "ws-zhong"
    if "休囚" in verdict: return "ws-xiu"
    if "空破" in verdict: return "ws-kong"
    return "ws-zhong"


def verdict_css_class(qualitative: str) -> str:
    if any(w in qualitative for w in ("吉", "有利", "佳", "顺")): return "ji"
    if any(w in qualitative for w in ("凶", "不利", "败", "阻")): return "xiong"
    return "ping"


def tag_html(tag_name: str, label: str) -> str:
    cls_map = {"旬空": "kong", "月破": "po", "暗动": "an", "入墓": "mu"}
    cls = cls_map.get(tag_name, "kong")
    return f'<span class="tag tag-{cls}">{label}</span>'


def build_gua_fu_cell(ben: str, bian: str) -> str:
    b = GUA_FU.get(ben, "") if ben else ""
    if bian and bian != ben:
        c = GUA_FU.get(bian, "")
        return f'<td class="gua-fu">{b} → <span class="gua-fu-grey">{c}</span></td>'
    elif bian:
        c = GUA_FU.get(bian, "")
        return f'<td class="gua-fu">{b}<br><span class="gua-fu-grey">{c}</span></td>'
    else:
        return f'<td class="gua-fu">{b}</td>'


def build_yao_rows(yao_list: list) -> str:
    """构建横向六爻表行：六神兽 | 本卦爻象（含动标+世应）| 变卦爻象"""
    rows = []
    sorted_yao = sorted(yao_list, key=lambda y: y["pos"], reverse=True)

    for y in sorted_yao:
        pos = y["pos"]
        dong = y.get("dong", False)
        row_class = ' class="dong"' if dong else ""
        b_sy = y.get("shi_ying") or ""
        b_sy_disp = f' <b>{b_sy}</b>' if b_sy else ""

        # 特殊标签
        tags = y.get("special_tags", []) or []
        tag_s = "".join(tag_html(t, t) for t in tags)

        # 本卦爻象：对齐用 span + 爻位前缀
        b_gf = GUA_FU.get(y.get("ben_yin_yang", ""), "")
        ben_cell = (
            f'<span class="yao-lq">{y["liu_qin"]}</span>'
            f'<span class="yao-dz">{y["di_zhi"]}</span>'
            f'<span class="yao-gf">{b_gf}</span>'
            f'<span class="yao-sy">{b_sy}</span>'
            f'<span class="yao-dm">{"○" if dong else ""}</span>'
            f'<span class="yao-tag">{tag_s}</span>'
        )

        # 变卦爻象：对齐用 span
        bq = y.get("bian_liu_qin") or y["liu_qin"]
        bd = y.get("bian_di_zhi") or y["di_zhi"]
        b_bg = y.get("bian_yin_yang") or y.get("ben_yin_yang", "")
        b_gf_b = GUA_FU.get(b_bg, "")
        b_bsy = y.get("bian_shi_ying") or ""
        diff = (bq != y["liu_qin"] or bd != y["di_zhi"] or dong)
        gf_cls = 'gua-fu-grey' if diff else 'gua-fu'
        bian_cell = (
            f'<span class="yao-lq">{bq}</span>'
            f'<span class="yao-dz">{bd}</span>'
            f'<span class="yao-gf {gf_cls}">{b_gf_b}</span>'
            f'<span class="yao-sy">{b_bsy}</span>'
            f'<span class="yao-dm"></span>'
            f'<span class="yao-tag"></span>'
        )

        row_html = (
            f'<tr{row_class}>'
            f'<td class="yao-shou">{y["liu_shou"]}</td>'
            f'<td class="yao-ben">{ben_cell}</td>'
            f'<td class="yao-bian">{bian_cell}</td>'
            f'</tr>'
        )

        # 伏神行
        fu_shen = y.get("fu_shen")
        fu_row = ""
        if fu_shen:
            fu_row = (
                f'<tr class="fushen"><td colspan="3" style="text-align:left;font-size:12px;color:#9e8b7a;padding:2px 6px;">'
                f'　└ 伏神：{fu_shen["liu_qin"]}{fu_shen["di_zhi"]}（{fu_shen["wu_xing"]}）'
                f'</td></tr>'
            )

        rows.append(row_html + fu_row)

    return "\n".join(rows)


def build_yong_shen_block(step1: dict, step2: dict) -> str:
    ws_cls = wang_shuai_class(step2.get("verdict", ""))
    parts = [
        f'<p><strong>主用神：</strong>{step1["zhu_yong_shen"]}，{step2["yong_shen_location"]}</p>',
        f'<p><strong>辅助用神：</strong>{step1["fu_zhu_yong_shen"]}</p>',
        f'<p><strong>月建：</strong>{step2["yue_jian"]}　<strong>日辰：</strong>{step2["ri_chen"]}</p>',
        f'<p><strong>特殊状态：</strong>{step2["special"]}</p>',
        f'<p><strong>综合判定：</strong><span class="{ws_cls}">{step2["verdict"]}</span></p>',
    ]
    if step1.get("note"):
        parts.append(f'<p class="note">{step1["note"]}</p>')
    return "\n".join(parts)


def build_dong_bian_block(step3: dict) -> str:
    if not step3.get("dong_count"):
        return "<p>本卦为静卦，无动变路径。</p>"
    parts = []
    for d in step3.get("dong_yao", []):
        parts.append('<div class="dong-yao-card">')
        cn = {1:'初',2:'二',3:'三',4:'四',5:'五',6:'上'}.get(d["pos"], d["pos"])
        parts.append(f'<h3>{cn}爻 {d["liu_qin"]}{d["di_zhi"]} 发动</h3>')
        parts.append(f'<p><strong>化为：</strong>{d["bian_liu_qin"]}{d["bian_di_zhi"]}</p>')
        parts.append(f'<p><strong>角色：</strong>{d["role"]}</p>')
        parts.append(f'<p><strong>变化性质：</strong>{d["change_type"]}</p>')
        parts.append(f'<p><strong>影响：</strong>{d["effect"]}</p>')
        parts.append('</div>')
    parts.append(f'<p><strong>特殊格局：</strong>{step3["pattern"]}</p>')
    return "\n".join(parts)


def build_chain_block(step3: dict) -> str:
    if not step3.get("dong_count"):
        return ""
    chain = step3.get("chain", "")
    if not chain:
        return ""
    import re
    chain_v = re.sub(r'(→|‖|←|↗|↘|↖|↙)', r'<span class="arrow">\1</span>', chain)
    chain_v = re.sub(r'(回头克|回头生|克|生)', r'<span class="arrow-back">\1</span>', chain_v)
    return f'<h2>生克链条</h2>\n<div class="chain-box">{chain_v}</div>'


def build_shi_ying_block(step4: dict) -> str:
    return "\n".join([
        f'<p><strong>世爻：</strong>{step4["shi"]}</p>',
        f'<p><strong>应爻：</strong>{step4["ying"]}</p>',
        f'<p><strong>关系：</strong>{step4["relation"]}</p>',
        f'<p><strong>用神与世应：</strong>{step4["yong_shi_ying"]}</p>',
        f'<p><strong>刑害检测：</strong>{step4["xing_hai"]}</p>',
    ])


def build_liu_shou_block(step5: dict) -> str:
    return "\n".join([
        "<ul>",
        f'<li><strong>用神临{step5["yong_shen_shou"]}：</strong>{step5["yong_shen_shou_xiang"]}</li>',
        f'<li><strong>动爻临{step5["dong_yao_shou"]}：</strong>{step5["dong_yao_shou_xiang"]}</li>',
        "</ul>",
        '<p class="note">六神兽不单独断吉凶，仅供修饰参考。</p>',
    ])


def build_ying_qi_block(step6: dict) -> str:
    return "\n".join([
        f'<p><strong>匹配法则：</strong>{step6["matched_rule"]}</p>',
        f'<p><strong>综合窗口：</strong>{step6["window"]}</p>',
        f'<p><strong>依据：</strong>{step6["detail"]}</p>',
    ])


def build_final_block(step7: dict) -> str:
    trend = step7.get("trend", "")
    advice = step7.get("action_advice", "")
    if trend and advice:
        return (
            '<div class="split-grid">'
            f'<div class="trend-card"><h3>📈 趋势推演</h3><p>{trend}</p></div>'
            f'<div class="advice-card"><h3>💡 行动建议</h3><p>{advice}</p></div>'
            '</div>'
            f'<div class="final-verdict">{step7["final_verdict"]}</div>'
        )
    return f'<div class="final-verdict">{step7["final_verdict"]}</div>'


def generate(data: dict, output_path: str) -> str:
    meta = data["meta"]
    yao = data["yao"]
    steps = data["steps"]

    s1 = steps["step1"]
    s2 = steps["step2"]
    s3 = steps["step3"]
    s4 = steps["step4"]
    s5 = steps["step5"]
    s6 = steps["step6"]
    s7 = steps["step7"]
    s8 = steps["step8"]

    # 补全变卦阴阳爻：非动爻 = 本卦阴阳爻, 动爻 = 翻转
    ben_lines = ben_lines_from_yao(yao)
    bian_lines = compute_bian_lines(ben_lines, yao)
    sorted_yao = sorted(yao, key=lambda y: y["pos"])
    for i, y in enumerate(sorted_yao):
        # 写入内存中的 bian_yin_yang（不改原 JSON）
        y["_bian_yin_yang_computed"] = "阳" if bian_lines[i] else "阴"
        if y.get("dong", False) and not y.get("bian_yin_yang"):
            y["bian_yin_yang"] = y["_bian_yin_yang_computed"]

    # 确保非动爻也有 bian_yin_yang
    for i, y in enumerate(sorted_yao):
        if not y.get("bian_yin_yang"):
            y["bian_yin_yang"] = y.get("ben_yin_yang", "阳" if ben_lines[i] else "阴")

    # 补全变卦五行
    for y in sorted_yao:
        if y.get("dong") and y.get("bian_di_zhi") and not y.get("bian_wu_xing"):
            y["bian_wu_xing"] = di_zhi_to_wuxing(y["bian_di_zhi"])

    yao_rows_html = build_yao_rows(yao)

    qualitative = s7["qualitative"]
    vcls = verdict_css_class(qualitative)

    gua_panels_html = build_gua_panels(ben_lines, yao, meta.get("bian_gua") or "静卦", meta.get("ben_gua", ""))

    # 自动检测特殊格局
    patterns = detect_patterns(ben_lines, yao, meta)
    patterns_html = build_patterns_section(patterns)

    # 神煞渲染
    shensha_html = build_shensha_section(meta, yao)

    html = HTML_TEMPLATE.format(
        ben_gua=meta["ben_gua"],
        bian_gua=meta.get("bian_gua") or "静卦",
        question=meta["question"],
        date=meta["date"],
        lunar=meta.get("lunar", ""),
        yue_jian=meta["yue_jian"],
        ri_chen=meta["ri_chen"],
        kong_wang=meta["kong_wang"],
        gua_panels_html=gua_panels_html,
        yao_rows=yao_rows_html,
        verdict_class=vcls,
        qualitative=qualitative,
        basis=s7["basis"],
        yong_shen_block=build_yong_shen_block(s1, s2),
        dong_bian_block=build_dong_bian_block(s3),
        chain_block=build_chain_block(s3),
        shi_ying_block=build_shi_ying_block(s4),
        liu_shou_block=build_liu_shou_block(s5),
        ying_qi_block=build_ying_qi_block(s6),
        patterns_block=patterns_html,
        shensha_block=shensha_html,
        final_block=build_final_block(s7),
        verify_result=f"✅ {s8['final']}",
        generate_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def validate_json(data):
    """校验 liuyao-data.json 的 schema 完整性（替代 SKILL.md 里的 inline Python heredoc）

    统一校验入口，schema 演进只需改这一处。
    返回 (ok: bool, errors: list[str])。
    """
    errors = []

    # 顶层三大域
    for k in ("meta", "yao", "steps"):
        if k not in data:
            errors.append(f"缺少顶层字段: {k}")

    # 八步齐全
    if "steps" in data:
        s = data["steps"]
        for step in ("step1", "step2", "step3", "step4",
                      "step5", "step6", "step7", "step8"):
            if step not in s:
                errors.append(f"缺少 step: {step}")
        # step5 子字段（历史易漏点）
        if "step5" in s:
            for fld in ("yong_shen_shou", "yong_shen_shou_xiang",
                        "dong_yao_shou", "dong_yao_shou_xiang"):
                if fld not in s["step5"]:
                    errors.append(f"step5 缺少字段: {fld}")

    # yao 数组每爻必须有阴阳属性（v1.5.4 修复的易错点）
    if "yao" in data:
        for i, y in enumerate(data["yao"]):
            if "ben_yin_yang" not in y:
                errors.append(f"yao[{i}] 缺少 ben_yin_yang（卦象面板会全错）")

    return (len(errors) == 0, errors)


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="六爻卦象 HTML 报告生成器 v1.5")
    parser.add_argument("--input", "-i", required=True, help="输入 JSON 文件路径")
    parser.add_argument("--output", "-o", default="liuyao-report.html", help="输出 HTML 文件路径")
    parser.add_argument("--validate", action="store_true",
                        help="仅校验 JSON schema，不生成 HTML（用于第九步前置校验）")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ── 校验模式：仅检查 schema，不生成 HTML ──
    if args.validate:
        ok, errors = validate_json(data)
        if ok:
            print("✅ Schema OK")
            sys.exit(0)
        else:
            print(f"❌ Schema 校验失败（{len(errors)} 项）：", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            sys.exit(1)

    # 自动适配扁平格式（paipan.py 直出）-> 包装为 meta/yao/steps
    if "meta" not in data:
        if "ganzhi" in data:
            print("检测到 paipan.py 扁平格式，自动适配...", file=sys.stderr)
            raw_lines = data.get("lines", [])
            yao = []
            for rl in raw_lines:
                y = {
                    "pos": rl["pos"],
                    "liu_qin": rl["liu_qin"],
                    "di_zhi": rl["di_zhi"],
                    "wu_xing": rl["wu_xing"],
                    "shi_ying": rl.get("shi_ying") if rl.get("shi_ying") != "" else None,
                    "liu_shou": rl.get("liu_shou", ""),
                    "dong": rl.get("dong", False),
                    "bian_di_zhi": rl["bian_yao"]["di_zhi"] if rl.get("bian_yao") else None,
                    "bian_liu_qin": rl["bian_yao"]["liu_qin"] if rl.get("bian_yao") else None,
                    "special_tags": (
                        (["日空"] if "日空" in str(rl.get("kong_wang") or "") else [])
                        + (["月空"] if "月空" in str(rl.get("kong_wang") or "") else [])
                        + (["旬空"] if rl.get("kong_wang") and "日空" not in str(rl.get("kong_wang") or "") and "月空" not in str(rl.get("kong_wang") or "") else [])
                        + (["月破"] if rl.get("yue_po") else [])
                    ),
                }
                if rl.get("fu_shen"):
                    y["fu_shen"] = rl["fu_shen"]
                if rl.get("shensha"):
                    y["shensha"] = rl["shensha"]
                # ben_yin_yang：优先使用 paipan.py 直出字段（v1.5.1+），
                # 缺失时回退到 ygua 推算以兼容旧 JSON
                if rl.get("ben_yin_yang"):
                    y["ben_yin_yang"] = rl["ben_yin_yang"]
                else:
                    ygua = data.get("ygua", "")
                    if len(ygua) == 6:
                        idx = rl["pos"] - 1
                        y["ben_yin_yang"] = "阳" if ygua[idx] in ("1", "3") else "阴"
                yao.append(y)
            data = {
                "meta": {
                    "date": f'{data["date"]["year"]}-{data["date"]["month"]:02d}-{data["date"]["day"]:02d} {data["date"]["hour"]:02d}:{data["date"]["minute"]:02d}',
                    "lunar": data.get("lunar", ""),
                    "question": data["question"],
                    "intent": data["intent"],
                    "ben_gua": data["ben_gua"],
                    "bian_gua": data["bian_gua"],
                    "yue_jian": data["month_branch"],
                    "ri_chen": data["ri_chen"],
                    "kong_wang": (
                        (("日空" + "".join(data["kong_wang"])) if isinstance(data.get("kong_wang"), list) else data.get("kong_wang", ""))
                        + ((", 月空" + "".join(data["yue_xunkong"]))
                           if isinstance(data.get("yue_xunkong"), list) and data["yue_xunkong"] else "")
                    ),
                    "shensha": data.get("shensha", {}),
                },
                "yao": yao,
                "steps": {
                    "step1": {"intent": data["intent"], "zhu_yong_shen": "", "fu_zhu_yong_shen": "", "appearance": "", "note": "由 paipan.py 自动排盘，未做解卦分析"},
                    "step2": {"yong_shen_location": "", "yue_jian": "", "ri_chen": "", "special": "", "verdict": "未分析（仅盘面）"},
                    "step3": {"dong_count": sum(1 for y in yao if y["dong"]), "dong_yao": [], "chain": "", "pattern": ""},
                    "step4": {"shi": "", "ying": "", "relation": "", "yong_shi_ying": "", "xing_hai": ""},
                    "step5": {"yong_shen_shou": "", "yong_shen_shou_xiang": "", "dong_yao_shou": "", "dong_yao_shou_xiang": ""},
                    "step6": {"matched_rule": "", "window": "", "unit": "", "detail": ""},
                    "step7": {"qualitative": "盘面报告", "basis": "由 paipan.py 自动排盘生成", "final_verdict": "此报告仅含排盘信息，未做解卦分析。请通过六爻解卦 Skill 九步法进行完整分析。", "trend": "", "action_advice": ""},
                    "step8": {"integrity": "", "cross_check": "", "principles": "", "final": "仅盘面，未校验"},
                },
            }
        else:
            for key in ("meta", "yao", "steps"):
                if key not in data:
                    print(f"错误: JSON 缺少必需字段: {key}", file=sys.stderr)
                    sys.exit(1)

    output_path = generate(data, args.output)
    size = os.path.getsize(output_path)
    print(f"✅ HTML 报告已生成: {os.path.abspath(output_path)}")
    print(f"   文件大小: {size:,} bytes ({size / 1024:.1f} KB)")
    # 板块检查
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    sections = ["report-header", "info-bar", "gua-panels", "yao-table", "verdict-box",
                "用神分析", "动变解析", "世应关系", "六神兽提点", "应期推断"]
    found = sum(1 for s in sections if s in content)
    print(f"   板块完整性: {found}/{len(sections)}")


def detect_patterns(ben_lines, yao_list, meta):
    """自动检测卦中特殊格局：三会局/六合/六冲/伏吟/反吟"""
    patterns = []
    sorted_yao = sorted(yao_list, key=lambda y: y["pos"])
    
    # 收集所有地支
    all_dz = [y["di_zhi"] for y in sorted_yao]
    yue_jian = meta.get("yue_jian", "")
    ri_chen = meta.get("ri_chen", "")
    
    # 地支五行映射
    dz_wx = {"寅":"木","卯":"木","巳":"火","午":"火","申":"金","酉":"金","亥":"水","子":"水","辰":"土","戌":"土","丑":"土","未":"土"}
    
    # ── 三会局检测 ──
    sanhui = [
        ("东方木局", ["寅","卯","辰"]),
        ("南方火局", ["巳","午","未"]),
        ("西方金局", ["申","酉","戌"]),
        ("北方水局", ["亥","子","丑"]),
    ]
    for name, dz_set in sanhui:
        has_all = all(dz in all_dz for dz in dz_set)
        dong_yao = [y for y in sorted_yao if y.get("dong", False) and y["di_zhi"] in dz_set]
        kong_yao = [y for y in sorted_yao if y["di_zhi"] in dz_set and any(t in (y.get("special_tags") or []) for t in ["旬空"])]
        
        if has_all:
            if len(dong_yao) >= 3:
                patterns.append({"name": name, "level": "成局", "detail": f'卦中{"、".join(dz_set)}三支皆动，严格成局，力量凌驾单爻生克。', "css": "sanhui-cheng"})
            elif len(dong_yao) >= 1:
                missing_dong = [dz for dz in dz_set if dz not in [y["di_zhi"] for y in dong_yao]]
                patterns.append({"name": name, "level": "之势（动不足）", "detail": f'{"、".join(dz_set)}三支俱全，但仅{len(dong_yao)}爻发动，未达严格三会标准，降为三会之势。', "css": "sanhui-shi"})
            elif kong_yao:
                kong_dz = [y["di_zhi"] for y in kong_yao]
                patterns.append({"name": name, "level": "虚势（有支旬空）", "detail": f'{"、".join(dz_set)}三支齐聚，但{"、".join(kong_dz)}旬空，为虚势——三会之势已具其形，须待出空方能化为实质力量。', "css": "sanhui-xu"})
            else:
                patterns.append({"name": name, "level": "之势", "detail": f'{"、".join(dz_set)}三支俱全，静卦伏势，增强相关五行之力。', "css": "sanhui-shi"})
    
    # ── 六合检测 ──
    liuhe = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯","辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
    he_pairs = []
    for i, y1 in enumerate(sorted_yao):
        for y2 in sorted_yao[i+1:]:
            if liuhe.get(y1["di_zhi"]) == y2["di_zhi"]:
                he_pairs.append((y1, y2))
    if he_pairs:
        detail = "、".join(f'{y1["di_zhi"]}({y1["liu_qin"]})合{y2["di_zhi"]}({y2["liu_qin"]})' for y1, y2 in he_pairs)
        patterns.append({"name": "六合", "level": "", "detail": f'卦中存在六合关系：{detail}。合则绊住，事有牵缠。', "css": "liuhe"})
    
    # ── 六冲检测 ──
    liuchong = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅","卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
    chong_pairs = []
    for i, y1 in enumerate(sorted_yao):
        for y2 in sorted_yao[i+1:]:
            if liuchong.get(y1["di_zhi"]) == y2["di_zhi"]:
                chong_pairs.append((y1, y2))
    if chong_pairs:
        detail = "、".join(f'{y1["di_zhi"]}({y1["liu_qin"]})冲{y2["di_zhi"]}({y2["liu_qin"]})' for y1, y2 in chong_pairs)
        patterns.append({"name": "六冲", "level": "", "detail": f'卦中存在六冲关系：{detail}。冲则散而不聚，事多反复。', "css": "liuchong"})
    
    # ── 本卦六冲卦检测 ──
    chong_gua_pairs = {"乾":"坤","坤":"乾","震":"巽","巽":"震","坎":"离","离":"坎","艮":"兑","兑":"艮"}
    sgua = get_trigram((ben_lines[3], ben_lines[4], ben_lines[5]))
    xgua = get_trigram((ben_lines[0], ben_lines[1], ben_lines[2]))
    if chong_gua_pairs.get(sgua) == xgua:
        patterns.append({"name": "六冲卦", "level": "", "detail": f'本卦上{TRIGRAM_SYMBOL[sgua]}下{TRIGRAM_SYMBOL[xgua]}为六冲卦，事多散乱，变动频仍。', "css": "liuchong"})
    
    # ── 伏吟检测（动爻化同地支） ──
    fy_yao = [y for y in sorted_yao if y.get("dong") and y.get("bian_di_zhi") == y.get("di_zhi")]
    if fy_yao:
        detail = "、".join(f'{y["liu_qin"]}{y["di_zhi"]}化{y["di_zhi"]}' for y in fy_yao)
        patterns.append({"name": "伏吟", "level": "", "detail": f'动爻{detail}，伏吟之象——进退维谷，呻吟不快。', "css": "fuyin"})
    
    # ── 反吟检测（动变对冲冲位） ──
    fy_chong = [y for y in sorted_yao if y.get("dong") and y.get("bian_di_zhi") and liuchong.get(y.get("di_zhi","")) == y.get("bian_di_zhi")]
    if fy_chong:
        detail = "、".join(f'{y["liu_qin"]}{y["di_zhi"]}化{y["bian_di_zhi"]}' for y in fy_chong)
        patterns.append({"name": "反吟", "level": "", "detail": f'动爻{detail}，反吟之象——事有反复，去而复返。', "css": "fanyin"})
    
    return patterns


def build_patterns_section(patterns):
    """构建特殊格局 HTML 板块"""
    if not patterns:
        return "<p>本卦未检测到明显特殊格局。</p>"
    
    css_map = {
        "sanhui-cheng": "background:#e8f5e9;border-left:4px solid #2e7d32;",
        "sanhui-shi": "background:#fff8e1;border-left:4px solid #f9a825;",
        "sanhui-xu": "background:#f3e5f5;border-left:4px solid #7b1fa2;",
        "liuhe": "background:#e3f2fd;border-left:4px solid #1565c0;",
        "liuchong": "background:#fbe9e7;border-left:4px solid #c62828;",
        "fuyin": "background:#fff3e0;border-left:4px solid #e65100;",
        "fanyin": "background:#fce4ec;border-left:4px solid #ad1457;",
    }
    
    parts = ['<h2>特殊格局</h2>']
    for p in patterns:
        style = css_map.get(p["css"], "background:#fff;border-left:4px solid #9e9e9e;")
        level = f'<span class="badge">{p["level"]}</span>' if p["level"] else ""
        parts.append(f'<div style="{style}padding:14px 18px;margin-bottom:10px;border-radius:0 6px 6px 0;"><strong>{p["name"]}</strong>{level}<p style="margin-top:6px;">{p["detail"]}</p></div>')
    return "\n".join(parts)


def build_shensha_section(meta, yao_list):
    """构建神煞 HTML 板块"""
    top_shensha = meta.get("shensha")
    yao_shensha = any(y.get("shensha") for y in yao_list)
    
    if not top_shensha and not yao_shensha:
        return ""  # 无神煞数据，不展示此板块
    
    parts = ['<h2>神煞</h2>']
    
    # 顶层神煞
    if top_shensha:
        parts.append('<h3>全局神煞</h3>')
        items = []
        for name, dz_list in top_shensha.items():
            dz_str = "、".join(dz_list)
            items.append(f'<span style="display:inline-block;background:#f5f0e8;border:1px solid #d4c5b2;border-radius:4px;padding:4px 10px;margin:3px;"><strong>{name}</strong>：{dz_str}</span>')
        parts.append(''.join(items))
    
    # 每爻神煞
    if yao_shensha:
        parts.append('<h3 style="margin-top:16px;">各爻神煞</h3>')
        sorted_yao = sorted(yao_list, key=lambda y: y["pos"], reverse=True)
        for y in sorted_yao:
            ss = y.get("shensha", [])
            if not ss:
                continue
            wei_map = {6:"六爻",5:"五爻",4:"四爻",3:"三爻",2:"二爻",1:"初爻"}
            ss_str = "　".join(ss)
            parts.append(f'<p style="margin:4px 0;"><strong>{wei_map[y["pos"]]}</strong> {y["liu_qin"]}{y["di_zhi"]}：{ss_str}</p>')
    
    # 无数据
    if not top_shensha and not any(y.get("shensha") for y in yao_list):
        return ""
    
    return "\n".join(parts)
if __name__ == "__main__":
    main()


# ── 特殊格局自动检测 ────────────────────────────────────────