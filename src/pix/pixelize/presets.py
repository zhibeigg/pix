"""风格预设加载与合并。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class Preset:
    name: str
    description: str = ""
    output_size: tuple[int, int] | None = None
    colors: int | None = None
    palette_lock: list[str] = field(default_factory=list)
    dither: str | None = None
    edge_enhance: float | None = None
    saturation: float | None = None


def _builtin_presets_dir() -> Path:
    """返回仓库内置预设目录。"""
    # 源码 / Docker 布局：src/pix/pixelize/presets.py → ../../../assets/presets
    return Path(__file__).resolve().parents[3] / "assets" / "presets"


_BUILTIN_DIR = _builtin_presets_dir()


def list_presets(extra_dir: Path | None = None) -> list[str]:
    names: set[str] = {"auto"}
    for d in (_BUILTIN_DIR, extra_dir):
        if d and d.exists():
            for p in d.glob("*.toml"):
                names.add(p.stem)
    return sorted(names)


def load_preset(name: str, extra_dir: Path | None = None) -> Preset | None:
    """按名字加载预设；auto 返回 None。"""
    if not name or name == "auto":
        return None
    for d in (_BUILTIN_DIR, extra_dir):
        if not d:
            continue
        path = d / f"{name}.toml"
        if path.exists():
            with path.open("rb") as fp:
                data = tomllib.load(fp)
            return _to_preset(name, data)
    return None


def _to_preset(name: str, data: dict[str, Any]) -> Preset:
    size = data.get("output_size")
    size_tuple: tuple[int, int] | None = None
    if isinstance(size, (list, tuple)) and len(size) == 2:
        size_tuple = (int(size[0]), int(size[1]))
    return Preset(
        name=str(data.get("name", name)),
        description=str(data.get("description", "")),
        output_size=size_tuple,
        colors=int(data["colors"]) if "colors" in data else None,
        palette_lock=list(data.get("palette_lock", []) or []),
        dither=data.get("dither"),
        edge_enhance=float(data["edge_enhance"]) if "edge_enhance" in data else None,
        saturation=float(data["saturation"]) if "saturation" in data else None,
    )
