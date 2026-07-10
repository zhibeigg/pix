from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)


def _load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_versions() -> dict[str, str]:
    pyproject = _load_toml(ROOT / "pyproject.toml")
    init_text = (ROOT / "src" / "pix" / "__init__.py").read_text(encoding="utf-8")
    init_match = VERSION_RE.search(init_text)
    if init_match is None:
        raise ValueError("src/pix/__init__.py 中缺少 __version__")

    package = _load_json(ROOT / "apps" / "web" / "package.json")
    package_lock = _load_json(ROOT / "apps" / "web" / "package-lock.json")
    lock_root = package_lock.get("packages", {}).get("", {})

    uv_lock = _load_toml(ROOT / "uv.lock")
    editable_versions = [
        str(item.get("version", ""))
        for item in uv_lock.get("package", [])
        if item.get("name") == "pix" and item.get("source", {}).get("editable") == "."
    ]
    if len(editable_versions) != 1:
        raise ValueError("uv.lock 中应恰好存在一个 editable pix 项目条目")

    return {
        "pyproject.toml": str(pyproject["project"]["version"]),
        "src/pix/__init__.py": init_match.group(1),
        "apps/web/package.json": str(package["version"]),
        "apps/web/package-lock.json": str(package_lock["version"]),
        "apps/web/package-lock.json#packages['']": str(lock_root.get("version", "")),
        "uv.lock": editable_versions[0],
    }


def _default_github_tag() -> str:
    if os.environ.get("GITHUB_REF_TYPE") != "tag":
        return ""
    return os.environ.get("GITHUB_REF_NAME", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Pix 发布版本在所有清单中保持一致。")
    parser.add_argument(
        "--tag",
        default=_default_github_tag(),
        help="可选的发布标签（格式 vA.B.C）；标签工作流默认读取 GITHUB_REF_NAME。",
    )
    args = parser.parse_args()

    try:
        versions = collect_versions()
    except (KeyError, OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"版本校验失败：{exc}", file=sys.stderr)
        return 1

    unique = set(versions.values())
    if len(unique) != 1 or "" in unique:
        print("版本不一致：", file=sys.stderr)
        for source, version in versions.items():
            print(f"  {source}: {version or '<missing>'}", file=sys.stderr)
        return 1

    version = unique.pop()
    if args.tag and args.tag != f"v{version}":
        print(f"标签 {args.tag!r} 与版本 v{version} 不一致", file=sys.stderr)
        return 1

    print(f"版本一致：{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
