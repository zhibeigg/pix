"""单图序列帧（mosaic）生成流水线。

一次 API 调用直接输出 rows×cols 的 sprite sheet，再按格切图、复用现有的
perfect-pixel + chroma-key + 共享调色板后处理流程。

与 sprite.py 的逐帧（iterative）模式互补：
- mosaic：1 次生图，便宜快，能表达"每行一个动作循环"的语义。
- iterative：N 次生图，闭环和细节更稳定。
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager

import numpy as np
from PIL import Image

from pix import __version__
from pix.api.image_gen import edit_image, generate_image
from pix.api.prompt_guard import PromptPolicyError, RAW_IMAGE_PROMPT_MAX_CHARS, validate_user_prompt
from pix.cache import Cache
from pix.config import AppConfig
from pix.contact_sheet import parse_hex_color, resolve_key_color
from pix.io_utils import new_run_dir, sha256_of_file
from pix.pixelize.bg_removal import remove_background, remove_translucent_edge_halo
from pix.pixelize.core import PixelizeParams
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.sprite import (
    SpriteFrame,
    SpritePipelineResult,
    _apply_shared_palette,
    _ceil_to_multiple,
    _paste_content_to_canvas,
    _rel,
    _sprite_bg_removal_options,
    _visible_bbox,
    compose_gif,
    compose_horizontal_sprite_sheet,
)


LocalStageContext = Callable[[], ContextManager[None]]
ProgressCb = Any


# ---- 输入 / 输出 ----


@dataclass
class SpriteMosaicInput:
    """单图序列帧输入。"""

    prompt: str
    rows: int
    cols: int
    row_prompts: list[str] = field(default_factory=list)
    reference_image_path: Path | None = None
    image_size: str | None = None
    image_quality: str | None = None
    image_model: str | None = None
    pixelize_params: PixelizeParams = field(default_factory=PixelizeParams)
    out_root: str | Path | None = None
    use_cache: bool = True
    refresh_cache: bool = False
    fps: int = 8
    duration_ms: int | None = None
    loop: int | None = None
    gif_export: bool | None = None
    key_tolerance: int | None = None
    billing: dict[str, Any] | None = None
    local_stage_context: LocalStageContext | None = None


@dataclass(frozen=True)
class _MosaicSettings:
    rows: int
    cols: int
    frame_count: int
    fps: int
    duration_ms: int
    loop: int
    target_size: tuple[int, int]
    sheet_pixel_size: tuple[int, int]
    api_size: str
    api_size_pixel: tuple[int, int]
    frame_size_step: int
    gif_export: bool
    anchor: str
    key_color: str
    key_tolerance: int
    max_colors: int
    image_quality: str
    image_model: str | None
    use_reference: bool


# ---- 工具 ----


def _noop(_step: str, _payload: dict) -> None:
    pass


def _local_stage(factory: LocalStageContext | None) -> ContextManager[None]:
    return factory() if factory is not None else nullcontext()


def _ensure_row_prompts(row_prompts: list[str], rows: int, fallback: str) -> list[str]:
    """确保 row_prompts 长度等于 rows；不足的用 fallback 补齐。"""
    items: list[str] = []
    for index in range(rows):
        text = ""
        if index < len(row_prompts):
            text = (row_prompts[index] or "").strip()
        if not text:
            text = fallback.strip()
        items.append(text)
    return items


def _format_row_block(row_prompts: list[str]) -> str:
    return "\n".join(f"Row {index + 1}: {phase}" for index, phase in enumerate(row_prompts))


_SUPPORTED_API_SIZES: tuple[tuple[int, int], ...] = (
    (1024, 1024),
    (1024, 1536),
    (1536, 1024),
    (1536, 1536),
    (2048, 2048),
    (2048, 1536),
    (1536, 2048),
)


def _pick_api_size(sheet_pixel_size: tuple[int, int], explicit: str | None) -> tuple[str, tuple[int, int]]:
    """根据整图像素挑选最近且不小于其总像素的 API 尺寸档。

    - 如果用户/配置显式给了 size 字符串（且不是 auto），原样使用。
    - 否则在内置档位中挑面积最接近且 ≥ 实际整图面积的那一档。
    - 都不满足时退回 1024x1024。
    """
    if explicit and explicit.strip().lower() not in {"", "auto"}:
        return explicit.strip(), sheet_pixel_size
    target_pixels = max(1, sheet_pixel_size[0]) * max(1, sheet_pixel_size[1])
    candidates = sorted(_SUPPORTED_API_SIZES, key=lambda wh: wh[0] * wh[1])
    for w, h in candidates:
        if w * h >= target_pixels:
            return f"{w}x{h}", (w, h)
    w, h = candidates[-1]
    return f"{w}x{h}", (w, h)


def _normalize_pixelize_size(value: Any, fallback: tuple[int, int]) -> tuple[int, int]:
    if not value:
        return fallback
    try:
        return max(1, int(value[0])), max(1, int(value[1]))
    except (TypeError, ValueError, IndexError):
        return fallback


def _resolve_settings(cfg: AppConfig, inputs: SpriteMosaicInput, description: str) -> _MosaicSettings:
    sprite = cfg.sprite
    max_rows = max(1, int(getattr(sprite, "max_grid_rows", 8)))
    max_cols = max(1, int(getattr(sprite, "max_grid_cols", 8)))
    rows = max(1, min(max_rows, int(inputs.rows or sprite.rows or 1)))
    cols = max(1, min(max_cols, int(inputs.cols or sprite.cols or 1)))
    frame_count = rows * cols
    if frame_count < 1:
        raise ValueError("rows × cols 必须 ≥ 1")

    target_size = _normalize_pixelize_size(inputs.pixelize_params.output_size, tuple(sprite.pixel_size))
    sheet_pixel_size = (target_size[0] * cols, target_size[1] * rows)
    api_size, api_size_pixel = _pick_api_size(sheet_pixel_size, inputs.image_size or cfg.image_gen.size)

    fps = max(1, int(inputs.fps or sprite.fps))
    duration_ms = max(20, int(inputs.duration_ms if inputs.duration_ms is not None else round(1000 / fps)))
    loop = int(sprite.loop if inputs.loop is None else inputs.loop)
    gif_export = bool(sprite.gif_export if inputs.gif_export is None else inputs.gif_export)

    key_hex, _ = resolve_key_color(sprite.green_screen_color, description)
    key_tolerance = int(sprite.green_screen_tolerance if inputs.key_tolerance is None else inputs.key_tolerance)
    max_colors = int(inputs.pixelize_params.colors or sprite.colors)

    image_quality = str(inputs.image_quality or sprite.image_quality)
    image_model = inputs.image_model or None

    return _MosaicSettings(
        rows=rows,
        cols=cols,
        frame_count=frame_count,
        fps=fps,
        duration_ms=duration_ms,
        loop=loop,
        target_size=target_size,
        sheet_pixel_size=sheet_pixel_size,
        api_size=api_size,
        api_size_pixel=api_size_pixel,
        frame_size_step=max(1, int(getattr(sprite, "frame_size_step", 16))),
        gif_export=gif_export,
        anchor=str(getattr(sprite, "anchor", "bottom_center") or "bottom_center"),
        key_color=key_hex,
        key_tolerance=key_tolerance,
        max_colors=max_colors,
        image_quality=image_quality,
        image_model=image_model,
        use_reference=inputs.reference_image_path is not None,
    )


# ---- prompt 构造 ----


def build_mosaic_prompt(
    cfg: AppConfig,
    description: str,
    *,
    rows: int,
    cols: int,
    row_prompts: list[str],
    sheet_pixel_size: tuple[int, int],
    frame_pixel_size: tuple[int, int],
    key_color: str,
    key_tolerance: int,
    max_colors: int,
    use_reference: bool,
) -> str:
    """组装单图 sprite sheet 的 prompt。"""
    sprite_cfg = cfg.sprite
    base_template = (getattr(sprite_cfg, "mosaic_prompt_template", "") or "").strip()
    reference_template = (getattr(sprite_cfg, "mosaic_reference_prompt_template", "") or "").strip()
    safe_row_prompts = _ensure_row_prompts(row_prompts, rows, description)
    values = {
        "description": description.strip(),
        "rows": int(rows),
        "cols": int(cols),
        "frame_count": int(rows * cols),
        "frame_width": int(frame_pixel_size[0]),
        "frame_height": int(frame_pixel_size[1]),
        "sheet_width": int(sheet_pixel_size[0]),
        "sheet_height": int(sheet_pixel_size[1]),
        "row_block": _format_row_block(safe_row_prompts),
        "green": key_color,
        "key_color": key_color,
        "key_tolerance": int(key_tolerance),
        "max_colors": int(max_colors),
        "colors": int(max_colors),
    }
    base_prompt = ""
    if base_template:
        try:
            base_prompt = base_template.format(**values).strip()
        except Exception:  # noqa: BLE001 - 模板缺占位符时退回兜底
            base_prompt = ""
    if not base_prompt:
        base_prompt = _fallback_mosaic_prompt(**values)

    if not use_reference:
        return base_prompt

    if reference_template:
        try:
            return reference_template.format(base_template=base_prompt, **values).strip()
        except Exception:  # noqa: BLE001
            pass
    return _fallback_mosaic_reference_prompt(base_prompt, **values)


def _fallback_mosaic_prompt(**values: Any) -> str:
    return (
        "Create a TRUE pixel-art sprite sheet for the following subject. "
        f"Subject: {values['description']}. "
        f"Layout: an exact {values['rows']}x{values['cols']} grid of sprites, read left-to-right then top-to-bottom. "
        f"Total canvas: {values['sheet_width']}x{values['sheet_height']} pixels. "
        f"Each cell is exactly {values['frame_width']}x{values['frame_height']} pixels and aligned to the grid. "
        f"Each row is one independent animation loop with {values['cols']} frames, listed below:\n{values['row_block']}\n"
        "Character/subject consistency: keep the same identity, palette, outline thickness, scale, and proportions across every cell. "
        f"Background: use pure solid key-color {values['green']} for ALL empty/background pixels for chroma-key removal; "
        f"keep visible colors outside the maximum key-color tolerance ({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        f"Use no more than {values['max_colors']} visible subject colors; background color does not count. "
        "Style: crisp pixel art, hard edges, limited palette, no painterly blending, no anti-aliased soft brush. Every pixel must be a perfect square aligned to the grid. "
        f"Do not add text, watermark, UI, border, grid lines, labels, numbers, or shadows outside the subject. Do not draw extra frames outside the {values['rows']}x{values['cols']} grid."
    )


def _fallback_mosaic_reference_prompt(base_prompt: str, **values: Any) -> str:
    _ = values
    return (
        "Re-create the sprite sheet described below based on the provided reference image as the character source. "
        "The reference image defines the core character design (silhouette, palette, costume, proportions). "
        "Reuse the reference character identity in EVERY cell; only the action/pose changes per cell.\n\n"
        f"{base_prompt}\n\n"
        "Strictly preserve the reference character's identity, color palette, and proportions across every cell."
    )


# ---- pipeline 步骤 ----


def _generate_or_load_sheet(
    cfg: AppConfig,
    cache: Cache,
    settings: _MosaicSettings,
    *,
    prompt: str,
    raw_path: Path,
    material: dict[str, Any],
    refresh_cache: bool,
    reference_image_path: Path | None,
) -> str:
    """生成或读取整张 sprite sheet 原图。"""
    cache_kind = "sprite_mosaic_imageedit" if reference_image_path is not None else "sprite_mosaic_imagegen"
    cached = None if refresh_cache else cache.lookup(cache_kind, material, "png")
    if cached is not None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(cached.read_bytes())
        return "cache"

    if reference_image_path is not None:
        edit_image(
            cfg,
            reference_image_path,
            prompt,
            raw_path,
            size=settings.api_size,
            quality=settings.image_quality,
            model=settings.image_model,
            input_fidelity=cfg.image_gen.edit_input_fidelity,
        )
    else:
        generate_image(
            cfg,
            prompt,
            raw_path,
            size=settings.api_size,
            quality=settings.image_quality,
            model=settings.image_model,
        )
    cache.store_copy(cache_kind, material, "png", raw_path)
    return "edited" if reference_image_path is not None else "generated"


def _split_sheet_to_cells(
    sheet_path: Path,
    *,
    rows: int,
    cols: int,
    key_rgb: tuple[int, int, int],
    key_tolerance: int,
) -> tuple[list[Image.Image], dict[str, Any]]:
    """按 rows×cols 切图。

    优先使用"前景像素列/行投影"在每条等分线附近找最稀疏（最像间隙）的位置作为切线，
    避免主体溢出隔壁单元被错误归并。当主体填满全图、无明显空白时退化回等分切。

    返回 (cells, meta)，cells 长度 == rows*cols；meta 含两条切分线列表，便于排查。
    """
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    with Image.open(sheet_path) as opened:
        image = opened.convert("RGBA")
    rgba = np.asarray(image)
    if rgba.shape[-1] == 4:
        alpha = rgba[..., 3]
        # 仅当 alpha 通道已经被预先抠透明（存在显著透明像素）时，才把它作为前景判据；
        # 否则（生图原图 alpha=255 全不透明）一律改用与 key_color 的距离判断，
        # 否则会把整张含背景的图当成前景，投影找不到任何空白柱。
        has_meaningful_alpha = bool(((alpha > 8) & (alpha < 248)).any() or (alpha < 8).any())
        if has_meaningful_alpha:
            fg_mask = alpha > 8
        else:
            fg_mask = _key_color_foreground_mask(rgba[..., :3], key_rgb, key_tolerance)
    else:
        fg_mask = _key_color_foreground_mask(rgba[..., :3], key_rgb, key_tolerance)

    height, width = fg_mask.shape
    row_splits = _projection_splits(fg_mask.sum(axis=1), height, safe_rows)
    cells: list[Image.Image] = []
    per_row_col_splits: list[list[int]] = []
    for row_index in range(safe_rows):
        top = row_splits[row_index]
        bottom = row_splits[row_index + 1]
        if bottom <= top:
            top, bottom = row_splits[row_index], min(height, row_splits[row_index] + 1)
        # 行带内的列投影：仅对该行的前景做投影，避免别行干扰
        col_proj = fg_mask[top:bottom, :].sum(axis=0).astype(np.int64) if bottom > top else np.zeros(width, dtype=np.int64)
        col_splits = _projection_splits(col_proj, width, safe_cols)
        per_row_col_splits.append(col_splits.tolist())
        for col_index in range(safe_cols):
            left = col_splits[col_index]
            right = col_splits[col_index + 1]
            if right <= left:
                left, right = col_splits[col_index], min(width, col_splits[col_index] + 1)
            cells.append(image.crop((int(left), int(top), int(right), int(bottom))).convert("RGBA"))
    meta = {
        "image_size": [int(width), int(height)],
        "row_splits": row_splits.tolist(),
        "col_splits_per_row": per_row_col_splits,
        "method": "foreground_projection_minimum",
    }
    return cells, meta


def _key_color_foreground_mask(rgb: np.ndarray, key_rgb: tuple[int, int, int], tolerance: int) -> np.ndarray:
    """返回与 key_color 的欧氏距离大于 tolerance 的像素 mask（即前景）。"""
    if rgb.size == 0:
        return np.zeros(rgb.shape[:2], dtype=bool)
    diff = rgb.astype(np.int32) - np.array(key_rgb, dtype=np.int32).reshape(1, 1, 3)
    dist_sq = (diff * diff).sum(axis=2)
    threshold_sq = max(0, int(tolerance)) ** 2
    return dist_sq > threshold_sq


def _projection_splits(projection: np.ndarray, total: int, segments: int) -> np.ndarray:
    """根据 1D 投影找 `segments+1` 条切分线（含 0 与 total）。

    在每条理论等分线附近的搜索窗口内挑前景像素最少的位置；如果窗口内有多个并列最小值，
    取最靠近等分线的那个，保证切分线单调递增。
    """
    safe_segments = max(1, int(segments))
    if safe_segments == 1 or total <= safe_segments:
        return np.array([int(round(i * total / safe_segments)) for i in range(safe_segments + 1)], dtype=np.int64)

    proj = np.asarray(projection, dtype=np.int64)
    if proj.size != total:
        # 维度不匹配时退化
        return np.array([int(round(i * total / safe_segments)) for i in range(safe_segments + 1)], dtype=np.int64)

    cell_size = total / safe_segments
    # 搜索半径：cell 的 40%，至少 2 像素，让模型轻微出格也能被纠正
    search_radius = max(2, int(round(cell_size * 0.4)))

    splits: list[int] = [0]
    for i in range(1, safe_segments):
        ideal = i * cell_size
        lo = max(splits[-1] + 1, int(round(ideal - search_radius)))
        hi = min(total - (safe_segments - i), int(round(ideal + search_radius)))
        if hi <= lo:
            splits.append(int(round(ideal)))
            continue
        window = proj[lo:hi]
        min_val = int(window.min())
        # 取窗口内所有最小值索引中，距离 ideal 最近的那个
        candidate_indices = np.flatnonzero(window == min_val) + lo
        # 转 float 以避免有符号差
        best = int(candidate_indices[np.abs(candidate_indices - ideal).argmin()])
        splits.append(max(splits[-1] + 1, best))
    splits.append(int(total))
    return np.asarray(splits, dtype=np.int64)


def _extract_cell_content(
    cfg: AppConfig,
    cell: Image.Image,
    *,
    target_size: tuple[int, int],
    key_tolerance: int,
    generated_preprocess_method: str | None,
) -> tuple[Image.Image, tuple[int, int, int, int] | None, dict[str, Any]]:
    """对单个 cell 做 perfect-pixel + chroma-key + bbox 抠出。"""
    preprocessed = preprocess_generated_image(
        cell,
        method=generated_preprocess_method,
        target_size=target_size,
    )
    image = preprocessed.image.convert("RGBA")
    alpha = remove_background(
        image,
        tolerance=max(0, int(key_tolerance)),
        feather=0,
        edge_style="hard",
        keep_border_bleed=True,
        **_sprite_bg_removal_options(cfg, tolerance=key_tolerance),
    )
    alpha = remove_translucent_edge_halo(alpha)
    bbox = _visible_bbox(alpha)
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), None, {
            "preprocess": preprocessed.meta,
            "bbox": None,
            "alpha_size": list(alpha.size),
        }
    content = alpha.crop(bbox).convert("RGBA")
    return content, bbox, {
        "preprocess": preprocessed.meta,
        "alpha_size": list(alpha.size),
        "bbox": list(bbox),
        "content_size": list(content.size),
    }


# ---- 主入口 ----


def run_sprite_mosaic_pipeline(
    cfg: AppConfig,
    inputs: SpriteMosaicInput,
    progress: ProgressCb | None = None,
) -> SpritePipelineResult:
    """执行单图序列帧 pipeline：1 次生图 → 切图 → 后处理 → 横向 sheet + sequence.json。"""

    notify = progress or _noop
    if not (inputs.prompt or "").strip():
        raise ValueError("序列帧任务需要 prompt")

    out_root = Path(inputs.out_root or cfg.output.root)
    run_dir = new_run_dir(out_root, seed=f"mosaic\n{inputs.prompt}")
    notify("sprite_run_start", {"run_dir": str(run_dir), "mode": "mosaic"})

    # 1. 审核（含主体描述 + 行描述合并文本）
    row_prompts_raw = list(inputs.row_prompts or [])
    guard_text = "\n".join([inputs.prompt, *(p for p in row_prompts_raw if p)]).strip()
    try:
        guard = validate_user_prompt(
            cfg,
            guard_text,
            allow_template_break=True,
            max_chars=RAW_IMAGE_PROMPT_MAX_CHARS,
        )
    except PromptPolicyError as exc:
        notify("prompt_guard_rejected", exc.result.to_metadata())
        raise ValueError(str(exc)) from exc
    prompt_guard_meta = guard.to_metadata()
    description = guard.normalized_description or inputs.prompt
    notify("prompt_guard_ready", prompt_guard_meta)

    settings = _resolve_settings(cfg, inputs, description)
    safe_row_prompts = _ensure_row_prompts(row_prompts_raw, settings.rows, description)

    # 2. 组装 prompt
    effective_prompt = build_mosaic_prompt(
        cfg,
        description,
        rows=settings.rows,
        cols=settings.cols,
        row_prompts=safe_row_prompts,
        sheet_pixel_size=settings.sheet_pixel_size,
        frame_pixel_size=settings.target_size,
        key_color=settings.key_color,
        key_tolerance=settings.key_tolerance,
        max_colors=settings.max_colors,
        use_reference=settings.use_reference,
    )

    # 3. 写 debug 文件（提交前先写一份基础信息，pipeline 失败时仍可读到）
    debug_path = run_dir / "00_input.txt"
    _write_mosaic_debug(
        debug_path,
        raw_prompt=inputs.prompt,
        normalized_description=description,
        settings=settings,
        row_prompts=safe_row_prompts,
        effective_prompt=effective_prompt,
        billing=inputs.billing,
        reference_image=inputs.reference_image_path,
    )

    # 4. 生图
    raw_dir = run_dir / "frames" / "raw"
    final_dir = run_dir / "frames" / "final"
    sheet_raw_path = run_dir / "sprite_mosaic.png"
    sheet_path = run_dir / "sprite_sheet.png"
    sequence_path = run_dir / "sequence.json"
    gif_path = run_dir / "sprite.gif"
    cache = Cache(cfg.cache.dir, enabled=cfg.cache.enabled and inputs.use_cache)

    cache_material: dict[str, Any] = {
        "prompt": effective_prompt,
        "user_prompt": inputs.prompt,
        "row_prompts": safe_row_prompts,
        "rows": settings.rows,
        "cols": settings.cols,
        "frame_size": list(settings.target_size),
        "sheet_size": list(settings.sheet_pixel_size),
        "api_size": settings.api_size,
        "quality": settings.image_quality,
        "model": settings.image_model or cfg.image_gen.model,
        "output_format": cfg.image_gen.output_format,
        "use_reference": settings.use_reference,
    }
    if inputs.reference_image_path is not None:
        cache_material["reference_sha256"] = sha256_of_file(inputs.reference_image_path)

    with _local_stage(inputs.local_stage_context):
        notify("sprite_mosaic_generation_start", {
            "rows": settings.rows,
            "cols": settings.cols,
            "frame_count": settings.frame_count,
            "api_size": settings.api_size,
            "use_reference": settings.use_reference,
        })
        mode = _generate_or_load_sheet(
            cfg,
            cache,
            settings,
            prompt=effective_prompt,
            raw_path=sheet_raw_path,
            material=cache_material,
            refresh_cache=inputs.refresh_cache,
            reference_image_path=inputs.reference_image_path,
        )
        notify("sprite_mosaic_generation_ready", {"mode": mode, "sheet": str(sheet_raw_path)})

        # 5. 切图（基于前景像素投影找最佳切分线，避免主体溢出隔壁单元被错误归并）
        key_rgb = parse_hex_color(settings.key_color)
        cells, split_meta = _split_sheet_to_cells(
            sheet_raw_path,
            rows=settings.rows,
            cols=settings.cols,
            key_rgb=key_rgb,
            key_tolerance=settings.key_tolerance,
        )
        notify("sprite_mosaic_split", split_meta)
        raw_dir.mkdir(parents=True, exist_ok=True)
        contents: list[Image.Image] = []
        bboxes: list[tuple[int, int, int, int] | None] = []
        cell_meta: list[dict[str, Any]] = []
        for cell_index, cell in enumerate(cells, start=1):
            raw_cell_path = raw_dir / f"frame_{cell_index:03d}.png"
            cell.save(raw_cell_path)
            content, bbox, meta = _extract_cell_content(
                cfg,
                cell,
                target_size=settings.target_size,
                key_tolerance=settings.key_tolerance,
                generated_preprocess_method=inputs.pixelize_params.generated_preprocess_method,
            )
            contents.append(content)
            bboxes.append(bbox)
            cell_meta.append(meta)
            notify("sprite_mosaic_cell_ready", {
                "index": cell_index,
                "bbox": list(bbox) if bbox else None,
                "content_size": list(content.size),
            })

        if not any(bbox is not None for bbox in bboxes):
            raise ValueError("整张 mosaic 切图后没有任何可见主体；请检查抠色配置或 prompt")

        # 6. 共享调色板 + 贴齐画布
        max_w = max(content.width for content in contents) if contents else 1
        max_h = max(content.height for content in contents) if contents else 1
        effective_size = (
            _ceil_to_multiple(max(settings.target_size[0], max_w), settings.frame_size_step),
            _ceil_to_multiple(max(settings.target_size[1], max_h), settings.frame_size_step),
        )
        canvases = [
            _paste_content_to_canvas(content, size=effective_size, anchor=settings.anchor)
            for content in contents
        ]
        shared_palette_hex: list[str] = []
        if cfg.sprite.shared_palette:
            canvases, shared_palette_hex = _apply_shared_palette(
                canvases,
                colors=settings.max_colors,
                dither=inputs.pixelize_params.dither,
            )

        # 7. 落盘最终单帧 + 横向 sheet（用于旧版预览组件）
        final_dir.mkdir(parents=True, exist_ok=True)
        frames: list[SpriteFrame] = []
        frame_paths: list[Path] = []
        for cell_index, image in enumerate(canvases, start=1):
            path = final_dir / f"frame_{cell_index:03d}.png"
            image.save(path)
            frame_paths.append(path)
            row_index = (cell_index - 1) // settings.cols
            col_index = (cell_index - 1) % settings.cols
            sheet_rect = {
                "x": (cell_index - 1) * effective_size[0],
                "y": 0,
                "w": effective_size[0],
                "h": effective_size[1],
            }
            frames.append(
                SpriteFrame(
                    index=cell_index,
                    raw_path=raw_dir / f"frame_{cell_index:03d}.png",
                    reference_path=raw_dir / f"frame_{cell_index:03d}.png",
                    path=path,
                    sheet_rect=sheet_rect,
                    action_phase=safe_row_prompts[row_index] if row_index < len(safe_row_prompts) else "",
                    bbox=bboxes[cell_index - 1],
                )
            )
            # 修正 SpriteFrame.row/col：默认实现按横向单行，mosaic 模式额外保留二维信息
            # 读取时通过 to_metadata 输出 row/col；这里不能改 frozen dataclass 字段，
            # 在写元数据阶段单独覆盖 row/col。

        compose_horizontal_sprite_sheet(frame_paths, sheet_path)

        preview_path: Path | None = None
        if settings.gif_export:
            compose_gif(frame_paths, gif_path, duration_ms=settings.duration_ms, loop=settings.loop)
            preview_path = gif_path

        notify("sprite_mosaic_outputs_ready", {
            "sheet": str(sheet_path),
            "mosaic_sheet": str(sheet_raw_path),
            "sequence": str(sequence_path),
            "gif": str(preview_path) if preview_path else None,
        })

    # 8. sequence.json + meta.json
    sequence = _build_sequence_json(
        sequence_path,
        run_dir=run_dir,
        frames=frames,
        settings=settings,
        effective_size=effective_size,
        sheet_path=sheet_path,
        mosaic_sheet_path=sheet_raw_path,
        row_prompts=safe_row_prompts,
        billing=inputs.billing,
    )

    _write_mosaic_debug(
        debug_path,
        raw_prompt=inputs.prompt,
        normalized_description=description,
        settings=settings,
        row_prompts=safe_row_prompts,
        effective_prompt=effective_prompt,
        billing=inputs.billing,
        reference_image=inputs.reference_image_path,
        effective_frame_size=effective_size,
    )

    meta = {
        "version": __version__,
        "input": {
            "prompt": inputs.prompt,
            "row_prompts": safe_row_prompts,
            "effective_prompt": effective_prompt,
        },
        "prompt_guard": prompt_guard_meta,
        "image_gen": {
            "model": settings.image_model or cfg.image_gen.model,
            "size": settings.api_size,
            "quality": settings.image_quality,
            "output_format": cfg.image_gen.output_format,
            "input_fidelity": cfg.image_gen.edit_input_fidelity,
            "used": True,
            "mode": "sprite_mosaic",
            "use_reference": settings.use_reference,
        },
        "sprite": {
            "type": "sequence_frames",
            "mode": "mosaic",
            "generation_mode": "mosaic",
            "rows": settings.rows,
            "cols": settings.cols,
            "frame_count": settings.frame_count,
            "max_frame_count": int(getattr(cfg.sprite, "max_frame_count", 64)),
            "fps": settings.fps,
            "duration_ms": settings.duration_ms,
            "loop": settings.loop,
            "target_frame_size": list(settings.target_size),
            "effective_frame_size": list(effective_size),
            "sheet_size": [effective_size[0] * len(frames), effective_size[1]],
            "mosaic_sheet_size": list(settings.sheet_pixel_size),
            "api_size": settings.api_size,
            "colors": settings.max_colors,
            "anchor": settings.anchor,
            "green_screen_color": settings.key_color,
            "green_screen_tolerance": settings.key_tolerance,
            "shared_palette": bool(cfg.sprite.shared_palette),
            "shared_palette_colors": shared_palette_hex,
            "split": split_meta,
            "row_prompts": safe_row_prompts,
            "raw_frames_dir": _rel(raw_dir, run_dir),
            "frames_dir": _rel(final_dir, run_dir),
            "horizontal_sheet": sheet_path.name,
            "mosaic_sheet": sheet_raw_path.name,
            "sequence_json": sequence_path.name,
            "gif": gif_path.name if settings.gif_export else None,
            "frames": [_frame_metadata(frame, run_dir, cols=settings.cols, cell_meta=cell_meta) for frame in frames],
            "sequence": sequence,
            "billing": inputs.billing or None,
            "use_reference": settings.use_reference,
        },
        "cache": {"enabled": cache.enabled, "refresh": inputs.refresh_cache},
        "outputs": {
            "source": _rel(sheet_raw_path, run_dir),
            "sprite_frames": _rel(final_dir, run_dir),
            "sprite_sheet": sheet_path.name,
            "sprite_mosaic": sheet_raw_path.name,
            "sequence_json": sequence_path.name,
            "sprite_gif": gif_path.name if settings.gif_export else None,
            "pixelized": sheet_path.name,
            "preview": gif_path.name if settings.gif_export else None,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return SpritePipelineResult(
        run_dir=run_dir,
        source_path=sheet_raw_path,
        frame_paths=frame_paths,
        pixel_path=sheet_path,
        preview_path=preview_path,
        meta_path=meta_path,
        meta=meta,
    )


def _frame_metadata(
    frame: SpriteFrame,
    run_dir: Path,
    *,
    cols: int,
    cell_meta: list[dict[str, Any]],
) -> dict[str, Any]:
    base = frame.to_metadata(run_dir)
    safe_cols = max(1, int(cols))
    grid_row = (frame.index - 1) // safe_cols
    grid_col = (frame.index - 1) % safe_cols
    base["row"] = grid_row
    base["col"] = grid_col
    base["grid_row"] = grid_row
    base["grid_col"] = grid_col
    if 0 < frame.index <= len(cell_meta):
        base["cell"] = cell_meta[frame.index - 1]
    return base


def _build_sequence_json(
    path: Path,
    *,
    run_dir: Path,
    frames: list[SpriteFrame],
    settings: _MosaicSettings,
    effective_size: tuple[int, int],
    sheet_path: Path,
    mosaic_sheet_path: Path,
    row_prompts: list[str],
    billing: dict[str, Any] | None,
) -> dict[str, Any]:
    sheet_size = (effective_size[0] * len(frames), effective_size[1])
    sequence = {
        "type": "sequence_frames",
        "mode": "mosaic",
        "frame_count": len(frames),
        "rows": settings.rows,
        "cols": settings.cols,
        "fps": settings.fps,
        "duration_ms": settings.duration_ms,
        "loop": settings.loop == 0,
        "target_frame_size": {"width": settings.target_size[0], "height": settings.target_size[1]},
        "effective_frame_size": {"width": effective_size[0], "height": effective_size[1]},
        "sheet_size": {"width": sheet_size[0], "height": sheet_size[1]},
        "mosaic_sheet_size": {"width": settings.sheet_pixel_size[0], "height": settings.sheet_pixel_size[1]},
        "anchor": settings.anchor,
        "row_prompts": list(row_prompts),
        "playback_source": _rel(sheet_path, run_dir),
        "mosaic_source": _rel(mosaic_sheet_path, run_dir),
        "billing": billing or None,
        "frames": [
            {
                "index": frame.index,
                "name": f"frame_{frame.index:03d}",
                "file": _rel(frame.path, run_dir),
                "raw_file": _rel(frame.raw_path, run_dir),
                "sheet_rect": dict(frame.sheet_rect),
                "grid_row": (frame.index - 1) // max(1, settings.cols),
                "grid_col": (frame.index - 1) % max(1, settings.cols),
                "action_phase": frame.action_phase,
                "bbox": list(frame.bbox) if frame.bbox else None,
            }
            for frame in frames
        ],
    }
    path.write_text(json.dumps(sequence, ensure_ascii=False, indent=2), encoding="utf-8")
    return sequence


def _write_mosaic_debug(
    path: Path,
    *,
    raw_prompt: str,
    normalized_description: str,
    settings: _MosaicSettings,
    row_prompts: list[str],
    effective_prompt: str,
    billing: dict[str, Any] | None,
    reference_image: Path | None,
    effective_frame_size: tuple[int, int] | None = None,
) -> None:
    effective = effective_frame_size or settings.target_size
    parts = [
        "[mode]",
        "generation_mode = mosaic",
        "",
        "[raw_prompt]",
        raw_prompt,
        "",
        "[normalized_description]",
        normalized_description,
        "",
        "[grid_settings]",
        f"rows = {settings.rows}",
        f"cols = {settings.cols}",
        f"frame_count = {settings.frame_count}",
        f"frame_width = {settings.target_size[0]}",
        f"frame_height = {settings.target_size[1]}",
        f"sheet_width = {settings.sheet_pixel_size[0]}",
        f"sheet_height = {settings.sheet_pixel_size[1]}",
        f"api_size = {settings.api_size}",
        f"effective_frame_width = {effective[0]}",
        f"effective_frame_height = {effective[1]}",
        f"anchor = {settings.anchor}",
        f"green_screen_color = {settings.key_color}",
        f"green_screen_tolerance = {settings.key_tolerance}",
        f"max_colors = {settings.max_colors}",
        f"fps = {settings.fps}",
        f"duration_ms = {settings.duration_ms}",
        f"loop = {settings.loop}",
        f"gif_export = {'true' if settings.gif_export else 'false'}",
        f"image_quality = {settings.image_quality}",
        f"image_model = {settings.image_model or '(default)'}",
        f"use_reference = {'true' if settings.use_reference else 'false'}",
        f"reference_image = {reference_image if reference_image else '(none)'}",
        "",
        "[row_prompts]",
    ]
    parts.extend(f"row_{index + 1} = {phase}" for index, phase in enumerate(row_prompts))
    parts.extend(["", "[billing]"])
    if billing:
        parts.extend(f"{key} = {value}" for key, value in billing.items())
    else:
        parts.append("billing = not_provided")
    parts.extend(["", "[effective_prompt]", effective_prompt])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
