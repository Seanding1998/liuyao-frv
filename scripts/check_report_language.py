#!/usr/bin/env python3
"""六爻报告「对外交付语言」验收器（v2.0.7 配套）。

用途：对着**已生成的 HTML 报告**复检「可读区有没有内部流程黑话」。
与 `generate_report.py --validate` 的区别：`--validate` 查的是组装前的 JSON，
本脚本查的是最终 HTML——能在交付前抓住任何漏网的内部语（含手工改过的报告）。

判定口径与 `generate_report.py` 的 `INTERNAL_TOKEN_RE` 完全同源（直接 import），
不另立一份黑名单，避免两处漂移。

用法：
    python check_report_language.py path/to/liuyao-report.html
    python check_report_language.py --verbose path/to/liuyao-report.html

退出码：0 = 可读区干净；1 = 发现残留（打印命中位置与上下文）；2 = 参数/文件错误。
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_report as G  # noqa: E402

TRAIL_MARKER = '<details class="tech-trail">'


def client_region(markup: str) -> str:
    """取可读区（技术留痕 `<details>` 之前的部分）。"""
    idx = markup.find(TRAIL_MARKER)
    return markup[:idx] if idx >= 0 else markup


def html_to_text(markup: str) -> str:
    """把 HTML 还原成「读者实际看到的文字」：去脚本/样式/标签/注释，解实体。

    不这样做会把 `class=`、`display =` 这类 HTML/CSS 属性误判成内部流程语。
    """
    text = re.sub(r"(?is)<script\b.*?</script>", " ", markup)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)</?(?:details|summary)\b[^>]*>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    return re.sub(r"[ \t]{2,}", " ", text)


def scan(markup: str):
    client_text = html_to_text(client_region(markup))
    hits = []
    for m in G.INTERNAL_TOKEN_RE.finditer(client_text):
        token = m.group(0)
        start = max(0, m.start() - 60)
        end = min(len(client_text), m.end() + 60)
        context = re.sub(r"\s+", " ", client_text[start:end]).strip()
        hits.append((token, context))
    return hits, client_text


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="六爻报告对外交付语言验收器 v2.0.7")
    parser.add_argument("html", help="待检查的 HTML 报告路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印每条命中的上下文")
    args = parser.parse_args()

    path = Path(args.html)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 2

    markup = path.read_text(encoding="utf-8")
    hits, client_text = scan(markup)

    has_trail = TRAIL_MARKER in markup
    collapsed = bool(re.search(r'<details class="tech-trail"(?![^>]*\bopen\b)[^>]*>', markup))

    print(f"报告: {path}")
    print(f"  可读区正文（还原后的可见文字）字符数: {len(client_text):,}")
    print(f"  技术留痕区: {'存在' if has_trail else '不存在'}")
    if has_trail:
        print(f"  默认收起: {'✅' if collapsed else '❌ 未收起（应为默认折叠）'}")
    print(f"  可读区内部流程词命中: {len(hits)}")

    if hits:
        print("\n❌ 可读区仍有内部流程语，必须修正：")
        for token, context in hits[:30]:
            print(f"  - [{token}] …{context}…")
        if len(hits) > 30:
            print(f"  …另有 {len(hits) - 30} 处")
        if args.verbose:
            print("\n提示：把这些内容移进步骤 md 的 "
                  "<!-- LIUYAO-INTERNAL:BEGIN --> … <!-- LIUYAO-INTERNAL:END --> 分隔区，"
                  "重新生成即可自动折叠。")
        return 1

    print("\n✅ 可读区干净（只出人话），技术留痕已折叠。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
