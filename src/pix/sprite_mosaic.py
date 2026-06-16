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
from dataclasses import dataclass, field, replace
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
from pix.pixelize.bg_removal import apply_pixel_bg_alpha
from pix.pixelize.core import PixelizeParams
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.sprite import (
    SpriteFrame,
    SpritePipelineResult,
    _apply_shared_palette,
    _ceil_to_multiple,
    _paste_content_to_canvas,
    _rel,
    _visible_bbox,
    compose_gif,
    compose_grid_sprite_sheet,
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
    (2048, 1152),
    (1152, 2048),
    (2048, 1536),
    (1536, 2048),
    (2048, 2048),
    (3840, 2160),
    (2160, 3840),
)


# 模型生图尺寸约束（与 OpenAI gpt-image-2 / 通用图像 API 对齐）：
#   - 长短边都是 16 的倍数
#   - 最大边 ≤ 3840
#   - 长短边比 ≤ 3:1
#   - 总像素 ≥ 655_360 且 ≤ 8_294_400
_API_SIZE_MULTIPLE = 16
_API_SIZE_MAX_SIDE = 3840
_API_SIZE_MAX_RATIO = 3.0
_API_SIZE_MIN_PIXELS = 655_360
_API_SIZE_MAX_PIXELS = 8_294_400
# 每个像素艺术像素至少占多少渲染像素：上采样系数。8 是模型能稳定画出大块色块、
# 又不至于让小尺寸 sprite mosaic 撑爆 3840 上限的折中值。
_RENDER_UPSCALE_PRIMARY = 8
_RENDER_UPSCALE_FALLBACK = 6
_RENDER_UPSCALE_FLOOR = 4
# 即便每像素上采样系数已经退到 4，也要保证整体 sheet 至少有这么多渲染像素，
# 防止 8×1 之类极端窄长 mosaic 被压成 1024×128 之类的退化档。
_API_MIN_LONG_SIDE = 1024
_FRAME_BACKGROUND_FLOW = "split_frame_to_perfect_pixel_to_pixel_bg_alpha_to_alpha_bbox"


def _round_to_multiple(value: float, multiple: int) -> int:
    safe_multiple = max(1, int(multiple))
    return int(round(value / safe_multiple)) * safe_multiple


def _ceil_to_multiple_int(value: float, multiple: int) -> int:
    safe_multiple = max(1, int(multiple))
    return int(-(-int(round(value)) // safe_multiple)) * safe_multiple


def _api_size_valid(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return False
    if width % _API_SIZE_MULTIPLE != 0 or height % _API_SIZE_MULTIPLE != 0:
        return False
    if max(width, height) > _API_SIZE_MAX_SIDE:
        return False
    long_side = max(width, height)
    short_side = min(width, height)
    if short_side == 0 or long_side / short_side > _API_SIZE_MAX_RATIO:
        return False
    pixels = width * height
    if pixels < _API_SIZE_MIN_PIXELS or pixels > _API_SIZE_MAX_PIXELS:
        return False
    return True


def _scale_to_api_constraints(width: float, height: float) -> tuple[int, int] | None:
    """把任意整图渲染目标尺寸钳制到合法 API 尺寸。

    步骤：
    1. 钳制最大边到 3840（按比例缩短长边）；同时把任一边裁到 ≤ 3*另一边。
    2. 圆整到 16 的倍数。
    3. 检查总像素：超过上限按比例缩、低于下限按比例放（再次圆整 + 钳制最大边）。
    4. 返回不能满足全部约束时返回 None。
    """
    if width <= 0 or height <= 0:
        return None
    w, h = float(width), float(height)
    # 1) 长边 / 比例钳制
    long_side = max(w, h)
    if long_side > _API_SIZE_MAX_SIDE:
        scale = _API_SIZE_MAX_SIDE / long_side
        w, h = w * scale, h * scale
    if w / h > _API_SIZE_MAX_RATIO:
        w = h * _API_SIZE_MAX_RATIO
    elif h / w > _API_SIZE_MAX_RATIO:
        h = w * _API_SIZE_MAX_RATIO
    # 2) 圆整到 16 的倍数（先 ceil，避免低于期望渲染分辨率太多）
    iw = max(_API_SIZE_MULTIPLE, _ceil_to_multiple_int(w, _API_SIZE_MULTIPLE))
    ih = max(_API_SIZE_MULTIPLE, _ceil_to_multiple_int(h, _API_SIZE_MULTIPLE))
    # 3) 像素总量校正
    pixels = iw * ih
    if pixels > _API_SIZE_MAX_PIXELS:
        scale = (_API_SIZE_MAX_PIXELS / pixels) ** 0.5
        iw = max(_API_SIZE_MULTIPLE, _round_to_multiple(iw * scale, _API_SIZE_MULTIPLE))
        ih = max(_API_SIZE_MULTIPLE, _round_to_multiple(ih * scale, _API_SIZE_MULTIPLE))
    if iw * ih < _API_SIZE_MIN_PIXELS:
        scale = (_API_SIZE_MIN_PIXELS / max(1, iw * ih)) ** 0.5
        iw = _ceil_to_multiple_int(iw * scale, _API_SIZE_MULTIPLE)
        ih = _ceil_to_multiple_int(ih * scale, _API_SIZE_MULTIPLE)
    # 重新检查长边与比例（可能被像素下限抬升后超过）
    if max(iw, ih) > _API_SIZE_MAX_SIDE:
        long_scale = _API_SIZE_MAX_SIDE / max(iw, ih)
        iw = _round_to_multiple(iw * long_scale, _API_SIZE_MULTIPLE)
        ih = _round_to_multiple(ih * long_scale, _API_SIZE_MULTIPLE)
    if iw == 0 or ih == 0:
        return None
    if iw / ih > _API_SIZE_MAX_RATIO or ih / iw > _API_SIZE_MAX_RATIO:
        return None
    return int(iw), int(ih)


def _parse_size_string(text: str) -> tuple[int, int] | None:
    """解析 "WxH" / "W*H" / "WxH " 等字符串到 (w, h)；解析失败返回 None。"""
    if not text:
        return None
    norm = text.strip().lower().replace("*", "x").replace("×", "x")
    parts = norm.split("x")
    if len(parts) != 2:
        return None
    try:
        w = int(parts[0].strip())
        h = int(parts[1].strip())
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return w, h


def _pick_api_size(sheet_pixel_size: tuple[int, int], explicit: str | None) -> tuple[str, tuple[int, int]]:
    """根据整图像素挑选合法 API 尺寸；显式 size 直接尊重。

    - 如果用户/配置显式给了合法 size 字符串（且不是 auto），原样使用，并把字符串解析
      到像素返回（确保 api_size_str 与 api_size_pixel 一致）；非法显式值回退自动计算。
    - 否则：
      1) 如果传入的 sheet_pixel_size 本身已经满足全部 API 约束，**直接使用它**
         （比例与渲染像素都是为 mosaic 量身算出来的，硬挑主流档反而会让窄长条
         mosaic 拿到 cell 比例严重失衡的画布）。
      2) 否则按约束钳制到合法尺寸。
      3) 极端失败时退回 1024×1024。
    """
    target_w = max(1, int(sheet_pixel_size[0]))
    target_h = max(1, int(sheet_pixel_size[1]))

    if explicit and explicit.strip().lower() not in {"", "auto"}:
        text = explicit.strip()
        parsed = _parse_size_string(text)
        if parsed is not None and _api_size_valid(*parsed):
            return f"{parsed[0]}x{parsed[1]}", parsed
        # 解析失败或违反 API 尺寸约束时，不再把非法值直传给生图 API；
        # 回退到自动尺寸，避免 400 / 422。

    # 1) sheet_pixel_size 已合法 → 圆整到 16 倍数后直接用
    iw = _round_to_multiple(target_w, _API_SIZE_MULTIPLE)
    ih = _round_to_multiple(target_h, _API_SIZE_MULTIPLE)
    if _api_size_valid(iw, ih):
        return f"{iw}x{ih}", (iw, ih)

    # 2) 按约束钳制
    scaled = _scale_to_api_constraints(target_w, target_h)
    if scaled is not None and _api_size_valid(*scaled):
        return f"{scaled[0]}x{scaled[1]}", scaled

    # 3) 兜底
    return "1024x1024", (1024, 1024)


def _compute_render_target(
    target_size: tuple[int, int],
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """按「每像素艺术像素 ≥ N 渲染像素」算出整图理想渲染尺寸。

    依次尝试 8× / 6× / 4× 上采样，挑第一个满足 API 合法约束（≤3840、≤8.3M 像素、
    ≤3:1）的方案。如果连 4× 都装不下，按 4× 计算并交给 _scale_to_api_constraints
    去钳制（最终会落到比 4× 更小但仍合法的尺寸，至少不再是 2× 那种渲染不动的）。

    特殊处理「极窄长条 mosaic」（1×N 或 8×1）：当原始比例 > 3:1 时，
    通过加大短边把比例补到 3:1，而不是缩小长边——cell 上下/左右多出的空白远比
    "cell 被压扁/拉长" 对模型更友好（模型仍能在每个 cell 内画出正常 sprite，
    后续 _split_sheet_to_cells 会用前景投影自动剪掉多余空白带）。
    """
    safe_target_w = max(1, int(target_size[0]))
    safe_target_h = max(1, int(target_size[1]))
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    for upscale in (_RENDER_UPSCALE_PRIMARY, _RENDER_UPSCALE_FALLBACK, _RENDER_UPSCALE_FLOOR):
        sheet_w = safe_target_w * safe_cols * upscale
        sheet_h = safe_target_h * safe_rows * upscale
        # 极窄长条：补短边到 3:1
        long_side = max(sheet_w, sheet_h)
        short_side = min(sheet_w, sheet_h)
        if short_side > 0 and long_side / short_side > _API_SIZE_MAX_RATIO:
            min_short = int(round(long_side / _API_SIZE_MAX_RATIO))
            if sheet_w >= sheet_h:
                sheet_h = max(sheet_h, min_short)
            else:
                sheet_w = max(sheet_w, min_short)
        if (
            max(sheet_w, sheet_h) <= _API_SIZE_MAX_SIDE
            and sheet_w * sheet_h <= _API_SIZE_MAX_PIXELS
            and (max(sheet_w, sheet_h) / max(1, min(sheet_w, sheet_h))) <= _API_SIZE_MAX_RATIO + 1e-6
        ):
            # 还要 ≥ 最小像素 + 最小长边
            if sheet_w * sheet_h >= _API_SIZE_MIN_PIXELS and max(sheet_w, sheet_h) >= _API_MIN_LONG_SIDE:
                return sheet_w, sheet_h
            # 像素太少：按 _API_MIN_LONG_SIDE 抬升后再返回
            scale = max(_API_MIN_LONG_SIDE / max(sheet_w, sheet_h), (_API_SIZE_MIN_PIXELS / max(1, sheet_w * sheet_h)) ** 0.5)
            return int(sheet_w * scale), int(sheet_h * scale)
    # 4× 也装不下时返回 4× 期望，让 _pick_api_size + _scale_to_api_constraints 钳制
    return safe_target_w * safe_cols * _RENDER_UPSCALE_FLOOR, safe_target_h * safe_rows * _RENDER_UPSCALE_FLOOR



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
    # sheet_pixel_size 仍按「像素艺术粒度」表达（用于后续切图、贴 canvas、debug），
    # 而 API 渲染分辨率单独按上采样系数算出来再选档：每个像素艺术像素至少
    # 占 8 渲染像素（必要时退到 6×/4×），让模型能稳定画出大块色块、避免
    # perfect_pixel 在低分辨率下检测不稳。
    #
    # 注意：sprite mosaic 不再继承 image_gen.size 当默认值——image_gen.size 通常被
    # 配置为 1024×1024 给 icon 直出用，对 4×8 mosaic 显然不够。只有 inputs.image_size
    # （来自前端 SpriteParamsSchema）显式给出且非 auto 时才尊重用户选择，否则按
    # rows×cols 自动算出最优渲染档。
    sheet_pixel_size = (target_size[0] * cols, target_size[1] * rows)
    render_target = _compute_render_target(target_size, rows, cols)
    explicit_size = inputs.image_size  # 不再 fallback 到 cfg.image_gen.size
    api_size, api_size_pixel = _pick_api_size(render_target, explicit_size)

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
    api_size_pixel: tuple[int, int] | None = None,
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
    # 渲染尺寸（API 实际生图画布）：每个像素艺术像素占多少渲染像素
    render_w = int(api_size_pixel[0]) if api_size_pixel else int(sheet_pixel_size[0])
    render_h = int(api_size_pixel[1]) if api_size_pixel else int(sheet_pixel_size[1])
    safe_cols = max(1, int(cols))
    safe_rows = max(1, int(rows))
    cell_render_w = max(1, render_w // safe_cols)
    cell_render_h = max(1, render_h // safe_rows)
    upscale_w = max(1, cell_render_w // max(1, int(frame_pixel_size[0])))
    upscale_h = max(1, cell_render_h // max(1, int(frame_pixel_size[1])))
    upscale = max(1, min(upscale_w, upscale_h))
    values = {
        "description": description.strip(),
        "rows": int(rows),
        "cols": int(cols),
        "frame_count": int(rows * cols),
        "frame_width": int(frame_pixel_size[0]),
        "frame_height": int(frame_pixel_size[1]),
        "sheet_width": int(sheet_pixel_size[0]),
        "sheet_height": int(sheet_pixel_size[1]),
        # 新增渲染分辨率占位符：模板可选用，旧模板向下兼容
        "render_width": render_w,
        "render_height": render_h,
        "cell_render_width": cell_render_w,
        "cell_render_height": cell_render_h,
        "upscale": upscale,
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
        f"Render the entire image at exactly {values['render_width']}x{values['render_height']} render pixels; "
        f"every cell occupies {values['cell_render_width']}x{values['cell_render_height']} render pixels. "
        f"Each cell represents a {values['frame_width']}x{values['frame_height']} pixel-art sprite, so every pixel-art pixel "
        f"must be drawn as a perfectly square block of {values['upscale']}x{values['upscale']} render pixels (no anti-aliasing inside the block). "
        f"Each row is one independent animation loop with {values['cols']} frames, listed below:\n{values['row_block']}\n"
        "Character/subject consistency: keep the same identity, palette, outline thickness, scale, and proportions across every cell. "
        f"Background: use pure solid key-color {values['green']} for ALL empty/background pixels for chroma-key removal; "
        f"keep visible colors outside the maximum key-color tolerance ({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        f"Use no more than {values['max_colors']} visible subject colors; background color does not count. "
        "Style: crisp pixel art, hard edges, limited palette, no painterly blending, no anti-aliased soft brush. "
        f"Do not add text, watermark, UI, border, grid lines, labels, numbers, or shadows outside the subject. "
        f"Do not draw extra frames outside the {values['rows']}x{values['cols']} grid."
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
    # 行数代表用户请求的动作数，不能仅因前景投影相连/断裂就改写，否则会把 4 个动作误
    # 合并为 3 个动作。投影仍用于寻找更合适的切线；列数可继续按每行前景纠正。
    row_projection = fg_mask.sum(axis=1)
    detected_rows = _detect_grid_count(row_projection, height, safe_rows)
    actual_rows = safe_rows
    row_splits = _projection_splits(row_projection, height, actual_rows)
    detected_cols: list[int] = []
    for row_index in range(actual_rows):
        top = int(row_splits[row_index])
        bottom = int(row_splits[row_index + 1])
        if bottom <= top:
            bottom = min(height, top + 1)
        band = fg_mask[top:bottom, :].sum(axis=0).astype(np.int64)
        detected_cols.append(_detect_grid_count(band, width, safe_cols))
    actual_cols = _most_common(detected_cols, safe_cols)

    cells: list[Image.Image] = []
    per_row_col_splits: list[list[int]] = []
    for row_index in range(actual_rows):
        top = int(row_splits[row_index])
        bottom = int(row_splits[row_index + 1])
        if bottom <= top:
            top, bottom = int(row_splits[row_index]), min(height, int(row_splits[row_index]) + 1)
        # 行带内的列投影：仅对该行的前景做投影，避免别行干扰
        col_proj = fg_mask[top:bottom, :].sum(axis=0).astype(np.int64) if bottom > top else np.zeros(width, dtype=np.int64)
        col_splits = _projection_splits(col_proj, width, actual_cols)
        per_row_col_splits.append(col_splits.tolist())
        for col_index in range(actual_cols):
            left = int(col_splits[col_index])
            right = int(col_splits[col_index + 1])
            if right <= left:
                left, right = int(col_splits[col_index]), min(width, int(col_splits[col_index]) + 1)
            cells.append(image.crop((left, top, right, bottom)).convert("RGBA"))
    meta = {
        "image_size": [int(width), int(height)],
        "requested_rows": safe_rows,
        "requested_cols": safe_cols,
        "rows": int(actual_rows),
        "cols": int(actual_cols),
        "detected_rows": int(detected_rows),
        "row_splits": row_splits.tolist(),
        "col_splits_per_row": per_row_col_splits,
        "method": "foreground_projection_autogrid",
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

    分两步：
    1. 用前景投影定位整体主体的 `[content_start, content_end]` 区间，trim 掉首尾的
       大段空白边距（典型 case：模型在 1024×1024 画布上画 3 行人物 + 底部空白条，
       直接全图等分会把第 4 条切线落在尾部空白里，让最后一行 cell 全空）。
    2. 在 trim 后的内容区间内对 `segments-1` 条内部切线均分，再在每条理论切线
       附近的搜索窗口里挑前景像素最少的位置。
    最外侧的两条切线仍固定为 0 与 total，保证完整覆盖原图。
    """
    safe_segments = max(1, int(segments))
    if safe_segments == 1 or total <= safe_segments:
        return np.array([int(round(i * total / safe_segments)) for i in range(safe_segments + 1)], dtype=np.int64)

    proj = np.asarray(projection, dtype=np.int64)
    if proj.size != total:
        # 维度不匹配时退化
        return np.array([int(round(i * total / safe_segments)) for i in range(safe_segments + 1)], dtype=np.int64)

    # 1. trim 首尾空白：投影 ≤ 阈值视为空白
    fg_threshold = max(1, int(proj.max() * 0.005)) if proj.max() > 0 else 1
    fg_mask = proj > fg_threshold
    if fg_mask.any():
        content_start = int(np.argmax(fg_mask))
        content_end = total - int(np.argmax(fg_mask[::-1]))  # 排他上界
    else:
        content_start, content_end = 0, total
    # 仅当首尾空白合计超过画布 5%（约 1/(2·cells) 个 cell）时才启用 trim
    margin_total = content_start + (total - content_end)
    if margin_total < int(total * 0.05):
        content_start, content_end = 0, total
    content_len = max(safe_segments, content_end - content_start)
    cell_size = content_len / safe_segments
    # 搜索半径：cell 的 40%，至少 2 像素
    search_radius = max(2, int(round(cell_size * 0.4)))

    splits: list[int] = [0]
    for i in range(1, safe_segments):
        ideal = content_start + i * cell_size
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


def _detect_grid_count(projection: np.ndarray, total: int, hint: int) -> int:
    """从 1D 前景投影检测实际分段数；不可靠时回退 hint。

    纠正「模型没严格按 rows×cols 画」导致的切分错位：例如请求 cols=8 但实际只画了 7 列，
    按 8 等分会把某个 cell 切在列间隙上变成空帧。这里数「显著低谷带」推断真实行/列数，
    仅在与 hint 偏差不大（≤ max(1, hint/3)）时采纳，避免误伤正常作品（参数正确或主体填满）。
    """
    safe_hint = max(1, int(hint))
    proj = np.asarray(projection, dtype=np.float64)
    if safe_hint <= 1 or proj.size == 0:
        return safe_hint
    peak = float(proj.max())
    if peak <= 0:
        return safe_hint
    content_line = proj > peak * 0.04
    if not content_line.any():
        return safe_hint
    start = int(np.argmax(content_line))
    end = proj.size - int(np.argmax(content_line[::-1]))
    span = max(1, end - start)
    min_gap = max(2, int(round((span / safe_hint) * 0.18)))
    valley = proj <= peak * 0.06
    gaps = 0
    i = start
    while i < end:
        if valley[i]:
            j = i
            while j < end and valley[j]:
                j += 1
            if (j - i) >= min_gap:
                gaps += 1
            i = j
        else:
            i += 1
    detected = gaps + 1
    if detected >= 1 and abs(detected - safe_hint) <= max(1, round(safe_hint / 3)):
        return int(detected)
    return safe_hint


def _most_common(values: list[int], fallback: int) -> int:
    """众数；并列时取较大值（更可能是真实列数，避免少切）。"""
    if not values:
        return fallback
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return int(max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0])


def _extract_cell_content(
    cfg: AppConfig,
    cell: Image.Image,
    *,
    target_size: tuple[int, int],
    key_rgb: tuple[int, int, int],
    key_tolerance: int,
    generated_preprocess_method: str | None,
) -> tuple[Image.Image, tuple[int, int, int, int] | None, dict[str, Any]]:
    """对单个 cell 严格执行：切分帧 → perfect pixel → pixel_bg alpha → alpha bbox 裁剪。

    这里必须使用 prompt 中显式传入的 ``key_rgb``，并走双阈值连通域 + 二值 alpha。
    多行 mosaic 里主体经常溢出 cell 边界（长发、裙摆、武器），显式 key 色能避免
    从 cell 四角采到主体色导致背景没抠干净或主体边缘被啃掉。
    """
    _ = cfg  # 保留参数以兼容历史调用方；序列帧去背景不再读取 cfg 中的旧算法开关
    preprocessed = preprocess_generated_image(
        cell,
        method=generated_preprocess_method,
        target_size=target_size,
    )
    image = preprocessed.image.convert("RGBA")

    # 序列帧要求的后处理链路是：perfect pixel 后使用显式 key 色做 pixel_bg
    # 双阈值连通域 + 二值 alpha，再按最终 alpha bbox 裁剪；不从四角重新采样背景色。
    alpha_image = apply_pixel_bg_alpha(
        image,
        key_rgb=key_rgb,
        tolerance=max(0, int(key_tolerance)),
    )
    bbox = _visible_bbox(alpha_image, threshold=8)
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), None, {
            "preprocess": preprocessed.meta,
            "background_flow": _FRAME_BACKGROUND_FLOW,
            "background_algorithm": "pixel_bg",
            "bbox": None,
            "alpha_size": list(alpha_image.size),
            "key_rgb": list(key_rgb),
            "key_tolerance": int(key_tolerance),
        }
    content = alpha_image.crop(bbox)
    return content, bbox, {
        "preprocess": preprocessed.meta,
        "background_flow": _FRAME_BACKGROUND_FLOW,
        "background_algorithm": "pixel_bg",
        "alpha_size": list(alpha_image.size),
        "bbox": list(bbox),
        "content_size": list(content.size),
        "key_rgb": list(key_rgb),
        "key_tolerance": int(key_tolerance),
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
        api_size_pixel=settings.api_size_pixel,
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
    sheet_grid_path = run_dir / "sprite_sheet_grid.png"
    row_sheets_dir = run_dir / "row_sheets"
    row_previews_dir = run_dir / "previews"
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
        # 切分按实际检测到的网格走（模型可能没严格按请求的 rows×cols 画）；之后所有
        # settings.rows/cols（行号、rows_outputs、网格预览、sequence.json）随之统一。
        detected_rows = int(split_meta.get("rows", settings.rows))
        detected_cols = int(split_meta.get("cols", settings.cols))
        if (detected_rows, detected_cols) != (settings.rows, settings.cols):
            settings = replace(settings, rows=detected_rows, cols=detected_cols)
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
                key_rgb=key_rgb,
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

        # 7.1 网格预览：rows × cols 二维 sheet，便于和原始 mosaic 对照
        compose_grid_sprite_sheet(
            frame_paths,
            sheet_grid_path,
            rows=settings.rows,
            cols=settings.cols,
            frame_size=effective_size,
        )

        # 7.2 按行产物：每行一张横向 sheet + 一个独立动画 GIF。
        # rows>1 时强制生成行 GIF（多行 mosaic 的核心价值就是「每行一个动画循环」）；
        # rows==1 时复用原 sprite.gif 即可，不再额外生成 row_01.gif，避免重复。
        rows_outputs: list[dict[str, Any]] = []
        force_row_previews = settings.rows > 1
        if force_row_previews:
            row_sheets_dir.mkdir(parents=True, exist_ok=True)
            row_previews_dir.mkdir(parents=True, exist_ok=True)
        for row_index in range(settings.rows):
            start = row_index * settings.cols
            end = start + settings.cols
            row_frame_paths = frame_paths[start:end]
            row_indices = list(range(start + 1, end + 1))
            row_phase = safe_row_prompts[row_index] if row_index < len(safe_row_prompts) else ""
            row_entry: dict[str, Any] = {
                "row_index": row_index,
                "frame_indices": row_indices,
                "action_phase": row_phase,
                "sheet": None,
                "gif": None,
            }
            if force_row_previews and row_frame_paths:
                row_sheet_path = row_sheets_dir / f"row_{row_index + 1:02d}.png"
                compose_horizontal_sprite_sheet(row_frame_paths, row_sheet_path)
                row_gif_path = row_previews_dir / f"row_{row_index + 1:02d}.gif"
                compose_gif(
                    row_frame_paths,
                    row_gif_path,
                    duration_ms=settings.duration_ms,
                    loop=settings.loop,
                )
                row_entry["sheet"] = _rel(row_sheet_path, run_dir)
                row_entry["gif"] = _rel(row_gif_path, run_dir)
            rows_outputs.append(row_entry)

        preview_path: Path | None = None
        if settings.gif_export:
            compose_gif(frame_paths, gif_path, duration_ms=settings.duration_ms, loop=settings.loop)
            preview_path = gif_path
        # 多行 mosaic 默认让首行 GIF 作为顶级预览（更直观），不强行覆盖 gif_export=true 的总动画。
        if preview_path is None and force_row_previews and rows_outputs and rows_outputs[0]["gif"]:
            preview_path = run_dir / rows_outputs[0]["gif"]

        notify("sprite_mosaic_outputs_ready", {
            "sheet": str(sheet_path),
            "sheet_grid": str(sheet_grid_path),
            "mosaic_sheet": str(sheet_raw_path),
            "sequence": str(sequence_path),
            "gif": str(preview_path) if preview_path else None,
            "row_count": len(rows_outputs),
            "row_previews": [entry["gif"] for entry in rows_outputs if entry.get("gif")],
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
        sheet_grid_path=sheet_grid_path,
        row_prompts=safe_row_prompts,
        rows_outputs=rows_outputs,
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
        rows_outputs=rows_outputs,
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
            "frame_background_flow": _FRAME_BACKGROUND_FLOW,
            "shared_palette": bool(cfg.sprite.shared_palette),
            "shared_palette_colors": shared_palette_hex,
            "split": split_meta,
            "row_prompts": safe_row_prompts,
            "raw_frames_dir": _rel(raw_dir, run_dir),
            "frames_dir": _rel(final_dir, run_dir),
            "horizontal_sheet": sheet_path.name,
            "grid_sheet": sheet_grid_path.name,
            "mosaic_sheet": sheet_raw_path.name,
            "sequence_json": sequence_path.name,
            "gif": gif_path.name if settings.gif_export else None,
            "frames": [_frame_metadata(frame, run_dir, cols=settings.cols, cell_meta=cell_meta) for frame in frames],
            "rows_outputs": rows_outputs,
            "row_sheets_dir": _rel(row_sheets_dir, run_dir) if row_sheets_dir.exists() else None,
            "row_previews_dir": _rel(row_previews_dir, run_dir) if row_previews_dir.exists() else None,
            "sequence": sequence,
            "billing": inputs.billing or None,
            "use_reference": settings.use_reference,
        },
        "cache": {"enabled": cache.enabled, "refresh": inputs.refresh_cache},
        "outputs": {
            "source": _rel(sheet_raw_path, run_dir),
            "sprite_frames": _rel(final_dir, run_dir),
            "sprite_sheet": sheet_path.name,
            "sprite_sheet_grid": sheet_grid_path.name,
            "sprite_mosaic": sheet_raw_path.name,
            "sequence_json": sequence_path.name,
            "sprite_gif": gif_path.name if settings.gif_export else None,
            "row_sheets_dir": _rel(row_sheets_dir, run_dir) if row_sheets_dir.exists() else None,
            "row_previews_dir": _rel(row_previews_dir, run_dir) if row_previews_dir.exists() else None,
            "row_previews": [entry["gif"] for entry in rows_outputs if entry.get("gif")],
            "row_sheets": [entry["sheet"] for entry in rows_outputs if entry.get("sheet")],
            "pixelized": sheet_path.name,
            "preview": (
                _rel(preview_path, run_dir) if preview_path is not None
                else (gif_path.name if settings.gif_export else None)
            ),
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
    sheet_grid_path: Path,
    row_prompts: list[str],
    rows_outputs: list[dict[str, Any]],
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
        "frame_background_flow": _FRAME_BACKGROUND_FLOW,
        "row_prompts": list(row_prompts),
        "playback_source": _rel(sheet_path, run_dir),
        "mosaic_source": _rel(mosaic_sheet_path, run_dir),
        "grid_source": _rel(sheet_grid_path, run_dir),
        "rows_outputs": rows_outputs,
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
    rows_outputs: list[dict[str, Any]] | None = None,
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
        f"frame_background_flow = {_FRAME_BACKGROUND_FLOW}",
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
    if rows_outputs:
        parts.extend(["", "[row_outputs]"])
        for entry in rows_outputs:
            row_index = int(entry.get("row_index", 0)) + 1
            sheet = entry.get("sheet") or "(none)"
            gif = entry.get("gif") or "(none)"
            parts.append(f"row_{row_index} sheet = {sheet}")
            parts.append(f"row_{row_index} gif = {gif}")
    parts.extend(["", "[billing]"])
    if billing:
        parts.extend(f"{key} = {value}" for key, value in billing.items())
    else:
        parts.append("billing = not_provided")
    parts.extend(["", "[effective_prompt]", effective_prompt])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
