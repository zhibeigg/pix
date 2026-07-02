"""序列帧锚点对齐与本地重合成。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import HTTPException, status
from PIL import Image

from pix.sprite import _apply_shared_palette, compose_gif, compose_grid_sprite_sheet, compose_horizontal_sprite_sheet
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


def _int_or_none(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _sprite_grid(sprite_meta: dict[str, Any], raw_frames: list[Any]) -> tuple[int | None, int | None]:
    sequence = sprite_meta.get("sequence") if isinstance(sprite_meta.get("sequence"), dict) else {}
    rows = _int_or_none(sprite_meta.get("rows")) or _int_or_none(sequence.get("rows"))
    cols = _int_or_none(sprite_meta.get("cols")) or _int_or_none(sequence.get("cols"))
    rows_outputs = sprite_meta.get("rows_outputs")
    if (rows is None or rows <= 0) and isinstance(rows_outputs, list) and rows_outputs:
        rows = len(rows_outputs)
    if (cols is None or cols <= 0) and isinstance(rows_outputs, list):
        for entry in rows_outputs:
            if not isinstance(entry, dict):
                continue
            indices = entry.get("frame_indices")
            if isinstance(indices, list) and indices:
                cols = len(indices)
                break
    if rows is None or rows <= 0 or cols is None or cols <= 0:
        return None, None
    expected = rows * cols
    if expected != len(raw_frames):
        return rows, cols
    return rows, cols


def _frame_grid_position(item: dict[str, Any], frame_index: int, cols: int | None) -> tuple[int, int]:
    if cols and cols > 0:
        return (max(0, frame_index - 1) // cols, max(0, frame_index - 1) % cols)
    row = _int_or_none(item.get("grid_row"))
    if row is None:
        row = _int_or_none(item.get("row"))
    col = _int_or_none(item.get("grid_col"))
    if col is None:
        col = _int_or_none(item.get("col"))
    return row or 0, col if col is not None else max(0, frame_index - 1)


def _row_phase(sprite_meta: dict[str, Any], row_index: int, frame_indices: list[int], frames_by_index: dict[int, dict[str, Any]]) -> str:
    prompts = sprite_meta.get("row_prompts")
    if isinstance(prompts, list) and row_index < len(prompts) and str(prompts[row_index]).strip():
        return str(prompts[row_index]).strip()
    for frame_index in frame_indices:
        phase = frames_by_index.get(frame_index, {}).get("action_phase")
        if isinstance(phase, str) and phase.strip():
            return phase.strip()
    return ""


def _row_entries(sprite_meta: dict[str, Any], rows: int | None, cols: int | None, aligned_meta: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows or rows <= 0:
        return []
    existing = sprite_meta.get("rows_outputs")
    existing_by_row: dict[int, dict[str, Any]] = {}
    if isinstance(existing, list):
        for entry in existing:
            if not isinstance(entry, dict):
                continue
            row_index = _int_or_none(entry.get("row_index"))
            if row_index is not None:
                existing_by_row[row_index] = entry
    frames_by_index = {int(item["index"]): item for item in aligned_meta if isinstance(item.get("index"), int)}
    result: list[dict[str, Any]] = []
    for row_index in range(rows):
        existing_entry = existing_by_row.get(row_index, {})
        raw_indices = existing_entry.get("frame_indices")
        frame_indices = [int(value) for value in raw_indices if _int_or_none(value) is not None] if isinstance(raw_indices, list) else []
        if not frame_indices and cols and cols > 0:
            start = row_index * cols + 1
            frame_indices = list(range(start, start + cols))
        if not frame_indices:
            frame_indices = [int(item["index"]) for item in aligned_meta if _int_or_none(item.get("row")) == row_index]
        phase = str(existing_entry.get("action_phase") or "").strip() or _row_phase(sprite_meta, row_index, frame_indices, frames_by_index)
        result.append({"row_index": row_index, "frame_indices": frame_indices, "action_phase": phase, "sheet": None, "gif": None})
    return result


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


def _payload_colors(payload: SequenceAlignmentRequest) -> int | None:
    try:
        colors = int(payload.colors) if payload.colors is not None else None
    except (TypeError, ValueError):
        return None
    if colors is None:
        return None
    return max(2, min(256, colors))


def _pixelize_dither(job: GenerationJob) -> str:
    params = job.params_json if isinstance(job.params_json, dict) else {}
    pixelize = params.get("pixelize")
    dither = pixelize.get("dither") if isinstance(pixelize, dict) else None
    return "floyd_steinberg" if str(dither).strip().lower() == "floyd_steinberg" else "none"


def _quantize_aligned_frames(images: list[Image.Image], *, colors: int | None, dither: str) -> tuple[list[Image.Image], list[str]]:
    if colors is None:
        return images, []
    quantized, palette = _apply_shared_palette(images, colors=colors, dither=dither)
    return quantized, palette


def _compose_row_outputs(
    sprite_meta: dict[str, Any],
    aligned_meta: list[dict[str, Any]],
    frame_paths_by_index: dict[int, Path],
    *,
    rows: int | None,
    cols: int | None,
    run_dir: Path,
    align_root: Path,
    duration_ms: int,
    loop: int,
    gif_export: bool,
) -> list[dict[str, Any]]:
    rows_outputs: list[dict[str, Any]] = []
    for spec in _row_entries(sprite_meta, rows, cols, aligned_meta):
        row_index = _int_or_none(spec.get("row_index"))
        if row_index is None:
            row_index = len(rows_outputs)
        raw_indices = spec.get("frame_indices")
        frame_indices = [int(value) for value in raw_indices if _int_or_none(value) is not None] if isinstance(raw_indices, list) else []
        row_paths = [frame_paths_by_index[index] for index in frame_indices if index in frame_paths_by_index]
        if not row_paths:
            continue
        sheet_path = align_root / "row_sheets" / f"row_{row_index + 1:02d}.png"
        compose_horizontal_sprite_sheet(row_paths, sheet_path)
        gif_rel: str | None = None
        if gif_export:
            gif_path = align_root / "previews" / f"row_{row_index + 1:02d}.gif"
            compose_gif(row_paths, gif_path, duration_ms=duration_ms, loop=loop)
            gif_rel = _rel(gif_path, run_dir)
        rows_outputs.append({
            "row_index": row_index,
            "frame_indices": frame_indices,
            "action_phase": str(spec.get("action_phase") or "").strip(),
            "sheet": _rel(sheet_path, run_dir),
            "gif": gif_rel,
        })
    return rows_outputs


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
    rows, cols = _sprite_grid(sprite_meta, raw_frames)
    offsets = _frame_offsets(payload)
    scales = _frame_scales(payload)
    color_count = _payload_colors(payload)
    dither = _pixelize_dither(job)
    version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    align_root = run_dir / "alignments" / version
    aligned_frames_dir = align_root / "frames"
    aligned_frames_dir.mkdir(parents=True, exist_ok=True)

    pending_frames: list[dict[str, Any]] = []
    aligned_images: list[Image.Image] = []
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
        row_index, col_index = _frame_grid_position(item, frame_index, cols)
        pending_frames.append({
            "index": frame_index,
            "row": row_index,
            "col": col_index,
            "grid_row": row_index,
            "grid_col": col_index,
            "raw_path": item.get("raw_path"),
            "reference_path": item.get("reference_path"),
            "action_phase": item.get("action_phase"),
            "offset": offset,
            "scale": scale,
        })
        aligned_images.append(aligned)

    if not pending_frames:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="没有可合成的序列帧")

    aligned_images, palette = _quantize_aligned_frames(aligned_images, colors=color_count, dither=dither)
    aligned_frame_paths: list[Path] = []
    aligned_frame_paths_by_index: dict[int, Path] = {}
    aligned_meta: list[dict[str, Any]] = []
    for sheet_position, (item, aligned) in enumerate(zip(pending_frames, aligned_images, strict=False)):
        frame_index = int(item["index"])
        frame_path = aligned_frames_dir / f"frame_{frame_index:03d}.png"
        aligned.save(frame_path)
        aligned_frame_paths.append(frame_path)
        aligned_frame_paths_by_index[frame_index] = frame_path
        bbox = _visible_bbox(aligned)
        sheet_rect = {"x": sheet_position * frame_size[0], "y": 0, "w": frame_size[0], "h": frame_size[1]}
        aligned_meta.append({
            "index": frame_index,
            "row": item.get("row"),
            "col": item.get("col"),
            "grid_row": item.get("grid_row"),
            "grid_col": item.get("grid_col"),
            "raw_path": item.get("raw_path"),
            "reference_path": item.get("reference_path"),
            "path": _rel(frame_path, run_dir),
            "sheet_rect": sheet_rect,
            "action_phase": item.get("action_phase"),
            "bbox": list(bbox) if bbox else None,
            "alignment_offset": {"x": item["offset"][0], "y": item["offset"][1]},
            "alignment_scale": item["scale"],
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
    loop = int(sprite_meta.get("loop") or 0)
    if payload.gif_export:
        compose_gif(aligned_frame_paths, gif_path, duration_ms=duration_ms, loop=loop)
        gif_rel = _rel(gif_path, run_dir)
    rows_outputs = _compose_row_outputs(
        sprite_meta,
        aligned_meta,
        aligned_frame_paths_by_index,
        rows=rows,
        cols=cols,
        run_dir=run_dir,
        align_root=align_root,
        duration_ms=duration_ms,
        loop=loop,
        gif_export=bool(payload.gif_export),
    )
    grid_rel: str | None = None
    if rows and cols and len(aligned_frame_paths) == rows * cols:
        grid_path = align_root / "sprite_sheet_grid.png"
        compose_grid_sprite_sheet(aligned_frame_paths, grid_path, rows=rows, cols=cols, frame_size=frame_size)
        grid_rel = _rel(grid_path, run_dir)

    original_outputs = meta.get("outputs") if isinstance(meta.get("outputs"), dict) else {}
    original_alignment = sprite_meta.get("alignment") if isinstance(sprite_meta.get("alignment"), dict) else None
    alignment = {
        "version": version,
        "coordinate_space": "effective_frame_size",
        "unit": "pixel",
        "active": True,
        "fps": fps,
        "gif_export": bool(payload.gif_export),
        "colors": color_count,
        "palette": palette,
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
        "rows": rows,
        "cols": cols,
        "fps": fps,
        "duration_ms": duration_ms,
        "colors": color_count,
        "palette": palette,
        "effective_frame_size": {"width": frame_size[0], "height": frame_size[1]},
        "sheet_size": {"width": frame_size[0] * len(aligned_meta), "height": frame_size[1]},
        "playback_source": _rel(sheet_path, run_dir),
        "grid_source": grid_rel,
        "rows_outputs": rows_outputs,
        "alignment": alignment,
        "frames": [
            {
                "index": item["index"],
                "name": f"frame_{int(item['index']):03d}",
                "file": item["path"],
                "raw_file": item.get("raw_path"),
                "reference_file": item.get("reference_path"),
                "sheet_rect": item["sheet_rect"],
                "row": item.get("row"),
                "col": item.get("col"),
                "grid_row": item.get("grid_row"),
                "grid_col": item.get("grid_col"),
                "action_phase": item.get("action_phase"),
                "bbox": item.get("bbox"),
                "alignment_offset": item.get("alignment_offset"),
                "alignment_scale": item.get("alignment_scale"),
            }
            for item in aligned_meta
        ],
    })
    if rows_outputs:
        sequence["rows_outputs"] = rows_outputs
    if grid_rel:
        sequence["grid_source"] = grid_rel
    _write_json(sequence_path, sequence)
    _write_json(alignment_path, alignment)

    sprite_meta["frames"] = aligned_meta
    sprite_meta["horizontal_sheet"] = _rel(sheet_path, run_dir)
    if grid_rel:
        sprite_meta["grid_sheet"] = grid_rel
    else:
        sprite_meta.pop("grid_sheet", None)
    sprite_meta["sequence_json"] = _rel(sequence_path, run_dir)
    sprite_meta["gif"] = gif_rel
    sprite_meta["fps"] = fps
    sprite_meta["duration_ms"] = duration_ms
    if color_count is not None:
        sprite_meta["colors"] = color_count
        sprite_meta["palette"] = palette
    sprite_meta["rows_outputs"] = rows_outputs
    sprite_meta["row_sheets_dir"] = _rel(align_root / "row_sheets", run_dir) if any(entry.get("sheet") for entry in rows_outputs) else None
    sprite_meta["row_previews_dir"] = _rel(align_root / "previews", run_dir) if any(entry.get("gif") for entry in rows_outputs) else None
    sprite_meta["alignment"] = alignment
    sprite_meta["sequence"] = sequence
    versions = sprite_meta.get("alignment_versions")
    if not isinstance(versions, list):
        versions = []
    versions.append({"version": version, "path": _rel(alignment_path, run_dir), "sprite_sheet": _rel(sheet_path, run_dir), "sprite_sheet_grid": grid_rel, "sequence_json": _rel(sequence_path, run_dir), "sprite_gif": gif_rel, "rows_outputs": rows_outputs, "colors": color_count, "palette": palette})
    sprite_meta["alignment_versions"] = versions[-12:]
    meta["sprite"] = sprite_meta
    outputs = dict(original_outputs)
    row_sheet_paths = [entry["sheet"] for entry in rows_outputs if entry.get("sheet")]
    row_preview_paths = [entry["gif"] for entry in rows_outputs if entry.get("gif")]
    preview_rel = gif_rel or (row_preview_paths[0] if row_preview_paths else None)
    outputs.update({
        "sprite_frames": _rel(aligned_frames_dir, run_dir),
        "sprite_sheet": _rel(sheet_path, run_dir),
        "sprite_sheet_grid": grid_rel,
        "sequence_json": _rel(sequence_path, run_dir),
        "sprite_gif": gif_rel,
        "row_sheets_dir": sprite_meta.get("row_sheets_dir"),
        "row_previews_dir": sprite_meta.get("row_previews_dir"),
        "row_sheets": row_sheet_paths,
        "row_previews": row_preview_paths,
        "pixelized": _rel(sheet_path, run_dir),
        "preview": preview_rel,
        "alignment": _rel(alignment_path, run_dir),
    })
    if color_count is not None:
        pixelize_meta = meta.get("pixelize") if isinstance(meta.get("pixelize"), dict) else {}
        pixelize_meta = dict(pixelize_meta)
        effective_params = pixelize_meta.get("effective_params") if isinstance(pixelize_meta.get("effective_params"), dict) else {}
        effective_params = dict(effective_params)
        effective_params["colors"] = color_count
        pixelize_meta["effective_params"] = effective_params
        pixelize_meta["alignment_palette"] = palette
        meta["pixelize"] = pixelize_meta
    meta["outputs"] = outputs
    _write_json(meta_path, meta)

    # 同步把用户调整后的 fps / gif_export / colors / 每帧 offset/scale 也写回 job.params_json，
    # 让下次打开编辑器、作品库快览、重试任务都能拿到调整后的值。
    params = dict(job.params_json or {})
    sprite_params = dict(params.get("sprite") or {})
    sprite_params["fps"] = fps
    sprite_params["duration_ms"] = duration_ms
    sprite_params["gif_export"] = bool(payload.gif_export)
    if color_count is not None:
        sprite_params["colors"] = color_count
    sprite_params["alignment_version"] = version
    sprite_params["alignment_frames"] = [
        {"index": index, "offset_x": offset[0], "offset_y": offset[1], "scale": scales.get(index, 1.0)}
        for index, offset in sorted(offsets.items())
    ]
    if color_count is not None:
        pixelize_params = dict(params.get("pixelize") or {})
        pixelize_params["colors"] = color_count
        params["pixelize"] = pixelize_params
    params["sprite"] = sprite_params
    job.params_json = params

    output.pixelized_path = str(sheet_path)
    output.preview_path = str(run_dir / preview_rel) if preview_rel else None
    return job
