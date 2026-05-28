"""序列帧锚点对齐与本地重合成。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import HTTPException, status
from PIL import Image

from pix.sprite import compose_gif, compose_horizontal_sprite_sheet
from pix_web.models import GenerationJob, GenerationOutput
from pix_web.schemas import SequenceAlignmentRequest


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧元数据无法读取") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧元数据格式不正确")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_meta_path(meta_path: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else meta_path.parent / path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _visible_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = np.asarray(image.convert("RGBA"))[..., 3]
    visible = alpha > threshold
    if not visible.any():
        return None
    ys, xs = np.where(visible)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _paste_offset(source: Image.Image, size: tuple[int, int], offset: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    src = source.convert("RGBA")
    ox, oy = int(offset[0]), int(offset[1])
    src_left = max(0, -ox)
    src_top = max(0, -oy)
    dest_left = max(0, ox)
    dest_top = max(0, oy)
    width = min(src.width - src_left, size[0] - dest_left)
    height = min(src.height - src_top, size[1] - dest_top)
    if width <= 0 or height <= 0:
        return canvas
    crop = src.crop((src_left, src_top, src_left + width, src_top + height))
    canvas.alpha_composite(crop, (dest_left, dest_top))
    return canvas


def _paste_aligned(
    source: Image.Image,
    size: tuple[int, int],
    *,
    offset: tuple[int, int],
    scale: float,
) -> Image.Image:
    """按帧中心缩放源图，再叠加用户偏移贴到画布。

    - scale==1.0 时退化为 _paste_offset（不重采样，避免无谓的精度损失）
    - 其它情况按 NEAREST 缩放，保留像素感
    - 缩放锚点固定为帧中心：缩放后会自动补偿位移，让中心对齐画布中心，再叠加用户 offset
    """
    safe_scale = max(0.05, float(scale or 1.0))
    if abs(safe_scale - 1.0) < 1e-3:
        return _paste_offset(source, size, offset)
    src = source.convert("RGBA")
    new_w = max(1, int(round(src.width * safe_scale)))
    new_h = max(1, int(round(src.height * safe_scale)))
    scaled = src.resize((new_w, new_h), Image.NEAREST)
    # 帧中心锚点：缩放前 (cx, cy)，缩放后中心要回到原 (cx, cy)
    center_x = src.width / 2.0
    center_y = src.height / 2.0
    base_x = int(round(center_x - new_w / 2.0))
    base_y = int(round(center_y - new_h / 2.0))
    final_offset = (base_x + int(offset[0]), base_y + int(offset[1]))
    return _paste_offset(scaled, size, final_offset)


def _size_from_sprite(sprite_meta: dict[str, Any]) -> tuple[int, int]:
    effective = sprite_meta.get("effective_frame_size")
    if isinstance(effective, (list, tuple)) and len(effective) == 2:
        try:
            width, height = int(effective[0]), int(effective[1])
            if width > 0 and height > 0:
                return width, height
        except (TypeError, ValueError):
            pass
    sequence = sprite_meta.get("sequence")
    if isinstance(sequence, dict):
        frame_size = sequence.get("effective_frame_size")
        if isinstance(frame_size, dict):
            try:
                width, height = int(frame_size.get("width")), int(frame_size.get("height"))
                if width > 0 and height > 0:
                    return width, height
            except (TypeError, ValueError):
                pass
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧缺少有效单帧尺寸")


def _frame_offsets(payload: SequenceAlignmentRequest) -> dict[int, tuple[int, int]]:
    offsets: dict[int, tuple[int, int]] = {}
    for item in payload.frames:
        offsets[int(item.index)] = (int(item.offset_x), int(item.offset_y))
    return offsets


def _frame_scales(payload: SequenceAlignmentRequest) -> dict[int, float]:
    scales: dict[int, float] = {}
    for item in payload.frames:
        try:
            scales[int(item.index)] = max(0.05, float(getattr(item, "scale", 1.0) or 1.0))
        except (TypeError, ValueError):
            scales[int(item.index)] = 1.0
    return scales


def apply_sequence_alignment(job: GenerationJob, output: GenerationOutput, payload: SequenceAlignmentRequest) -> GenerationJob:
    """应用每帧偏移并更新当前输出的活跃序列帧版本。"""

    if job.status != "succeeded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有生成成功的序列帧可以调整锚点")
    if job.job_type != "sprite_sheet":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该作品不是序列帧任务")

    meta_path = Path(output.meta_json_path)
    if not meta_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="序列帧元数据不存在")
    run_dir = meta_path.parent
    meta = _load_json(meta_path)
    sprite_meta = meta.get("sprite")
    if not isinstance(sprite_meta, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="作品缺少序列帧元数据")
    raw_frames = sprite_meta.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="作品缺少可调整的序列帧")

    frame_size = _size_from_sprite(sprite_meta)
    offsets = _frame_offsets(payload)
    scales = _frame_scales(payload)
    version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    align_root = run_dir / "alignments" / version
    aligned_frames_dir = align_root / "frames"
    aligned_frames_dir.mkdir(parents=True, exist_ok=True)

    aligned_frame_paths: list[Path] = []
    aligned_meta: list[dict[str, Any]] = []
    for index, item in enumerate(raw_frames, start=1):
        if not isinstance(item, dict):
            continue
        frame_index = int(item.get("index") or index)
        source_path = _resolve_meta_path(meta_path, str(item.get("path") or ""))
        if source_path is None or not source_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"第 {frame_index} 帧文件不存在")
        offset = offsets.get(frame_index, (0, 0))
        scale = scales.get(frame_index, 1.0)
        with Image.open(source_path) as opened:
            aligned = _paste_aligned(opened.convert("RGBA"), frame_size, offset=offset, scale=scale)
        frame_path = aligned_frames_dir / f"frame_{frame_index:03d}.png"
        aligned.save(frame_path)
        aligned_frame_paths.append(frame_path)
        bbox = _visible_bbox(aligned)
        sheet_rect = {"x": (frame_index - 1) * frame_size[0], "y": 0, "w": frame_size[0], "h": frame_size[1]}
        aligned_meta.append({
            "index": frame_index,
            "row": 0,
            "col": frame_index - 1,
            "raw_path": item.get("raw_path"),
            "reference_path": item.get("reference_path"),
            "path": _rel(frame_path, run_dir),
            "sheet_rect": sheet_rect,
            "action_phase": item.get("action_phase"),
            "bbox": list(bbox) if bbox else None,
            "alignment_offset": {"x": offset[0], "y": offset[1]},
            "alignment_scale": scale,
        })

    if not aligned_frame_paths:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="没有可合成的序列帧")

    sheet_path = align_root / "sprite_sheet.png"
    sequence_path = align_root / "sequence.json"
    gif_path = align_root / "sprite.gif"
    alignment_path = align_root / "alignment.json"
    compose_horizontal_sprite_sheet(aligned_frame_paths, sheet_path)
    gif_rel: str | None = None
    fps = int(payload.fps or sprite_meta.get("fps") or 8)
    duration_ms = max(20, int(round(1000 / max(1, fps))))
    if payload.gif_export:
        compose_gif(aligned_frame_paths, gif_path, duration_ms=duration_ms, loop=int(sprite_meta.get("loop") or 0))
        gif_rel = _rel(gif_path, run_dir)

    original_outputs = meta.get("outputs") if isinstance(meta.get("outputs"), dict) else {}
    original_alignment = sprite_meta.get("alignment") if isinstance(sprite_meta.get("alignment"), dict) else None
    alignment = {
        "version": version,
        "coordinate_space": "effective_frame_size",
        "unit": "pixel",
        "active": True,
        "fps": fps,
        "gif_export": bool(payload.gif_export),
        "frame_size": {"width": frame_size[0], "height": frame_size[1]},
        "frames": [
            {"index": index, "offset_x": offset[0], "offset_y": offset[1], "scale": scales.get(index, 1.0)}
            for index, offset in sorted(offsets.items())
        ],
        "source_outputs": original_outputs,
        "previous_alignment": original_alignment,
    }

    sequence = sprite_meta.get("sequence") if isinstance(sprite_meta.get("sequence"), dict) else {}
    sequence = dict(sequence)
    sequence.update({
        "type": "sequence_frames",
        "frame_count": len(aligned_meta),
        "fps": fps,
        "duration_ms": duration_ms,
        "effective_frame_size": {"width": frame_size[0], "height": frame_size[1]},
        "sheet_size": {"width": frame_size[0] * len(aligned_meta), "height": frame_size[1]},
        "playback_source": _rel(sheet_path, run_dir),
        "alignment": alignment,
        "frames": [
            {
                "index": item["index"],
                "name": f"frame_{int(item['index']):03d}",
                "file": item["path"],
                "raw_file": item.get("raw_path"),
                "reference_file": item.get("reference_path"),
                "sheet_rect": item["sheet_rect"],
                "action_phase": item.get("action_phase"),
                "bbox": item.get("bbox"),
                "alignment_offset": item.get("alignment_offset"),
                "alignment_scale": item.get("alignment_scale"),
            }
            for item in aligned_meta
        ],
    })
    _write_json(sequence_path, sequence)
    _write_json(alignment_path, alignment)

    sprite_meta["frames"] = aligned_meta
    sprite_meta["horizontal_sheet"] = _rel(sheet_path, run_dir)
    sprite_meta["sequence_json"] = _rel(sequence_path, run_dir)
    sprite_meta["gif"] = gif_rel
    sprite_meta["fps"] = fps
    sprite_meta["duration_ms"] = duration_ms
    sprite_meta["alignment"] = alignment
    sprite_meta["sequence"] = sequence
    versions = sprite_meta.get("alignment_versions")
    if not isinstance(versions, list):
        versions = []
    versions.append({"version": version, "path": _rel(alignment_path, run_dir), "sprite_sheet": _rel(sheet_path, run_dir), "sequence_json": _rel(sequence_path, run_dir), "sprite_gif": gif_rel})
    sprite_meta["alignment_versions"] = versions[-12:]
    meta["sprite"] = sprite_meta
    outputs = dict(original_outputs)
    outputs.update({
        "sprite_frames": _rel(aligned_frames_dir, run_dir),
        "sprite_sheet": _rel(sheet_path, run_dir),
        "sequence_json": _rel(sequence_path, run_dir),
        "sprite_gif": gif_rel,
        "pixelized": _rel(sheet_path, run_dir),
        "preview": gif_rel,
        "alignment": _rel(alignment_path, run_dir),
    })
    meta["outputs"] = outputs
    _write_json(meta_path, meta)

    output.pixelized_path = str(sheet_path)
    output.preview_path = str(gif_path) if gif_rel else None
    return job
