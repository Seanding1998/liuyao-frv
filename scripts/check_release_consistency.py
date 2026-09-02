#!/usr/bin/env python3
"""Check liuyao release-version display consistency.

`SKILL.md` metadata.version is the single source of truth. This script reports
version drift in human-facing docs and CLI strings; it never modifies files.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    expected: str
    actual: str | None
    ok: bool
    detail: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def first_match(pattern: str, text: str, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1) if match else None


def skill_version(root: Path) -> str:
    text = read_text(root / "SKILL.md")
    version = first_match(r"(?m)^\s*version:\s*[\"']?([^\"'\s]+)[\"']?\s*$", text)
    if not version:
        raise RuntimeError("SKILL.md metadata.version not found")
    return version


def check_value(name: str, expected: str, actual: str | None, detail: str) -> CheckResult:
    return CheckResult(
        name=name,
        expected=expected,
        actual=actual,
        ok=(actual == expected),
        detail=detail,
    )


def collect_checks(root: Path, expected: str) -> list[CheckResult]:
    version_with_v = f"v{expected}"
    readme = read_text(root / "README.md")
    changelog = read_text(root / "CHANGELOG.md")
    html_guide = read_text(root / "references" / "html-report-guide.md")
    generate_report = read_text(root / "scripts" / "generate_report.py")

    return [
        check_value(
            "README current version",
            version_with_v,
            first_match(r"(?m)^-\s+\*\*(v\d+\.\d+\.\d+)\*\*\s+—", readme),
            "README.md version list first current bullet",
        ),
        check_value(
            "CHANGELOG top release",
            version_with_v,
            first_match(r"(?m)^##\s+(v\d+\.\d+\.\d+)\s+\(", changelog),
            "CHANGELOG.md first release heading",
        ),
        check_value(
            "HTML guide script version",
            version_with_v,
            first_match(r"\*\*脚本版本\*\*：\s*(v\d+\.\d+\.\d+)", html_guide),
            "references/html-report-guide.md script version line",
        ),
        check_value(
            "generate_report docstring version",
            version_with_v,
            first_match(r"六爻卦象 HTML 报告生成器\s+(v\d+\.\d+\.\d+)", generate_report),
            "scripts/generate_report.py module docstring",
        ),
        check_value(
            "generate_report CLI description version",
            version_with_v,
            first_match(r"ArgumentParser\(description=\"六爻卦象 HTML 报告生成器\s+(v\d+\.\d+\.\d+)\"", generate_report),
            "scripts/generate_report.py argparse description",
        ),
    ]


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    root = repo_root()
    expected = skill_version(root)
    checks = collect_checks(root, expected)

    print(f"Release consistency source: SKILL.md metadata.version = {expected}")
    print()

    failures = 0
    for result in checks:
        status = "PASS" if result.ok else "FAIL"
        actual = result.actual if result.actual is not None else "<missing>"
        print(f"[{status}] {result.name}")
        print(f"       expected: {result.expected}")
        print(f"       actual:   {actual}")
        print(f"       detail:   {result.detail}")
        if not result.ok:
            failures += 1

    if failures:
        print()
        print(f"Release consistency failed: {failures} mismatched item(s).")
        return 1

    print()
    print("Release consistency passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
