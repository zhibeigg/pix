"""项目内置资源路径解析。"""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """返回 pix 内置资源路径，兼容源码运行、包安装与 PyInstaller。"""
    rel = Path(*parts)
    meipass = getattr(sys, "_MEIPASS", None)
    candidates: list[Path] = []
    if meipass:
        base = Path(meipass)
        candidates.extend([
            base / "pix" / "assets" / rel,
            base / "assets" / rel,
        ])

    # 源码 / editable / 普通 wheel 安装通常都能解析成真实文件系统路径。
    try:
        traversable = resources.files("pix").joinpath("assets", *parts)
        candidate = Path(str(traversable))
        candidates.append(candidate)
    except Exception:  # pragma: no cover - importlib.resources fallback
        pass

    candidates.append(Path(__file__).resolve().parent / "assets" / rel)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def app_icon_path() -> Path:
    """GUI / 通用 PNG 图标。"""
    return resource_path("icons", "pix_logo_64.png")


def windows_icon_path() -> Path:
    """Windows PyInstaller EXE 图标。"""
    return resource_path("icons", "pix_logo.ico")


def macos_icon_path() -> Path:
    """macOS app bundle 图标。"""
    return resource_path("icons", "pix_logo.icns")
