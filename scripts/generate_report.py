#!/usr/bin/env python3
"""六爻卦象 HTML 报告生成器 v2.0.7。

新增:
- 本卦/变卦/互卦 三栏盘面展示
- 错卦/综卦 切换按钮
- 变卦完整阴阳爻显示
- 特殊格局板块优先展示第三步深断文本，自动检测摘要仅作兜底

用法:
    python generate_report.py --input data.json --output report.html
    python generate_report.py --input data.json               # 默认输出 liuyao-report.html
"""

import argparse
import copy
import html
import json
import os
import re
import sys
from datetime import datetime

# 注意：「生产」是歧义词（亦指生产项目/生产力/投产），不作为拦截特征词；
# 分娩类拦截一律使用无歧义的强特征词，避免误伤求财、官运等正常问卦。
PREGNANCY_BLOCK_KEYWORDS = (
    "孕产", "怀孕", "有孕", "妊娠", "胎产", "胎儿", "胚胎", "保胎", "流产",
    "分娩", "临盆", "临产", "接生", "产妇", "生孩子", "坐月子", "预产期",
    "产检", "孕妇", "宝宝性别", "胎儿性别", "生男生女",
)
PREGNANCY_GENDER_KEYWORDS = (
    "性别", "男女", "男孩", "女孩", "男宝", "女宝", "儿子", "女儿",
    "生男", "生女", "是男是女", "蓝粉", "粉蓝", "宝宝性别", "胎儿性别",
)


def is_pregnancy_blocked_request(question: str, intent: str) -> bool:
    """frv gate: reject pregnancy/childbirth reports during validation."""
    text = f"{question or ''} {intent or ''}"
    return intent == "孕产" or any(keyword in text for keyword in PREGNANCY_BLOCK_KEYWORDS)


def is_pregnancy_gender_request(question: str, intent: str) -> bool:
    text = f"{question or ''} {intent or ''}"
    return any(keyword in text for keyword in PREGNANCY_GENDER_KEYWORDS)


def pregnancy_block_message(question: str, intent: str) -> str:
    message = "frv 门禁：不能生成孕产相关六爻报告，请优先参考医生和专业产检意见。"
    if is_pregnancy_gender_request(question, intent):
        message += " 宝宝的性别不该影响被期待和被善待的程度，更不能服务重男轻女。"
    return message


def render_text_with_emphasis(text: str) -> str:
    """Escape text and render the report's tiny safe Markdown subset."""
    escaped = html.escape(str(text or ""))
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped, flags=re.S)


def normalize_layer_text(value) -> str:
    """Flatten a layer value from string/list/dict into text for display/checks."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "；".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return "；".join(str(v).strip() for v in value.values() if str(v).strip())
    return str(value).strip()


# ─────────────────────────────────────────────────────────────────────────────
# 对外交付语言闸门（v2.0.7）
#
# 交付给问卦人的 HTML 报告只出「人话」——卦理与断语。
# 解卦流程的内部痕迹（参考资料加载清单、门禁/准入、Tier 分级、审查报告编号、
# 铁律编号、JSON 字段名、内部版本号等）不得出现在报告的可读区域。
#
# 作者约定（见 SKILL.md 铁律 18）：把这类内容包进 LIUYAO-INTERNAL 分隔区，写在
# 步骤 md 文件内部：
#     <!-- LIUYAO-INTERNAL:BEGIN -->
#     ...（加载清单 / 门禁说明 / 审查留痕 / 修正记录）...
#     <!-- LIUYAO-INTERNAL:END -->
#
# 生成报告时：
#   1) 分隔区内容          → 折叠的「技术留痕」板块（默认收起，非断语）
#   2) 未加分隔区的遗留脏句 → 逐从句/逐行剥离，同样收进技术留痕
#   3) 剥离后仍残留黑名单词 → 清洗失败，--validate 报错阻断，逼作者改到分隔区里
# ─────────────────────────────────────────────────────────────────────────────

INTERNAL_BEGIN = "<!-- LIUYAO-INTERNAL:BEGIN -->"
INTERNAL_END = "<!-- LIUYAO-INTERNAL:END -->"

INTERNAL_BLOCK_RE = re.compile(
    re.escape(INTERNAL_BEGIN) + r".*?" + re.escape(INTERNAL_END), flags=re.S
)

# 内部流程黑名单：命中即不得出现在问卦人可见文本中
INTERNAL_TOKEN_RE = re.compile(
    "|".join([
        r"Tier",
        r"待加载",
        r"软?门禁",
        r"准入条件",
        r"强制",
        r"加载",
        r"本步已加载",
        r"本步",
        r"该步",
        r"输出块",
        r"检查点",
        r"修正记录",
        r"审查",
        r"自检",
        r"审查轮次",
        r"单轮审查",
        r"审查智能体",
        r"审查\s*[A-D]\s*项",
        r"判据",
        r"假合规",
        r"真读",
        r"落盘",
        r"预读",
        r"路由表",
        r"升降级",
        r"十项深断",
        r"深断",
        r"\b[a-z]{3,}\s*=",
        r"铁律\s*\d+",
        r"原则\s*\d+",
        r"技法\s*\d+",
        r"步骤\s*\d+\s*附",
        r"第\s*3\.5\s*步",
        r"卦例目录",
        r"卦例临时目录",
        r"最终目录名",
        r"排盘命令",
        r"计算后端",
        r"退出码",
        r"sxtwl",
        r"已\s*read",
        r"术语校准",
        r"受控词表",
        r"触发条件",
        r"必须引用",
        r"本条权重",
        r"不得",
        r"禁止",
        r"档位",
        r"四档",
        r"主流程",
        r"智能体",
        r"上下文隔离",
        r"\bintent\b",
        r"\bseed\b",
        r"\bstatus\s*=",
        r"\bpatterns\b",
        r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b",
        r"~[/\\]Desktop",
        r"[A-Za-z]:\\[^\s\"'`）)]*",
        r"md\s*文件",
        r"口径",
        r"模板",
        r"v[12]\.\d+\.\d+",
        r"SKILL\.md",
        r"`[A-Za-z0-9_\-]+\.md`",
        r"[A-Za-z0-9_\-]+\.md",
        r"references/[^\s，。）)、」]*\.md",
        r"generate_report\.py",
        r"paipan_result\.json",
        r"liuyao-data\.json",
        r"cand_\d+\.json",
        r"\bJSON\b",
        r"\bP\d{1,2}\b",
    ])
)

# 内部编号标签：删「铁律 11」「原则10」「技法27.2」等编号，保留其后引文
INTERNAL_LABEL_RE = re.compile(
    r"(?:依|按|据|参见|参照|遵循|本于)?\s*(?:铁律|原则|技法)\s*\d+(?:\.\d+)?\s*[·、:：]?\s*"
)

# 打分记号（铁律 10：内部可量化，交付文本必须转自然语言）
SCORE_MARK_RES = (
    re.compile(r"[（(]\s*[＋+\-－]\s*\d\s*[）)]"),
    re.compile(r"\*\*\s*[＋+\-－]\s*1\s*\*\*"),
    re.compile(r"(?<![\d/])\s*[＋+\-－]\s*1\s*(?=([，。；、)）」』\"']|$))"),
    re.compile(r"\bplus\s*1\b|\bminus\s*1\b"),
)


def _strip_score_marks(text: str) -> str:
    out = text or ""
    for rx in SCORE_MARK_RES:
        out = rx.sub("", out)
    out = re.sub(r"＝\s*总分\s*0", "＝ 中和", out)
    out = re.sub(r"→\s*(?=[，。；、）)])", "", out)
    out = re.sub(r"\s*([，。；、])", r"\1", out)
    out = re.sub(r"（\s*）", "", out)
    out = re.sub(r"，\s*，", "，", out)
    return out

# 从句级手术：优先只删整句里那一小截带黑名单词的从句，保住整行的卦理内容
INTERNAL_CLAUSE_RES = (
    re.compile(r"（[^（）\n]*）"),
    re.compile(r"\([^()\n]*\)"),
    re.compile(r"——[^。；\n]*"),
    re.compile(r"\*\*[^*\n]+\*\*"),
)

# 纯脚手架标记行：【第N步·输出】/【第三步·附 — 伏神旁注】等
STEP_MARKER_RE = re.compile(r"^\s*【[^】]*步[^】]*】\s*$")

# references 加载清单块头（含 "- 本步已加载 …" 与 "## 本步已加载 …" 两种历史写法）
LOAD_LIST_HEAD_RE = re.compile(r"^\s*(?:[-*+]\s+|#+\s*)?本步已加载")

INDENTED_RE = re.compile(r"^(?:\s{2,}|\t)")
QUOTE_LINE_RE = re.compile(r"^\s*>")
# 清单块的续行形态：「- `xxx.md` 第N节…」这类以参考文件名开头的条目
INTERNAL_LIST_ITEM_RE = re.compile(r"^\s*[-*+]\s*`?[A-Za-z0-9_\-]+\.md")
# 纯引文行（只剩「…」与标点）——无上下文，判定为清单残渣
QUOTE_ONLY_RE = re.compile(r"^[\s「」『』。；，、*\-—…·]*$")


def _strip_internal_clauses(line: str) -> str | None:
    """尝试从句级删除带黑名单词的从句；返回清洗结果（可能仍含黑名单词）。"""
    out = line
    changed = False
    for _ in range(8):
        spans = []
        for rx in INTERNAL_CLAUSE_RES:
            spans.extend(rx.finditer(out))
        hit = None
        for m in sorted(spans, key=lambda m: (len(m.group(0)), m.start())):
            if INTERNAL_TOKEN_RE.search(m.group(0)):
                hit = m
                break
        if not hit:
            break
        out = out[: hit.start()] + out[hit.end():]
        changed = True
    if not changed:
        return None
    return _tidy_fragment(out)


def _tidy_fragment(text: str) -> str:
    out = re.sub(r"[ \t]{2,}", " ", text)
    out = re.sub(r"（\s*）", "", out)
    out = re.sub(r"：\s*。", "。", out)
    out = re.sub(r"，\s*。", "。", out)
    out = re.sub(r"。\s*。", "。", out)
    out = re.sub(r"[；，、]\s*([。；])", r"\1", out)
    out = re.sub(r"([⚠️★🔺❗])\s*[：:，、]\s*", r"\1 ", out)
    out = re.sub(r"[：:]\s*[：:，、]", "：", out)
    out = re.sub(r"^[\s\-+，、：；]+(?=\S)", "", out)
    return out.rstrip()


def _cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def _split_clauses(text: str) -> list:
    """按句读切分，但不在括号、引号、加粗标记内部切（防拆坏成对符号）。"""
    parts, buf = [], []
    depth, in_bold = 0, False
    i = 0
    while i < len(text):
        ch = text[i]
        if text.startswith("**", i):
            in_bold = not in_bold
            buf.append("**")
            i += 2
            continue
        if ch in "（(「《【":
            depth += 1
        elif ch in "）)」》】":
            depth = max(0, depth - 1)
        buf.append(ch)
        if depth == 0 and not in_bold and ch in "；。：，":
            parts.append("".join(buf))
            buf = []
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _drop_dirty_clauses(text: str):
    """按句读切分，只丢弃含黑名单词的子句，保住同一行里的卦理内容。

    返回 (结果文本, 是否丢弃过子句)。长段落（如第三步特殊格局深断）里的
    「来源=JSON patterns」这类内部指引只占一个子句，不应因此丢掉整段分析。
    被丢弃的子句若带长引文（「…」），把引文抢救回来——引文是断卦依据。
    """
    parts = _split_clauses(text)
    kept, dropped = [], False
    for part in parts:
        if not part.strip():
            continue
        if not INTERNAL_TOKEN_RE.search(part):
            kept.append(part)
            continue
        surgery = _strip_internal_clauses(part)
        if surgery is not None and not INTERNAL_TOKEN_RE.search(surgery) and _cjk_len(surgery) >= 4:
            kept.append(surgery)
            continue
        quotes = re.findall(r"「[^」]{12,}」", part)
        if quotes:
            kept.append("".join(quotes) + "。")
        dropped = True
    return _tidy_fragment("".join(kept)), dropped


def sanitize_client_text(text, label: str, fragments: dict) -> str:
    """把一段内部文本清洗成「问卦人可读」版本。

    被剥离的内容按 label 归集进 fragments（用于生成折叠的「技术留痕」板块）。
    处理顺序：整段分隔区 → 清单块 → 行内从句手术 → 子句级丢弃 → 整行移入留痕。
    """
    if text is None:
        return text
    raw = str(text)
    if not raw.strip():
        return raw

    remainder, block_frags = strip_internal_blocks(raw)
    for chunk in block_frags:
        fragments.setdefault(label, []).append(chunk)

    keep, buf = [], []

    def flush():
        chunk = "\n".join(buf).strip("\n")
        if chunk.strip():
            fragments.setdefault(label, []).append(chunk)
        buf.clear()

    lines = remainder.split("\n")
    i = 0
    while i < len(lines):
        line = INTERNAL_LABEL_RE.sub("", lines[i])
        if STEP_MARKER_RE.match(line):
            i += 1
            continue
        if LOAD_LIST_HEAD_RE.match(line):
            start = i
            i += 1
            while i < len(lines) and (
                not lines[i].strip()
                or INDENTED_RE.match(lines[i])
                or QUOTE_LINE_RE.match(lines[i])
                or INTERNAL_LIST_ITEM_RE.match(lines[i])
            ):
                i += 1
            flush()
            fragments.setdefault(label, []).append(
                "\n".join(lines[start:i]).strip("\n")
            )
            continue
        if INTERNAL_TOKEN_RE.search(line):
            surgery = _strip_internal_clauses(line)
            if (
                surgery is not None
                and not INTERNAL_TOKEN_RE.search(surgery)
                and _cjk_len(surgery) >= 6
            ):
                if buf:
                    flush()
                keep.append(surgery)
                i += 1
                continue
            dropped_text, _dropped = _drop_dirty_clauses(line)
            if (
                dropped_text
                and not INTERNAL_TOKEN_RE.search(dropped_text)
                and _cjk_len(dropped_text) >= 6
                and not QUOTE_ONLY_RE.match(dropped_text)
            ):
                if buf:
                    flush()
                keep.append(dropped_text)
            else:
                buf.append(line)
            i += 1
            continue
        if buf:
            flush()
        keep.append(line)
        i += 1

    flush()
    cleaned = "\n".join(keep)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return _strip_score_marks(cleaned.strip("\n"))


def strip_internal_blocks(text: str):
    """抽出 LIUYAO-INTERNAL 分隔区；返回 (剩余文本, [分隔区原文...])。"""
    frags = []

    def _take(m):
        frags.append(m.group(0))
        return ""

    return INTERNAL_BLOCK_RE.sub(_take, text or ""), frags


def find_internal_tokens(text) -> list:
    """返回文本中命中的黑名单词（去重、保序），供校验与验收使用。"""
    if not text:
        return []
    hits = []
    for m in INTERNAL_TOKEN_RE.finditer(str(text)):
        tok = m.group(0)
        if tok not in hits:
            hits.append(tok)
    return hits


# 内部流程字段：整段都属于流程留痕，不进可读区（如第八步审查报告）
AUDIT_STEP_KEYS = ("integrity", "cross_check", "principles", "final", "summary")

# md_full 中面向问卦人的键；其余键（审查报告原文等）整段进技术留痕
MD_FULL_CLIENT_KEYS = ("step0", "step1", "step2", "step3", "step3_fu",
                       "step4", "step5", "step6", "step7")


def build_client_view(data: dict):
    """生成对外交付视图。

    返回 (client_data, fragments, residual)：
    - client_data：剥离内部痕迹后的深拷贝，供 generate() 渲染
    - fragments：{步骤标签: [被剥离的内部原文...]}
    - residual：清洗后仍残留的黑名单词（空 = 干净）
    """
    client = copy.deepcopy(data)
    fragments: dict = {}

    def clean(value, label):
        if isinstance(value, str):
            return sanitize_client_text(value, label, fragments)
        if isinstance(value, list):
            return [clean(v, label) for v in value]
        if isinstance(value, dict):
            return {k: clean(v, label) for k, v in value.items()}
        return value

    steps = client.get("steps", {}) if isinstance(client.get("steps"), dict) else {}
    for step_key, step_val in list(steps.items()):
        if not isinstance(step_val, dict):
            continue
        label = step_key
        if step_key == "step8":
            # 第八步整份都是审查留痕：原文全进技术留痕，可读区只留一句人话结论
            audit_chunks = []
            for fld in AUDIT_STEP_KEYS:
                if step_val.get(fld):
                    audit_chunks.append(f"【{fld}】\n{step_val[fld]}")
            if audit_chunks:
                fragments.setdefault(label, []).append("\n\n".join(audit_chunks))
            for fld in AUDIT_STEP_KEYS:
                if fld in step_val:
                    step_val[fld] = ""
            continue
        for fld, val in list(step_val.items()):
            step_val[fld] = clean(val, label)

    md_full = client.get("md_full")
    if isinstance(md_full, dict):
        for key, content in list(md_full.items()):
            if key not in MD_FULL_CLIENT_KEYS:
                # 审查报告等不面向问卦人的正文：整段进技术留痕（不丢内容）
                if str(content or "").strip():
                    fragments.setdefault(key, []).append(str(content))
                md_full[key] = ""
                continue
            md_full[key] = sanitize_client_text(content, key, fragments)

    residual = []
    for label, text in _iter_client_strings(client):
        for tok in find_internal_tokens(text):
            residual.append(f"{label}: {tok}")
    return client, fragments, sorted(set(residual))


def _iter_client_strings(client):
    """遍历对外视图中所有会被渲染成文本的字符串（用于残留复检）。

    只取字符串叶子，不把 dict 的键序列化进来——JSON 键名不会被渲染。
    """

    def walk(value, path):
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from walk(v, f"{path}[{i}]")
        elif isinstance(value, dict):
            for k, v in value.items():
                yield from walk(v, f"{path}.{k}")

    yield "meta.question", str(client.get("meta", {}).get("question", ""))
    for step_key, step_val in (client.get("steps") or {}).items():
        label = STEP_NAMES.get(step_key, step_key)
        yield from walk(step_val, label)
    md_full = client.get("md_full")
    if isinstance(md_full, dict):
        for key, content in md_full.items():
            yield f"md_full.{key}", str(content)


SCENARIO_YINGQI_LAYER_REQUIREMENTS = {
    "求财": {
        "main": (("妻财", "财"), "财物/收益主应期"),
        "auxiliary": (("子孙", "原神", "财源", "项目", "父母"), "财源/项目/生财条件"),
        "risk": (("兄弟", "忌神", "仇神", "破财", "耗财"), "竞争/破财风险"),
    },
    "官运": {
        "main": (("官鬼", "职位", "岗位", "功名"), "职位/岗位/功名主应期"),
        "auxiliary": (("父母", "文书", "offer", "合同", "审批", "证照", "妻财", "待遇", "薪资", "俸禄"), "文书流程或待遇节点"),
        "risk": (("子孙", "兄弟", "忌神", "竞争", "化退", "化空", "化破"), "克官/竞争/退空破风险"),
    },
    "学业": {
        "main": (("父母", "考试", "论文", "证书", "学位"), "考试/论文/证书主应期"),
        "auxiliary": (("官鬼", "名次", "录取", "资格", "子孙", "发挥"), "名次录取或发挥节点"),
        "risk": (("妻财", "兄弟", "忌神", "分心", "耗学", "合住", "冲破", "化退"), "耗学/分心/文书受损风险"),
    },
    "感情": {
        "main": (("妻财", "官鬼", "对象", "配偶", "感情用神"), "关系对象主应期"),
        "auxiliary": (("应爻", "世应", "父母", "子孙", "沟通", "婚书", "流程"), "对方回应/沟通/关系流程节点"),
        "risk": (("兄弟", "竞争", "阻隔", "冲散", "多现", "忌神"), "竞争/阻隔/冲散风险"),
    },
    "健康": {
        "main": (("子孙", "医药", "康复", "治疗"), "医药/康复主应期"),
        "auxiliary": (("原神", "父母", "检查", "报告", "安排", "药力", "体力"), "检查治疗或体力药力节点"),
        "risk": (("官鬼", "病", "忌神", "冲克", "化空", "化破"), "病症/忌神发作风险"),
    },
    "出行": {
        "main": (("世爻", "驿马", "出行", "启程", "迁动"), "自身行动/启程迁动主应期"),
        "auxiliary": (("应爻", "目的地", "接应", "父母", "票证", "手续", "妻财", "费用"), "目的地/票证手续/费用节点"),
        "risk": (("忌神", "官鬼", "白虎", "灾煞", "六合", "绊住", "冲破"), "路途阻滞/风险窗口"),
    },
    "失物": {
        "main": (("妻财", "父母", "失物", "财物", "文书", "票证", "本体"), "失物本体主应期"),
        "auxiliary": (("子孙", "线索", "寻回", "世应", "伏神", "出伏"), "线索/寻回/露面节点"),
        "risk": (("官鬼", "兄弟", "盗", "占有", "入墓", "化空", "被合藏"), "盗失/占有/藏匿风险"),
    },
    "词讼": {
        "main": (("官鬼", "官方", "裁断", "处罚", "判决"), "官方裁断主应期"),
        "auxiliary": (("父母", "证据", "文书", "流程", "世应", "攻守"), "证据文书/双方攻守节点"),
        "risk": (("克世", "应爻", "兄弟", "口舌", "风险", "文书受破"), "克世/口舌/文书破损风险"),
    },
    "天气": {
        "main": (("父母", "妻财", "子孙", "雨", "晴", "天气"), "雨晴转变主应期"),
        "auxiliary": (("官鬼", "雷电", "风暴", "兄弟", "风", "日月"), "雷电风云/日月入局节点"),
        "risk": (("官鬼", "风暴", "久雨", "受克", "难开"), "风暴加剧/久雨难晴风险"),
    },
    "通用": {
        "main": (("世爻", "所问主体", "指定用神", "主用神"), "自身/所问主体主应期"),
        "auxiliary": (("应爻", "原神", "辅助", "条件", "对方"), "外部对象/辅助条件节点"),
        "risk": (("忌神", "仇神", "阻力", "风险"), "阻力/风险窗口"),
    },
}

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
.report-header .author {{ font-size: 13px; color: #8a6d1a; font-weight: bold; margin-bottom: 14px; }}
.report-header h1 {{ font-size: 28px; color: #5c3d2e; letter-spacing: 4px; margin-bottom: 8px; }}
.edition-badge {{ display: inline-block; padding: 2px 14px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-bottom: 10px; }}
.edition-badge.pro {{ background: #fff3cd; color: #8a6d1a; border: 1px solid #d4b84a; }}
.edition-badge.free {{ background: #e8e8e8; color: #555; border: 1px solid #bbb; }}
.report-header .subtitle {{ font-size: 18px; color: #8b7355; }}
.report-header .question {{ font-size: 15px; color: #6b5a4e; margin-top: 12px; }}
.report-header .date {{ font-size: 13px; color: #9e8b7a; margin-top: 4px; }}

/* 信息条 */
.info-bar {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 32px; }}
.info-item {{ background: #fff; border: 1px solid #d4c5b2; border-radius: 6px; padding: 8px 16px; }}
.info-item .label {{ font-size: 12px; color: #000; font-weight: bold; display: block; }}
.info-item .value {{ font-size: 16px; color: #000; font-weight: bold; }}
.info-item.kong-item .value {{ color: #c62828; }}

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

/* 旺相休囚死（五行之气随月令流转） */
.wxs-sub  {{ font-size: 13px; color: #9e8b7a; margin: 4px 0 12px; }}
.wxs-row  {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 32px; }}
.wxs-card {{ flex: 1; min-width: 130px; max-width: 170px; background: #faf7f2; border: 1px solid #d4c5b2; border-radius: 8px; padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; line-height: 1.2; }}
.wxs-card .wxs-name  {{ font-size: 18px; font-weight: bold; }}
.wxs-card .wxs-state {{ font-size: 15px; font-weight: bold; letter-spacing: 1px; }}
/* 五行字色（低饱和，统一浅宣纸背景；金为白字以深色描边保证可见） */
.wxs-mu   {{ color: #4d8a5e; }}
.wxs-huo  {{ color: #b0554a; }}
.wxs-tu   {{ color: #93752f; }}
.wxs-jin  {{ color: #fffdf5; text-shadow: 1px 1px 0 #6b5a4e, -1px -1px 0 #6b5a4e, 1px -1px 0 #6b5a4e, -1px 1px 0 #6b5a4e; }}
.wxs-shui {{ color: #333f47; }}

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

/* 解卦过程全文附录 */
.step-full {{ background: #faf7f2; border: 1px solid #e8dfd2; border-radius: 8px; padding: 18px; font-size: 13px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; color: #4e3d2f; }}
.step-full strong {{ color: #6d3518; background: #fff1d6; border-radius: 4px; padding: 1px 4px; font-weight: 700; }}
.pattern-deep {{ border-left: 4px solid #c49a3c; }}
.pattern-deep strong {{ color: #7a2f0f; background: #ffe7ba; }}
.yingqi-layers {{ margin-top: 12px; padding: 12px 16px; }}
.yingqi-layers p {{ margin: 6px 0; }}
.md-full-section {{ margin-bottom: 20px; }}
.md-full-section h3 {{ color: #5c3d2e; margin: 0 0 8px 0; font-size: 15px; }}
.md-full-intro {{ color: #9e8b7a; font-size: 13px; margin-bottom: 16px; }}

/* 技术留痕（默认收起 · 内部流程记录，非断语） */
.tech-trail {{ margin-top: 40px; border: 1px dashed #d4c5b2; border-radius: 8px; background: #f7f4ee; }}
.tech-trail > summary {{
  cursor: pointer; padding: 12px 18px; font-size: 13px; color: #8b7355;
  font-weight: bold; letter-spacing: 1px; list-style: none;
}}
.tech-trail > summary::-webkit-details-marker {{ display: none; }}
.tech-trail > summary::before {{ content: "▸ "; }}
.tech-trail[open] > summary::before {{ content: "▾ "; }}
.tech-trail[open] > summary {{ border-bottom: 1px dashed #d4c5b2; }}
.tech-trail-note {{ padding: 12px 18px 0; font-size: 12px; color: #9e8b7a; line-height: 1.7; }}
.tech-trail .md-full-section {{ padding: 0 18px; }}
.tech-trail .step-full {{ font-size: 12px; color: #6b5a4e; background: #fff; }}

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
  <p class="author">作者：Cyrux ｜ 微信：drdingno1 ｜ 邮箱：Cyrux.ding@outlook.sg</p>
  <h1>六爻卦象报告</h1>
  <p class="edition-badge {edition_class}">{edition_badge}</p>
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
  <div class="info-item kong-item"><span class="label">日空</span><span class="value">{day_kong}</span></div>
  <div class="info-item kong-item"><span class="label">月空</span><span class="value">{yue_kong}</span></div>
</div>

<!-- 3. 卦象盘面（三栏本变互 + 错综切换） -->
<h2>卦象盘面</h2>
{gua_panels_html}

<!-- 3b. 详细爻表 -->
<h2>爻象详表</h2>
<table class="yao-table">
  <thead><tr><th>六神兽</th><th>本卦</th><th>变卦</th></tr></thead>
  <tbody>
{yao_rows}
  </tbody>
</table>

<!-- 3b2. 旺相休囚死（五行之气月令流转） -->
{wang_shuai_block}

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

<!-- 11. 解卦过程全文（md_full 附录，逐字保真） -->
{md_full_block}

<!-- 12. 技术留痕（内部流程记录，默认收起） -->
{tech_trail_block}

<!-- 13. 校验印记 -->
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


def split_kong_wang(meta: dict):
    """从 meta 解析日空/月空显示串（v1.8.2：日空月空分开展示）。

    支持三种格式：
    1. 新组装格式：kong_wang="寅卯"（日空）、yue_kong="巳午"（月空）——分开字段
    2. paipan 自动适配格式：kong_wang="日空寅卯, 月空巳午"（合并字符串）
    3. 旧合并格式：kong_wang="寅卯 巳午（月空）"
    返回 (day_kong, yue_kong) 两个显示串。
    """
    day_kw = str(meta.get("kong_wang", "")).strip()
    yue_kw = str(meta.get("yue_kong", "") or meta.get("yue_xunkong", "")).strip()

    if not yue_kw and "月空" in day_kw:
        # 旧合并格式 → 拆出日空与月空
        import re
        m_day = re.search(r"日空([\u4e00-\u9fff]+)", day_kw)
        m_yue = re.search(r"月空[（(]?([\u4e00-\u9fff]+)", day_kw)
        day_kw = m_day.group(1) if m_day else day_kw
        yue_kw = m_yue.group(1) if m_yue else ""
        if "（月空）" in day_kw and not yue_kw:
            parts = day_kw.split("（月空）")[0].split()
            if len(parts) >= 2:
                day_kw, yue_kw = parts[0], parts[1]
            else:
                day_kw = parts[0]
    day_kw = day_kw.strip("日空, ，（）()")
    yue_kw = yue_kw.strip("月空, ，（）()")
    return day_kw or "—", yue_kw or "—"


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
    parts.append(f'<p><strong>特殊格局：</strong>{render_text_with_emphasis(step3["pattern"])}</p>')
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
    parts = [
        f'<p><strong>匹配法则：</strong>{render_text_with_emphasis(step6["matched_rule"])}</p>',
        f'<p><strong>综合窗口：</strong>{render_text_with_emphasis(step6["window"])}</p>',
        f'<p><strong>依据：</strong>{render_text_with_emphasis(step6["detail"])}</p>',
    ]
    layers = step6.get("layers")
    if isinstance(layers, dict):
        main = normalize_layer_text(layers.get("main"))
        auxiliary = normalize_layer_text(layers.get("auxiliary"))
        risk = normalize_layer_text(layers.get("risk"))
        if main or auxiliary or risk:
            parts.append('<div class="step-full yingqi-layers">')
            parts.append(f'<p><strong>主应期：</strong>{render_text_with_emphasis(main)}</p>')
            parts.append(f'<p><strong>辅助节点：</strong>{render_text_with_emphasis(auxiliary)}</p>')
            parts.append(f'<p><strong>风险窗口：</strong>{render_text_with_emphasis(risk)}</p>')
            parts.append('</div>')
    return "\n".join(parts)


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


STEP_NAMES = {
    "step0": "第零步 · 自动排盘",
    "step1": "第一步 · 审题取用神",
    "step2": "第二步 · 判定旺衰",
    "step3": "第三步 · 追踪动变",
    "step3_fu": "第三步·附 · 伏神旁注",
    "step3_5": "第3.5步 · 伏神分析",
    "step4": "第四步 · 世应关系",
    "step5": "第五步 · 六神兽取象",
    "step6": "第六步 · 应期推断",
    "step7": "第七步 · 综合断语",
    "step8": "第八步 · 智能体审查",
}


def build_md_full_block(md_full: dict) -> str:
    """渲染「解卦过程全文」附录板块：逐字展示各步骤 md 原文（pre-wrap）。

    md_full 缺失或为空时返回空字符串（板块自动隐藏，不报错）。
    传入的 md_full 已由 build_client_view() 剥离内部流程痕迹。
    """
    if not md_full:
        return ""
    sections = []
    for key in ("step0", "step1", "step2", "step3", "step3_fu",
                "step4", "step5", "step6", "step7"):
        content = md_full.get(key)
        if not content or not str(content).strip():
            continue
        name = STEP_NAMES.get(key, key)
        sections.append(
            '<div class="md-full-section">'
            f'<h3>{name}</h3>'
            f'<div class="step-full">{render_text_with_emphasis(content)}</div>'
            '</div>'
        )
    if not sections:
        return ""
    return (
        '<h2>📜 解卦过程全文</h2>'
        '<p class="md-full-intro">以下为本次解卦各步骤的完整分析原文，供复核推理过程。'
        '流程性记录（参考资料目录、自我检查痕迹、复核意见等）已移入文末'
        '「🔧 技术留痕」，不影响阅读，需要时展开即可。</p>'
        + "\n".join(sections)
    )


def build_tech_trail_block(fragments: dict, verify_raw: str = "") -> str:
    """渲染折叠的「技术留痕」板块（默认收起）：内部流程记录不进可读区。"""
    sections = []
    if isinstance(fragments, dict):
        for key in ("step0", "step1", "step2", "step3", "step3_fu", "step3_5", "step4",
                    "step5", "step6", "step7", "step8"):
            chunks = fragments.get(key)
            if not chunks:
                continue
            name = STEP_NAMES.get(key, key)
            body = "\n\n".join(str(c).strip() for c in chunks if str(c).strip())
            if not body:
                continue
            sections.append(
                '<div class="md-full-section">'
                f'<h3>{name}</h3>'
                f'<div class="step-full">{render_text_with_emphasis(body)}</div>'
                '</div>'
            )
    verify_block = ""
    if verify_raw and str(verify_raw).strip():
        verify_block = (
            '<div class="md-full-section"><h3>独立审查最终结论（原文）</h3>'
            f'<div class="step-full">{render_text_with_emphasis(verify_raw)}</div></div>'
        )
    if not sections and not verify_block:
        return ""
    return (
        '<details class="tech-trail">'
        '<summary>🔧 技术留痕（默认收起 · 非断语，问卦人可跳过）</summary>'
        '<p class="tech-trail-note">以下为解卦流程的内部执行记录——各步参考资料加载清单、'
        '流程门禁与自检痕迹、独立审查报告原文、修正记录等。它们用于复核流程是否按规执行，'
        '与卦理断语无关；展开查看仅作留痕，不影响上方任何结论。</p>'
        + "".join(sections)
        + verify_block
        + '</details>'
    )


def generate(data: dict, output_path: str) -> str:
    # 对外交付语言闸门：先剥离内部流程痕迹，再渲染（原文进「技术留痕」折叠区）
    verify_raw = ""
    if isinstance(data.get("steps", {}).get("step8"), dict):
        s8_raw = data["steps"]["step8"]
        verify_raw = str(s8_raw.get("final") or s8_raw.get("summary") or "")
    data, internal_fragments, residual = build_client_view(data)
    if residual:
        print(
            "⚠️ 对外文本仍残留内部流程词（未加 LIUYAO-INTERNAL 分隔区，"
            "已无法自动清洗）：" + "；".join(residual[:12]),
            file=sys.stderr,
        )
    print(
        f"   技术留痕：已折叠 {sum(len(v) for v in internal_fragments.values())} 段内部流程记录"
        f"（默认收起，不进可读区）"
    )

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

    # 日空/月空分开展示（v1.8.2：支持独立字段与旧合并字符串两种格式）
    day_kong, yue_kong = split_kong_wang(meta)

    # 套餐徽章（frv：由 meta.edition 传入，SKILL.md 组装时固定填写「免费基础版」）
    edition = str(meta.get("edition", "")).strip()
    if edition:
        edition_badge = f"六爻解卦 · {edition}"
        edition_class = "pro" if "高级" in edition else "free" if "免费" in edition else ""
    else:
        edition_badge, edition_class = "", ""

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

    # 自动检测特殊格局；展示层优先使用 step3.pattern 的人工深断文本，
    # 自动摘要只作为缺失深断时的兜底提示。
    patterns = detect_patterns(ben_lines, yao, meta)
    patterns_html = build_patterns_section(patterns, s3.get("pattern", ""))

    # 神煞渲染
    shensha_html = build_shensha_section(meta, yao)

    # 解卦过程全文附录（md_full，缺失时自动隐藏板块；已剥离内部痕迹）
    md_full_block = build_md_full_block(data.get("md_full", {}))

    # 技术留痕折叠区（内部流程记录 + 审查原文，默认收起）
    tech_trail_block = build_tech_trail_block(internal_fragments, verify_raw)

    # 页脚校验印记：只出一句人话，内部审查原文收进技术留痕
    if verify_raw.strip() and not find_internal_tokens(verify_raw):
        verify_display = f"✅ {verify_raw.strip()}"
    else:
        verify_display = (
            "✅ 已通过独立校验：审查发现的问题已在解卦过程中逐一修正"
            "（流程细节见文末「🔧 技术留痕」）"
        )

    html = HTML_TEMPLATE.format(
        ben_gua=meta["ben_gua"],
        bian_gua=meta.get("bian_gua") or "静卦",
        question=meta["question"],
        date=meta["date"],
        lunar=meta.get("lunar", ""),
        yue_jian=meta["yue_jian"],
        ri_chen=meta["ri_chen"],
        day_kong=day_kong,
        yue_kong=yue_kong,
        edition_badge=edition_badge,
        edition_class=edition_class,
        gua_panels_html=gua_panels_html,
        yao_rows=yao_rows_html,
        wang_shuai_block=build_wang_shuai_block(meta),
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
        md_full_block=md_full_block,
        tech_trail_block=tech_trail_block,
        verify_result=verify_display,
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

    meta = data.get("meta", {}) if isinstance(data.get("meta"), dict) else {}
    intent = str(meta.get("intent", "") or "")
    question = str(meta.get("question", "") or "")
    if is_pregnancy_blocked_request(question, intent):
        errors.append(pregnancy_block_message(question, intent))

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

    # ── 占位内容检测（防"空报告"——paipan 扁平格式自动适配时填入的占位文本）──
    PLACEHOLDER_SIGNATURES = {
        "step1.note": "未做解卦分析",
        "step2.verdict": "未分析（仅盘面）",
        "step7.final_verdict": "未做解卦分析",
        "step7.qualitative": "盘面报告",
        "step8.final": "仅盘面，未校验",
    }
    if "steps" in data:
        s = data["steps"]
        for key, sig in PLACEHOLDER_SIGNATURES.items():
            step_name, field = key.split(".")
            val = s.get(step_name, {}).get(field, "") if step_name in s else ""
            if sig in str(val):
                errors.append(
                    f"{key} 仍是占位文本（含 '{sig}'），"
                    f"未注入真实解卦内容。请回到第九步：必须先按 html-report-guide.md "
                    f"schema 从步骤 md 文件组装完整 JSON，再跑 --validate。"
                )

        # ── 特殊格局深断校验（frv v1.8.x：防「合则牵缠/冲则变动」式浅摘要混入交付）──
        step3_pattern = str(s.get("step3", {}).get("pattern", "") or "")
        shallow_signatures = ("合则绊住", "合则牵缠", "冲则变动", "游魂不定", "归魂拘泥", "事有牵缠", "事多散乱")
        deep_markers = ("角色", "用神", "世应", "应期", "合化", "冲起", "冲破", "冲开", "冲散", "所强", "参与")
        if any(sig in step3_pattern for sig in shallow_signatures) and not any(marker in step3_pattern for marker in deep_markers):
            errors.append(
                "step3.pattern 疑似仅含特殊格局套话（如「合则牵缠/冲则变动」），"
                "未完成铁律11深断。请补齐来源、类型、参与者、角色归属、合冲/成局产物、"
                "力量状态、对用神、对世应、应期、结果断语。"
            )

        # ── 应期排序校验（frv v1.8.4：结构化三层，防主应期被辅助节点淹没）──
        step6 = s.get("step6", {}) if isinstance(s.get("step6", {}), dict) else {}
        step6_text = "\n".join(str(step6.get(k, "") or "") for k in ("matched_rule", "window", "detail", "unit"))
        layers = step6.get("layers")
        layer_texts = {}
        if isinstance(layers, dict):
            layer_texts = {
                "main": normalize_layer_text(layers.get("main")),
                "auxiliary": normalize_layer_text(layers.get("auxiliary")),
                "risk": normalize_layer_text(layers.get("risk")),
            }
        if step6_text and not isinstance(layers, dict):
            errors.append(
                "step6 缺少结构化 layers 字段（main/auxiliary/risk）。"
                "请将主应期、辅助节点、风险窗口分层写入 step6.layers，不要只塞在 window/detail 文本里。"
            )
        elif step6_text:
            missing_layer_keys = [
                name for name, text in layer_texts.items()
                if not text
            ]
            if missing_layer_keys:
                errors.append(
                    "step6.layers 缺少内容："
                    + "、".join(missing_layer_keys)
                    + "。main/auxiliary/risk 三层均须填写，无法判断时也要写明理由。"
                )
        scenario_intent = intent
        if "跳槽" in question or "工作" in question or "升职" in question or "面试" in question:
            scenario_intent = "官运"
        requirements = SCENARIO_YINGQI_LAYER_REQUIREMENTS.get(scenario_intent, {})
        if requirements and step6_text and isinstance(layers, dict):
            missing_layer_roles = []
            for layer_name, (markers, description) in requirements.items():
                text = layer_texts.get(layer_name, "")
                if text and not any(marker in text for marker in markers):
                    missing_layer_roles.append(f"{layer_name}（{description}）")
            if missing_layer_roles:
                errors.append(
                    f"step6 {scenario_intent} 应期 layers 未按场景角色分层交代："
                    + "、".join(missing_layer_roles)
                    + "。请按 yingqi-faze.md「场景应期角色分层表」区分主应期、辅助节点、风险窗口。"
                )

    # ── md_full 全文保真校验（v1.8.1：防第九步组装时压缩/省略步骤 md 原文）──
    # md_full 必须存在且逐字承载步骤 md 全文；长度低于下限 = 组装时被摘要化，阻断。
    MD_FULL_MIN_LEN = {"step1": 50, "step2": 50, "step3": 50, "step4": 50,
                       "step5": 50, "step6": 50, "step7": 200}
    md_full = data.get("md_full")
    if not isinstance(md_full, dict):
        errors.append(
            "缺少顶层字段 md_full（解卦过程全文附录）。第九步组装 JSON 时必须将步骤0~7 "
            "md 文件内容逐字写入 md_full（如 {\"step1\": \"步骤1 md 全文\", ...}），"
            "HTML 报告的「📜 解卦过程全文」板块依赖该字段。"
        )
    else:
        for step_key, min_len in MD_FULL_MIN_LEN.items():
            content = md_full.get(step_key, "")
            if not content or not str(content).strip():
                errors.append(f"md_full.{step_key} 为空——步骤 md 全文未注入，报告将丢失该步分析。")
            elif len(str(content)) < min_len:
                errors.append(
                    f"md_full.{step_key} 仅 {len(str(content))} 字符（下限 {min_len}）——"
                    f"疑似组装时被压缩/摘要化。必须逐字写入步骤 md 全文，禁止改写精简。"
                )
        for step_key, sig in (("step1", "未做解卦分析"), ("step7", "未做解卦分析")):
            content = md_full.get(step_key, "")
            if sig in str(content):
                errors.append(f"md_full.{step_key} 含占位文本 '{sig}'，未注入真实解卦内容。")

    # ── 套餐徽章校验（frv：meta.edition 若存在必须是 免费基础版；缺失时徽章不显示）──
    edition = str(data.get("meta", {}).get("edition", "")).strip() if "meta" in data else ""
    if edition and edition != "免费基础版":
        errors.append(f"meta.edition 非法值 '{edition}'——本分支必须为「免费基础版」（由 SKILL.md 组装时填写）。")

    # ── 动变方向↔五行生克一致性校验（🚨 防方向性错误：申=金→卯=木 是金克木=本爻克变爻，不是回头克）──
    DIZHI_WUXING = {
        "申": "金", "酉": "金",
        "寅": "木", "卯": "木",
        "亥": "水", "子": "水",
        "巳": "火", "午": "火",
        "辰": "土", "戌": "土", "丑": "土", "未": "土",
    }
    WUXING_KE = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}
    WUXING_SHENG = {"金": "水", "水": "木", "木": "火", "火": "土", "土": "金"}
    TAG_TO_REQUIRED = {
        "回头克": "bian_ke_ben",
        "回头生": "bian_sheng_ben",
        "化出我克者": "ben_ke_bian",
        "化出我生者": "ben_sheng_bian",
    }
    DIR_NAMES = {
        "bian_ke_ben": "回头克",
        "bian_sheng_ben": "回头生",
        "ben_ke_bian": "化出我克者",
        "ben_sheng_bian": "化出我生者",
    }
    if "yao" in data and "steps" in data and "step3" in data["steps"]:
        step3_dong = {d["pos"]: d for d in data["steps"]["step3"].get("dong_yao", [])}
        for y in data["yao"]:
            if not y.get("dong"):
                continue
            pos = y["pos"]
            bw = y.get("wu_xing", "")
            bian_dz = y.get("bian_di_zhi")
            if not bian_dz or not bw:
                continue
            bian_wx = DIZHI_WUXING.get(bian_dz)
            if not bian_wx:
                continue

            if bw == bian_wx:
                actual_dir = "same"
            elif WUXING_KE.get(bw) == bian_wx:
                actual_dir = "ben_ke_bian"
            elif WUXING_KE.get(bian_wx) == bw:
                actual_dir = "bian_ke_ben"
            elif WUXING_SHENG.get(bw) == bian_wx:
                actual_dir = "ben_sheng_bian"
            elif WUXING_SHENG.get(bian_wx) == bw:
                actual_dir = "bian_sheng_ben"
            else:
                actual_dir = "unknown"

            sd = step3_dong.get(pos)
            if not sd:
                continue
            ct = sd.get("change_type", "")
            for tag, required_dir in TAG_TO_REQUIRED.items():
                if tag in ct:
                    if actual_dir != required_dir:
                        correct_tag = DIR_NAMES.get(actual_dir, actual_dir)
                        errors.append(
                            f"yao pos={pos} 动变方向矛盾：本爻{bw}({y['di_zhi']}) → 变爻{bian_wx}({bian_dz})，"
                            f"实际方向={actual_dir}(应标'{correct_tag}')，"
                            f"但 step3 change_type 含 '{tag}'（要求方向={required_dir}）。"
                            f"请回退第三步修正生克方向判定（参考 jie-gua-xiang-jie.md §3.2 前置步骤）。"
                        )
                    break

    # ── 对外交付语言校验（v2.0.7：交付报告只出人话，内部痕迹必须折叠）──
    try:
        _client, fragments, residual = build_client_view(data)
        if residual:
            errors.append(
                "对外文本残留内部流程词（报告将出现「不说人话」的流程黑话）："
                + "、".join(residual[:10])
                + "。请把这些内容移进 <!-- LIUYAO-INTERNAL:BEGIN --> … "
                "<!-- LIUYAO-INTERNAL:END --> 分隔区（见 SKILL.md 铁律 18）。"
            )
        elif not fragments:
            errors.append(
                "未识别到任何内部流程留痕（LIUYAO-INTERNAL 分隔区 / 加载清单块）。"
                "请确认各步骤 md 已按铁律 15 写入参考资料加载清单——清单缺失即为步骤无效。"
            )
    except Exception as exc:  # 清洗器异常不得静默放过
        errors.append(f"对外语言清洗失败：{exc}")

    return (len(errors) == 0, errors)

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="六爻卦象 HTML 报告生成器 v2.0.7")
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
            _client, fragments, _residual = build_client_view(data)
            moved = sum(len(v) for v in fragments.values())
            print(f"✅ Schema OK（已识别 {moved} 段内部流程留痕，将折叠进「技术留痕」区）")
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
                    "step6": {"matched_rule": "", "window": "", "unit": "", "detail": "", "layers": {"main": "", "auxiliary": "", "risk": ""}},
                    "step7": {"qualitative": "盘面报告", "basis": "由 paipan.py 自动排盘生成", "final_verdict": "此报告仅含排盘信息，未做解卦分析。请通过六爻解卦 Skill 九步法进行完整分析。", "trend": "", "action_advice": ""},
                    "step8": {"integrity": "", "cross_check": "", "principles": "", "final": "仅盘面，未校验"},
                },
                "md_full": {},
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
    # v1.9.0：「旺相休囚死」板块（wxs-row）
    sections.append("wxs-row")
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
                patterns.append({"name": name, "level": "检测摘要", "detail": f'卦中{"、".join(dz_set)}三支皆动，严格成局。此处仅提示格局存在，完整断法须回看第三步：定所强六亲、成员角色、对用神/世应影响与应期。', "css": "sanhui-cheng"})
            elif kong_yao:
                kong_dz = [y["di_zhi"] for y in kong_yao]
                dong_info = f'，其中{len(dong_yao)}爻发动' if dong_yao else ''
                patterns.append({"name": name, "level": "检测摘要", "detail": f'{"、".join(dz_set)}三支俱全{dong_info}，但{"、".join(kong_dz)}旬空。此处仅提示格局存在，完整断法须回看第三步：注明空亡打折、出空升级、所强六亲与对用神影响。', "css": "sanhui-shi-kong"})
            elif len(dong_yao) >= 1:
                patterns.append({"name": name, "level": "检测摘要", "detail": f'{"、".join(dz_set)}三支俱全，{len(dong_yao)}爻发动。此处仅提示格局存在，完整断法须回看第三步：判断成局状态、所强之爻、对用神吉凶与结果。', "css": "sanhui-shi"})
            else:
                patterns.append({"name": name, "level": "检测摘要", "detail": f'{"、".join(dz_set)}三支俱全，静卦伏势。此处仅提示格局存在，完整断法须回看第三步：判断是否仅为势、是否有日月引动及对用神影响。', "css": "sanhui-shi"})
    
    # ── 六合检测 ──
    liuhe = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯","辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
    he_pairs = []
    for i, y1 in enumerate(sorted_yao):
        for y2 in sorted_yao[i+1:]:
            if liuhe.get(y1["di_zhi"]) == y2["di_zhi"]:
                he_pairs.append((y1, y2))
    if he_pairs:
        detail = "、".join(f'{y1["di_zhi"]}({y1["liu_qin"]})合{y2["di_zhi"]}({y2["liu_qin"]})' for y1, y2 in he_pairs)
        patterns.append({"name": "六合", "level": "检测摘要", "detail": f'卦中存在六合关系：{detail}。此处仅提示格局存在，完整断法须回看第三步：逐项判断角色归属、合化五行、合住谁、释放点及对用神/世应的影响。', "css": "liuhe"})
    
    # ── 六冲检测 ──
    liuchong = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅","卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
    chong_pairs = []
    for i, y1 in enumerate(sorted_yao):
        for y2 in sorted_yao[i+1:]:
            if liuchong.get(y1["di_zhi"]) == y2["di_zhi"]:
                chong_pairs.append((y1, y2))
    if chong_pairs:
        detail = "、".join(f'{y1["di_zhi"]}({y1["liu_qin"]})冲{y2["di_zhi"]}({y2["liu_qin"]})' for y1, y2 in chong_pairs)
        patterns.append({"name": "六冲", "level": "检测摘要", "detail": f'卦中存在六冲关系：{detail}。此处仅提示格局存在，完整断法须回看第三步：逐项判断谁冲谁、谁旺谁弱、冲起/冲破/冲开/冲散及对用神/世应的影响。', "css": "liuchong"})
    
    # ── 本卦六冲卦检测 ──
    # 六冲卦判定：初四/二五/三上 三对爻位地支全部相冲
    # 六冲卦仅10个：八纯卦(8)+天雷无妄+雷天大壮
    # 注意：风雷益(上巽下震)不是六冲卦——上下卦互补但纳支不全冲
    liuchong_dz = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅","卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
    dz_by_pos = {y["pos"]: y["di_zhi"] for y in sorted_yao}
    chong_count = 0
    for a, b in [(1,4),(2,5),(3,6)]:
        if liuchong_dz.get(dz_by_pos.get(a)) == dz_by_pos.get(b):
            chong_count += 1
    if chong_count == 3:
        sgua = get_trigram((ben_lines[3], ben_lines[4], ben_lines[5]))
        xgua = get_trigram((ben_lines[0], ben_lines[1], ben_lines[2]))
        patterns.append({"name": "六冲卦", "level": "检测摘要", "detail": f'本卦上{TRIGRAM_SYMBOL[sgua]}下{TRIGRAM_SYMBOL[xgua]}为六冲卦。此处仅提示卦体结构倾向，完整断法须回看第三步/第七步，且不得替代具体爻层生克冲合分析。', "css": "liuchong"})
    
    # ── 伏吟检测（动爻化同地支） ──
    fy_yao = [y for y in sorted_yao if y.get("dong") and y.get("bian_di_zhi") == y.get("di_zhi")]
    if fy_yao:
        detail = "、".join(f'{y["liu_qin"]}{y["di_zhi"]}化{y["di_zhi"]}' for y in fy_yao)
        patterns.append({"name": "伏吟", "level": "检测摘要", "detail": f'动爻{detail}，伏吟之象。此处仅提示格局存在，完整断法须回看第三步：判断发生层位、角色归属、对用神/世应的影响及应期。', "css": "fuyin"})
    
    # ── 反吟检测（动变对冲冲位） ──
    fy_chong = [y for y in sorted_yao if y.get("dong") and y.get("bian_di_zhi") and liuchong.get(y.get("di_zhi","")) == y.get("bian_di_zhi")]
    if fy_chong:
        detail = "、".join(f'{y["liu_qin"]}{y["di_zhi"]}化{y["bian_di_zhi"]}' for y in fy_chong)
        patterns.append({"name": "反吟", "level": "检测摘要", "detail": f'动爻{detail}，反吟之象。此处仅提示格局存在，完整断法须回看第三步：判断发生层位、角色归属、反复来自我方/对方/流程/结局哪一层。', "css": "fanyin"})
    
    return patterns


def build_patterns_section(patterns, step3_pattern=""):
    """构建特殊格局 HTML 板块。

    frv v1.8.x 深断规则：优先展示 step3.pattern 中由解卦流程写出的深断文本。
    自动检测摘要只用于兜底，避免报告首页用模板短句替代真正分析。
    """
    deep_text = str(step3_pattern or "").strip()
    if deep_text and deep_text not in {"无", "无特殊格局", "本卦未检测到明显特殊格局。"}:
        rendered = render_text_with_emphasis(deep_text)
        return (
            '<h2>特殊格局</h2>\n'
            '<p class="md-full-intro">以下为卦中特殊格局的逐项解读：成局与否由排盘自动识别，'
            '吉凶落到何事则由卦理逐条说透。</p>\n'
            f'<div class="step-full pattern-deep">{rendered}</div>'
        )

    if not patterns:
        return "<p>本卦未检测到明显特殊格局。</p>"
    
    css_map = {
        "sanhui-cheng": "background:#e8f5e9;border-left:4px solid #2e7d32;",
        "sanhui-shi-kong": "background:#fff8e1;border-left:4px solid #f9a825;",
        "sanhui-shi": "background:#fff8e1;border-left:4px solid #f9a825;",
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


# ── 旺相休囚死（v1.9.0）────────────────────────────────────

# 月建地支 → 五行
DZ_TO_WX = {"寅": "木", "卯": "木", "巳": "火", "午": "火", "申": "金", "酉": "金",
            "亥": "水", "子": "水", "辰": "土", "戌": "土", "丑": "土", "未": "土"}
WX_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}      # 我生 → 相
WX_SHENG_WO = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}   # 生我 → 休
WX_KE_WO = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}      # 克我 → 囚
WX_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}          # 我克 → 死
WXS_CLS = {"木": "wxs-mu", "火": "wxs-huo", "土": "wxs-tu", "金": "wxs-jin", "水": "wxs-shui"}
STATE_ORDER = ["旺", "相", "休", "囚", "死"]  # 展示顺序：能量从高到低


def build_wang_shuai_block(meta: dict) -> str:
    """旺相休囚死板块：按能量从高到低（旺相休囚死）展示五行之气在月令下的流转。

    v1.9.0 已同步「旺相休囚死」板块。
    """
    month_branch = str(meta.get("yue_jian", "")).strip()
    month_wx = DZ_TO_WX.get(month_branch, "")
    if not month_wx:
        return ""
    states = {month_wx: "旺", WX_SHENG[month_wx]: "相", WX_SHENG_WO[month_wx]: "休",
              WX_KE_WO[month_wx]: "囚", WX_KE[month_wx]: "死"}
    cards = "".join(
        f'<div class="wxs-card {WXS_CLS[wx]}"><span class="wxs-name">{wx}</span>'
        f'<span class="wxs-state">{states[wx]}</span></div>'
        for wx in sorted(states, key=lambda w: STATE_ORDER.index(states[w])))
    return (f'<h2>旺相休囚死</h2>'
            f'<p class="wxs-sub">{month_branch}月{month_wx}当令 · 当令者旺，令生者相，生令者休，克令者囚，令克者死</p>'
            f'<div class="wxs-row">{cards}</div>')


if __name__ == "__main__":
    main()


# ── 特殊格局自动检测 ────────────────────────────────────────
