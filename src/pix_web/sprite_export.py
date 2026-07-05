"""序列帧作品的按需 GIF 导出。

作品生成默认 `gif_export=False`（作品库优先用 sprite_sheet.png + sequence.json
逐帧播放），因此大多数序列帧作品磁盘上并没有 sprite.gif。本模块从当前活跃的
序列帧 meta（`sprite.frames`，已随对齐版本同步）按需内存合成 GIF：
- 快路：meta 里已有 sprite.gif 且文件存在，直接读回字节，零重算。
- 慢路：用 PIL 从各帧内存合成，行为与 pix.sprite.compose_gif 一致（RGBA、disposal=2）。

仅在用户点击下载时触发，不改生成管线、不占额外存储。
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image


def _load_meta(meta_json_path: str | None) -> dict[str, Any]:
    if not meta_json_path:
        return {}
    try:
        data = json.loads(Path(meta_json_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_meta_path(meta_json_path: str, value: str | None) -> Path | None:
    """把 meta 内的相对路径解析成绝对路径（与 schemas._resolve_meta_relative_path 同口径）。"""
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    if "/" not in value and "\\" not in value:
        return Path(meta_json_path).with_name(value)
    return Path(meta_json_path).parent / value


def _fps_to_duration_ms(sprite: dict[str, Any]) -> int:
    duration = sprite.get("duration_ms")
    try:
        duration_int = int(duration) if duration is not None else 0
    except (TypeError, ValueError):
        duration_int = 0
    if duration_int > 0:
        return max(20, duration_int)
    fps = sprite.get("fps")
    try:
        fps_int = int(fps) if fps is not None else 0
    except (TypeError, ValueError):
        fps_int = 0
    if fps_int <= 0:
        fps_int = 8
    return max(20, int(round(1000 / fps_int)))


def _loop_value(sprite: dict[str, Any]) -> int:
    loop = sprite.get("loop")
    try:
        return max(0, int(loop)) if loop is not None else 0
    except (TypeError, ValueError):
        return 0


def _frame_paths(meta_json_path: str, sprite: dict[str, Any]) -> list[Path]:
    raw_frames = sprite.get("frames")
    if not isinstance(raw_frames, list):
        return []
    paths: list[Path] = []
    for item in raw_frames:
        if not isinstance(item, dict):
            continue
        resolved = _resolve_meta_path(meta_json_path, str(item.get("path") or ""))
        if resolved is not None and resolved.is_file():
            paths.append(resolved)
    return paths


def _existing_gif_bytes(meta_json_path: str, meta: dict[str, Any], sprite: dict[str, Any]) -> bytes | None:
    outputs = meta.get("outputs") if isinstance(meta.get("outputs"), dict) else {}
    gif_rel = outputs.get("sprite_gif") or sprite.get("gif")
    if not gif_rel:
        return None
    gif_path = _resolve_meta_path(meta_json_path, str(gif_rel))
    if gif_path is None or not gif_path.is_file():
        return None
    try:
        return gif_path.read_bytes()
    except OSError:
        return None


def build_sprite_gif_bytes(meta_json_path: str | None) -> bytes | None:
    """从序列帧作品 meta 生成可下载的 GIF 字节；无可用帧时返回 None。

    优先复用磁盘上已生成的 sprite.gif；否则按当前活跃帧内存合成。
    """
    meta = _load_meta(meta_json_path)
    sprite = meta.get("sprite") if isinstance(meta.get("sprite"), dict) else {}
    if not isinstance(sprite, dict) or not sprite:
        return None
    assert meta_json_path is not None  # _load_meta 非空才有 sprite

    existing = _existing_gif_bytes(meta_json_path, meta, sprite)
    if existing is not None:
        return existing

    frame_paths = _frame_paths(meta_json_path, sprite)
    if not frame_paths:
        return None

    frames: list[Image.Image] = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    if not frames:
        return None

    buffer = BytesIO()
    first, rest = frames[0], frames[1:]
    first.save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=rest,
        duration=_fps_to_duration_ms(sprite),
        loop=_loop_value(sprite),
        disposal=2,
    )
    return buffer.getvalue()
