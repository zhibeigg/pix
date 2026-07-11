from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
SECTION_RE = re.compile(r"^## \[([^\]]+)\](?:\s+-\s+.*)?$", re.MULTILINE)


def extract_release_notes(text: str, version: str) -> str:
    normalized = version.removeprefix("v")
    sections = list(SECTION_RE.finditer(text))
    for index, match in enumerate(sections):
        if match.group(1) != normalized:
            continue
        start = match.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        return text[start:end].strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="从 CHANGELOG.md 提取指定版本的发布说明。")
    parser.add_argument(
        "version",
        nargs="?",
        default=os.environ.get("GITHUB_REF_NAME", ""),
        help="版本或标签，例如 1.2.3 / v1.2.3；默认读取 GITHUB_REF_NAME。",
    )
    parser.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.version:
        parser.error("必须提供版本，或设置 GITHUB_REF_NAME")
    if not args.changelog.is_file():
        print(f"找不到变更记录：{args.changelog}", file=sys.stderr)
        return 1

    notes = extract_release_notes(args.changelog.read_text(encoding="utf-8"), args.version)
    if not notes:
        print(f"CHANGELOG.md 中没有 {args.version.removeprefix('v')} 的发布段落", file=sys.stderr)
        return 1

    rendered = notes + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
