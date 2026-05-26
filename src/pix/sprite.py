"""九宫格动画精灵表生成流水线。"""

from __future__ import annotations

import json
import math
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterable

import numpy as np
from PIL import Image

from pix import __version__
from pix.api.image_gen import generate_image
from pix.api.prompt_guard import PromptPolicyError, validate_user_prompt
from pix.cache import Cache
from pix.config import AppConfig
from pix.contact_sheet import resolve_key_color
from pix.io_utils import new_run_dir
from pix.pixelize.bg_removal import remove_background, remove_translucent_edge_halo
from pix.pixelize.core import PixelizeParams
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.pixelize.palette import build_palette_image, kmeans_palette, rgb_to_hex


LocalStageContext = Callable[[], ContextManager[None]]


@dataclass(frozen=True)
class SpriteFrame:
    """单帧输出信息。"""

    index: int
    row: int
    col: int
    raw_path: Path
    path: Path
    bbox: tuple[int, int, int, int] | None = None

    def to_metadata(self, run_dir: Path) -> dict[str, Any]:
        return {
            "index": self.index,
            "row": self.row,
            "col": self.col,
            "raw_path": _rel(self.raw_path, run_dir),
            "path": _rel(self.path, run_dir),
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class SpritePipelineInput:
    prompt: str
    image_size: str | None = None
    image_quality: str | None = None
    image_model: str | None = None
    pixelize_params: PixelizeParams = field(default_factory=PixelizeParams)
    out_root: str | Path | None = None
    use_cache: bool = True
    refresh_cache: bool = False
    duration_ms: int | None = None
    loop: int | None = None
    rows: int | None = None
    cols: int | None = None
    key_mode: str | None = None
    key_tolerance: int | None = None
    key_softness: int | None = None
    key_alpha_floor: int | None = None
    key_despill: bool | None = None
    local_stage_context: LocalStageContext | None = None


@dataclass
class SpritePipelineResult:
    run_dir: Path
    source_path: Path
    frame_paths: list[Path]
    pixel_path: Path
    preview_path: Path | None
    meta_path: Path
    meta: dict[str, Any]
    analysis_path: Path | None = None

    @property
    def gif_path(self) -> Path | None:
        return self.preview_path


@dataclass(frozen=True)
class SpriteSplitResult:
    source_path: Path
    raw_frames: list[Path]
    bboxes: list[tuple[int, int, int, int] | None]
    crop_box: tuple[int, int, int, int] | None
    preprocessed_path: Path | None = None
    alpha_path: Path | None = None
    cell_size: tuple[int, int] | None = None
    frame_canvas_size: tuple[int, int] | None = None
    sheet_canvas_size: tuple[int, int] | None = None
    preprocess_meta: dict[str, Any] = field(default_factory=dict)


ProgressCb = Any


def _noop(_step: str, _payload: dict) -> None:
    pass


def _local_stage(factory: LocalStageContext | None) -> ContextManager[None]:
    return factory() if factory is not None else nullcontext()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _size_tuple(value: tuple[int, int] | list[int] | None, fallback: tuple[int, int]) -> tuple[int, int]:
    if not value:
        return fallback
    try:
        return max(1, int(value[0])), max(1, int(value[1]))
    except (TypeError, ValueError, IndexError):
        return fallback


def _sprite_frame_bounds(rows: int, cols: int, width: int, height: int) -> str:
    parts: list[str] = []
    for row in range(rows):
        for col in range(cols):
            index = row * cols + col + 1
            x0 = col * width
            y0 = row * height
            x1 = (col + 1) * width - 1
            y1 = (row + 1) * height - 1
            parts.append(f"Frame {index}: row {row + 1}, col {col + 1}, x={x0}-{x1}, y={y0}-{y1}")
    return "; ".join(parts) + "."


def _sprite_frame_layout(rows: int, cols: int) -> str:
    if rows == 3 and cols == 3:
        return (
            "Frame placement contract: generate one single 3x3 sheet, not separate images and not a horizontal strip. "
            "Place the 9 frames exactly in row-major order: "
            "Frame 1 top-left = idle/anticipation pose before the action; "
            "Frame 2 top-center = wind-up, weapon/limbs pulling back; "
            "Frame 3 top-right = final anticipation, body compressed and ready to move; "
            "Frame 4 middle-left = action starts, first forward step/lunge; "
            "Frame 5 center = main action peak, weapon/energy fully extended forward; "
            "Frame 6 middle-right = hit/contact frame with the strongest flash or impact effect; "
            "Frame 7 bottom-left = follow-through, trailing energy/smear continues forward; "
            "Frame 8 bottom-center = recovery, body and weapon start returning; "
            "Frame 9 bottom-right = settle/back-to-ready pose. "
            "For thrust, stab, lunge, slash, projectile, or attack effects, make the motion read clearly in 2D game-sprite space: "
            "keep the body anchor near center-left and extend the weapon/effect toward screen-right unless the user explicitly asks for another direction. "
            "Frame 5 must have the farthest weapon reach, and Frame 6 must show the hit flash at the weapon tip. "
            "Every cell must contain exactly one full-body frame centered inside that cell; keep the same anchor point and scale. "
            "The character/effect silhouette should fill about 70-85% of the cell height or width, leaving only a few clear key-color pixels of padding. "
            "Do not draw cell borders, grid lines, arrows, frame numbers, labels, or timeline marks."
        )
    return (
        "Frame placement contract: generate one single grid sheet, not separate images. "
        f"Use {rows} rows and {cols} columns in strict row-major order, left-to-right then top-to-bottom. "
        "Each cell must contain exactly one centered animation keyframe with consistent scale and anchor point. "
        "Do not draw cell borders, grid lines, arrows, frame numbers, labels, or timeline marks."
    )


def build_sprite_sheet_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int] | None = None,
    rows: int | None = None,
    cols: int | None = None,
    max_colors: int | None = None,
    key_tolerance: int | None = None,
) -> str:
    """构造专用于 3×3 动画关键帧九宫格的受控 prompt。"""

    sprite_cfg = cfg.sprite
    safe_rows = max(1, int(rows or sprite_cfg.rows))
    safe_cols = max(1, int(cols or sprite_cfg.cols))
    width, height = target_size or sprite_cfg.pixel_size
    key_hex, _key_rgb = resolve_key_color(sprite_cfg.green_screen_color, description)
    frame_width = int(width)
    frame_height = int(height)
    values = {
        "description": description.strip(),
        "rows": safe_rows,
        "cols": safe_cols,
        "count": safe_rows * safe_cols,
        "green": key_hex,
        "key_color": key_hex,
        "key_tolerance": int(sprite_cfg.green_screen_tolerance if key_tolerance is None else key_tolerance),
        "max_colors": int(sprite_cfg.colors if max_colors is None else max_colors),
        "width": frame_width,
        "height": frame_height,
        "sheet_width": safe_cols * frame_width,
        "sheet_height": safe_rows * frame_height,
        "frame_bounds": _sprite_frame_bounds(safe_rows, safe_cols, frame_width, frame_height),
        "frame_layout": _sprite_frame_layout(safe_rows, safe_cols),
    }
    template = (sprite_cfg.prompt_template or "").strip()
    if template:
        try:
            return template.format(**values).strip()
        except Exception:
            pass
    return _fallback_sprite_prompt(**values)


def _fallback_sprite_prompt(**values: Any) -> str:
    return (
        "Create a TRUE pixel-art animation contact sheet for a game, not a painted digital illustration: "
        f"exactly {values['rows']}x{values['cols']} grid, {values['count']} sequential animation keyframes. "
        f"Animation subject/action: {values['description']}. "
        "Single-frame size is a hard contract from the user export target: "
        f"every frame must be exactly {values['width']}x{values['height']} logical pixels, where each pixel is one square grid cell. "
        f"The complete logical sprite sheet must be exactly {values['sheet_width']}x{values['sheet_height']} pixels: "
        f"{values['cols']} columns × {values['width']}px and {values['rows']} rows × {values['height']}px. "
        f"Frame cell coordinate bounds in the logical sheet are: {values['frame_bounds']} "
        "Do not make larger or smaller frames, do not merge cells, and do not add gutters between cells. "
        "Use large, chunky readable pixels, limited colors, and a clear silhouette in every frame. "
        f"Use no more than {values['max_colors']} visible subject/effect colors per frame; background color does not count. "
        f"Read order is left-to-right, top-to-bottom. {values['frame_layout']} "
        "Keep the same character, camera angle, scale, anchor point, "
        "lighting, and ground/contact position in every cell. Each cell is one clean keyframe of the continuous motion, "
        "centered with clear empty pixel rows around all edges for safe sprite padding and stable extraction. "
        f"Use pure solid key-color {values['green']} for all empty/background pixels across the whole image for chroma-key removal; "
        "keep every visible subject/effect color outside the maximum key-color tolerance "
        f"({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. "
        "The output should be pixel-perfect; each sprite pixel cell contains only one flat color. "
        "No text, no watermark, no labels, no numbers, no UI frame, no grid lines, no camera zoom changes."
    )


def _normalized_key_mode(value: str | None) -> str:
    mode = (value or "hard").strip().lower()
    if mode not in {"hard", "soft"}:
        raise ValueError("key_mode 必须是 hard 或 soft")
    return mode


def _apply_key_transparency(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int],
    tolerance: int,
    mode: str = "hard",
    softness: int = 150,
    alpha_floor: int = 12,
    despill: bool = True,
) -> Image.Image:
    """按 key color 移除背景。

    hard 模式全局移除接近 key color 的像素，并清除透明像素 RGB 残留和边缘溢色；
    soft 模式会估算半透明边缘 alpha，并用反混合去掉 key color 对边缘 RGB 的污染。
    """

    key_mode = _normalized_key_mode(mode)
    if key_mode == "hard":
        rgba = np.asarray(image.convert("RGBA")).copy()
        h, w = rgba.shape[:2]
        rgb = rgba[..., :3].astype(np.float64)
        ref = np.array(key_rgb, dtype=np.float64)
        dist = np.sqrt(((rgb - ref) ** 2).sum(axis=2))

        # 1. 全局移除背景
        bg_mask = dist <= max(0, int(tolerance))
        rgba[bg_mask, 3] = 0

        # 2. Decontaminate 半透明边缘（紧邻透明区域的半透明像素）
        transparent = rgba[..., 3] == 0
        near_transparent = np.zeros((h, w), dtype=bool)
        if h > 1:
            near_transparent[1:, :] |= transparent[:-1, :]
            near_transparent[:-1, :] |= transparent[1:, :]
        if w > 1:
            near_transparent[:, 1:] |= transparent[:, :-1]
            near_transparent[:, :-1] |= transparent[:, 1:]

        semi_mask = near_transparent & (rgba[..., 3] > 0) & (rgba[..., 3] < 255)
        if semi_mask.any():
            a = rgba[semi_mask, 3].astype(np.float64) / 255.0
            for c in range(3):
                channel = rgba[semi_mask, c].astype(np.float64)
                decontaminated = (channel - ref[c] * (1.0 - a)) / np.maximum(a, 0.01)
                rgba[semi_mask, c] = np.clip(decontaminated, 0, 255).astype(np.uint8)

        # 3. 透明像素 RGB 置黑（防止缩放时渗出背景色）
        fully_transparent = rgba[..., 3] == 0
        rgba[fully_transparent, :3] = 0

        return Image.fromarray(rgba, mode="RGBA")

    rgba_f = np.asarray(image.convert("RGBA")).astype(np.float32)
    rgb = rgba_f[..., :3]
    source_alpha = rgba_f[..., 3] / 255.0
    ref = np.array(key_rgb, dtype=np.float32)
    dist = np.sqrt(((rgb - ref) ** 2).sum(axis=2))
    hard = max(0.0, float(tolerance))
    soft = max(hard + 1.0, float(softness))
    estimated_alpha = np.clip((dist - hard) / (soft - hard), 0.0, 1.0)
    alpha = np.minimum(source_alpha, estimated_alpha)
    floor = max(0, int(alpha_floor)) / 255.0
    alpha[alpha < floor] = 0.0

    if despill:
        safe_alpha = np.maximum(alpha, 1e-5)[..., None]
        rgb = (rgb - ref * (1.0 - safe_alpha)) / safe_alpha
        rgb = np.clip(rgb, 0, 255)
        rgb = np.where(alpha[..., None] > 0, rgb, 0)

    out = np.zeros_like(rgba_f)
    out[..., :3] = rgb
    out[..., 3] = alpha * 255.0
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGBA")


def _visible_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = np.asarray(image.convert("RGBA"))[..., 3]
    visible = alpha > threshold
    if not visible.any():
        return None
    ys, xs = np.where(visible)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _union_bboxes(bboxes: Iterable[tuple[int, int, int, int] | None]) -> tuple[int, int, int, int] | None:
    valid = [bbox for bbox in bboxes if bbox is not None]
    if not valid:
        return None
    return (
        min(item[0] for item in valid),
        min(item[1] for item in valid),
        max(item[2] for item in valid),
        max(item[3] for item in valid),
    )


def _expand_crop_box(
    bbox: tuple[int, int, int, int],
    cell_size: tuple[int, int],
    *,
    padding: float,
    square: bool,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    width, height = cell_size
    subject_w = max(1, right - left)
    subject_h = max(1, bottom - top)
    pad = max(0, int(round(max(subject_w, subject_h) * max(0.0, float(padding)))))
    left -= pad
    top -= pad
    right += pad
    bottom += pad
    if square:
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        side = max(1, int(math.ceil(max(right - left, bottom - top))))
        left = int(round(cx - side / 2))
        top = int(round(cy - side / 2))
        right = left + side
        bottom = top + side
    crop_w = max(1, right - left)
    crop_h = max(1, bottom - top)
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > width:
        left -= right - width
        right = width
    if bottom > height:
        top -= bottom - height
        bottom = height
    left = max(0, min(left, max(0, width - 1)))
    top = max(0, min(top, max(0, height - 1)))
    right = max(left + 1, min(width, right))
    bottom = max(top + 1, min(height, bottom))
    if square:
        side = min(max(crop_w, crop_h), width, height)
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        left = int(round(cx - side / 2))
        top = int(round(cy - side / 2))
        left = max(0, min(left, width - side))
        top = max(0, min(top, height - side))
        right = left + side
        bottom = top + side
    return int(left), int(top), int(right), int(bottom)


SPRITE_FRAME_SIZE_PRESETS = (16, 24, 32, 48, 64, 96, 128, 256)


def _ceil_to_multiple(value: int, divisor: int) -> int:
    safe_divisor = max(1, int(divisor))
    safe_value = max(1, int(value))
    return ((safe_value + safe_divisor - 1) // safe_divisor) * safe_divisor


def _ceil_to_preset(value: int, requested: int) -> int:
    threshold = max(1, int(value), int(requested))
    for preset in sorted(set(SPRITE_FRAME_SIZE_PRESETS + (max(1, int(requested)),))):
        if preset >= threshold:
            return preset
    return threshold


def _pad_to_canvas(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    frame = image.convert("RGBA")
    x = max(0, (size[0] - frame.width) // 2)
    y = max(0, (size[1] - frame.height) // 2)
    canvas.alpha_composite(frame, (x, y))
    return canvas


def _pad_sheet_for_equal_cells(image: Image.Image, *, rows: int, cols: int) -> tuple[Image.Image, dict[str, Any]]:
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    target_size = (_ceil_to_multiple(image.width, safe_cols), _ceil_to_multiple(image.height, safe_rows))
    if target_size == image.size:
        return image.convert("RGBA"), {"applied": False, "input_size": list(image.size), "output_size": list(image.size)}
    return _pad_to_canvas(image, target_size), {
        "applied": True,
        "input_size": list(image.size),
        "output_size": list(target_size),
        "rows": safe_rows,
        "cols": safe_cols,
    }


def _frame_canvas_size(cell_size: tuple[int, int], requested_size: tuple[int, int] | None) -> tuple[int, int]:
    if requested_size is None:
        return cell_size
    return (
        _ceil_to_preset(cell_size[0], requested_size[0]),
        _ceil_to_preset(cell_size[1], requested_size[1]),
    )


def _sprite_bg_removal_options(cfg: AppConfig | None, *, tolerance: int) -> dict[str, Any]:
    asset = getattr(cfg, "asset", None)
    if asset is None:
        return {
            "bg_removal_algorithm": "color_to_alpha",
            "color_to_alpha_transparency": max(0, int(tolerance)),
        }
    return {
        "bg_removal_algorithm": "color_to_alpha",
        "color_to_alpha_shape": getattr(asset, "color_to_alpha_shape", "sphere"),
        "color_to_alpha_transparency": max(0, int(tolerance)),
        "color_to_alpha_opacity": getattr(asset, "color_to_alpha_opacity", 255),
        "color_to_alpha_interpolation": getattr(asset, "color_to_alpha_interpolation", "linear"),
    }


def _center_on_transparent_canvas(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    frame = image.convert("RGBA")
    x = max(0, (size[0] - frame.width) // 2)
    y = max(0, (size[1] - frame.height) // 2)
    canvas.alpha_composite(frame, (x, y))
    return canvas


def split_sprite_sheet(
    image_path: str | Path,
    dest_dir: str | Path,
    *,
    rows: int,
    cols: int,
    key_color: str,
    tolerance: int,
    crop_padding: float = 0.12,
    crop_square: bool = True,
    key_mode: str = "hard",
    key_softness: int = 150,
    key_alpha_floor: int = 12,
    key_despill: bool = True,
    target_size: tuple[int, int] | None = None,
    cfg: AppConfig | None = None,
    generated_preprocess_method: str = "perfect_pixel",
    preprocessed_sheet_path: str | Path | None = None,
    alpha_sheet_path: str | Path | None = None,
) -> SpriteSplitResult:
    """整表后处理后切帧。

    顺序固定为：整张 3×3 源图 perfectPixel → Color-to-Alpha → 透明补到可等分画布
    → 切 9 张相同宽高帧 → 每帧透明补到目标/预设帧尺寸。这里不再逐帧二次
    perfectPixel，也不再按联合 bbox 裁剪，避免破坏模型生成的九宫格空间关系。
    """

    _ = (key_color, crop_padding, crop_square, key_mode, key_softness, key_alpha_floor, key_despill)
    source_path = Path(image_path)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    requested_sheet_size = (safe_cols * target_size[0], safe_rows * target_size[1]) if target_size else None
    raw_frames: list[Path] = []

    with Image.open(source_path) as opened:
        source = opened.convert("RGBA")

    preprocessed_result = preprocess_generated_image(
        source,
        method=generated_preprocess_method,
        target_size=requested_sheet_size,
    )
    preprocessed = preprocessed_result.image.convert("RGBA")
    preprocessed_path = Path(preprocessed_sheet_path) if preprocessed_sheet_path else None
    if preprocessed_path is not None:
        preprocessed_path.parent.mkdir(parents=True, exist_ok=True)
        preprocessed.save(preprocessed_path)

    alpha = remove_background(
        preprocessed,
        tolerance=max(0, int(tolerance)),
        feather=0,
        edge_style="hard",
        keep_border_bleed=True,
        **_sprite_bg_removal_options(cfg, tolerance=tolerance),
    )
    alpha_path = Path(alpha_sheet_path) if alpha_sheet_path else None
    if alpha_path is not None:
        alpha_path.parent.mkdir(parents=True, exist_ok=True)
        alpha.save(alpha_path)

    equal_sheet, sheet_pad_meta = _pad_sheet_for_equal_cells(alpha, rows=safe_rows, cols=safe_cols)
    cell_size = (equal_sheet.width // safe_cols, equal_sheet.height // safe_rows)
    frame_canvas_size = _frame_canvas_size(cell_size, target_size)
    bboxes: list[tuple[int, int, int, int] | None] = []

    for row in range(safe_rows):
        for col in range(safe_cols):
            index = row * safe_cols + col + 1
            left = col * cell_size[0]
            top = row * cell_size[1]
            right = left + cell_size[0]
            bottom = top + cell_size[1]
            cell = equal_sheet.crop((left, top, right, bottom))
            frame = _pad_to_canvas(remove_translucent_edge_halo(cell), frame_canvas_size)
            bboxes.append(_visible_bbox(frame))
            frame_path = dest / f"frame_{index:02d}.png"
            frame.save(frame_path)
            raw_frames.append(frame_path)

    preprocess_meta = dict(preprocessed_result.meta)
    preprocess_meta["requested_sheet_size"] = list(requested_sheet_size) if requested_sheet_size else None
    preprocess_meta["alpha_size"] = list(alpha.size)
    preprocess_meta["equal_sheet_pad"] = sheet_pad_meta
    return SpriteSplitResult(
        source_path=source_path,
        raw_frames=raw_frames,
        bboxes=bboxes,
        crop_box=None,
        preprocessed_path=preprocessed_path,
        alpha_path=alpha_path,
        cell_size=cell_size,
        frame_canvas_size=frame_canvas_size,
        sheet_canvas_size=equal_sheet.size,
        preprocess_meta=preprocess_meta,
    )


def _compose_mosaic(frames: list[Image.Image]) -> Image.Image:
    if not frames:
        raise ValueError("没有可用于合成的帧")
    width = sum(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for frame in frames:
        sheet.alpha_composite(frame.convert("RGBA"), (x, (height - frame.height) // 2))
        x += frame.width
    return sheet


def _quantize_with_palette(
    image: Image.Image,
    palette_rgb: list[tuple[int, int, int]],
    *,
    dither: str,
) -> Image.Image:
    pal_img = build_palette_image(palette_rgb)
    dither_method = Image.Dither.FLOYDSTEINBERG if dither == "floyd_steinberg" else Image.Dither.NONE
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    quantized = rgba.convert("RGB").quantize(palette=pal_img, dither=dither_method)
    out = quantized.convert("RGBA")
    out.putalpha(alpha)
    return out


def pixelize_sprite_frames(
    raw_frames: list[Path],
    dest_dir: str | Path,
    params: PixelizeParams,
    *,
    shared_palette: bool = True,
    cfg: AppConfig | None = None,
    source_description: str = "",
) -> tuple[list[Path], dict[str, Any]]:
    """保存最终帧，并可用共享调色板统一全部帧。

    进入这里的 raw frame 已经来自整表 perfectPixel + Color-to-Alpha + 透明补画布，
    不再逐帧缩放或二次 pixelize，避免破坏等宽高序列帧。
    """

    _ = (cfg, source_description)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    images: list[Image.Image] = []
    per_frame_meta: list[dict[str, Any]] = []
    for raw in raw_frames:
        with Image.open(raw) as opened:
            image = opened.convert("RGBA")
        images.append(image)
        per_frame_meta.append({"path": str(raw), "input_size": list(image.size), "output_size": list(image.size), "resized": False})

    shared_palette_hex: list[str] = []
    if shared_palette and images:
        mosaic = _compose_mosaic(images)
        palette = kmeans_palette(mosaic, max(2, min(256, int(params.colors))))
        images = [_quantize_with_palette(img, palette, dither=params.dither) for img in images]
        shared_palette_hex = [rgb_to_hex(rgb) for rgb in palette]

    paths: list[Path] = []
    for index, image in enumerate(images, start=1):
        path = dest / f"frame_{index:02d}.png"
        image.save(path)
        paths.append(path)

    return paths, {
        "mode": "preserve_perfect_pixel_frames",
        "resized": False,
        "shared_palette": bool(shared_palette),
        "shared_palette_colors": shared_palette_hex,
        "frame_meta": per_frame_meta,
    }


def compose_horizontal_sprite_sheet(frame_paths: list[Path], out_path: str | Path) -> Path:
    frames = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    sheet = _compose_mosaic(frames)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def compose_gif(frame_paths: list[Path], out_path: str | Path, *, duration_ms: int, loop: int = 0) -> Path:
    frames: list[Image.Image] = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    if not frames:
        raise ValueError("没有可用于合成 GIF 的帧")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    first, rest = frames[0], frames[1:]
    first.save(
        target,
        save_all=True,
        append_images=rest,
        duration=max(20, int(duration_ms)),
        loop=max(0, int(loop)),
        disposal=2,
    )
    return target


def _write_sprite_input_debug(
    path: Path,
    *,
    raw_prompt: str,
    normalized_description: str,
    effective_prompt: str,
    rows: int,
    cols: int,
    pixel_size: tuple[int, int],
    colors: int,
    key_color: str,
    key_tolerance: int,
) -> None:
    sheet_size = (cols * pixel_size[0], rows * pixel_size[1])
    frame_bounds = _sprite_frame_bounds(rows, cols, pixel_size[0], pixel_size[1])
    path.write_text(
        "[raw_prompt]\n"
        f"{raw_prompt}\n\n"
        "[normalized_description]\n"
        f"{normalized_description}\n\n"
        "[sprite_settings]\n"
        f"rows={rows}\n"
        f"cols={cols}\n"
        f"frame_size={pixel_size[0]}x{pixel_size[1]}\n"
        f"logical_sheet_size={sheet_size[0]}x{sheet_size[1]}\n"
        f"frame_bounds={frame_bounds}\n"
        f"max_colors={colors}\n"
        f"key_color={key_color}\n"
        f"key_tolerance={key_tolerance}\n\n"
        "[effective_prompt]\n"
        f"{effective_prompt}\n",
        encoding="utf-8",
    )


def run_sprite_pipeline(
    cfg: AppConfig,
    inputs: SpritePipelineInput,
    progress: ProgressCb | None = None,
) -> SpritePipelineResult:
    """执行：prompt → 九宫格生图 → 9 帧 → 横向精灵表 + GIF。"""

    notify = progress or _noop
    if not (inputs.prompt or "").strip():
        raise ValueError("必须提供动画精灵表 prompt")

    rows = max(1, int(inputs.rows or cfg.sprite.rows))
    cols = max(1, int(inputs.cols or cfg.sprite.cols))
    expected_count = rows * cols
    if expected_count != 9:
        # 当前功能以九宫格为产品合同；保留 rows/cols 主要方便测试与未来扩展。
        raise ValueError("动画精灵表当前固定为 3x3 / 9 帧")

    out_root = Path(inputs.out_root or cfg.output.root)
    run_dir = new_run_dir(out_root, seed=f"sprite\n{inputs.prompt}")
    notify("sprite_run_start", {"run_dir": str(run_dir)})

    try:
        guard = validate_user_prompt(cfg, inputs.prompt)
    except PromptPolicyError as exc:
        notify("prompt_guard_rejected", exc.result.to_metadata())
        raise ValueError(str(exc)) from exc
    prompt_guard_meta = guard.to_metadata()
    description = guard.normalized_description or inputs.prompt
    notify("prompt_guard_ready", prompt_guard_meta)

    pixel_size = _size_tuple(inputs.pixelize_params.output_size, tuple(cfg.sprite.pixel_size))
    key_hex, _key_rgb = resolve_key_color(cfg.sprite.green_screen_color, description)
    key_mode = _normalized_key_mode(inputs.key_mode or cfg.sprite.key_mode)
    key_tolerance = int(cfg.sprite.green_screen_tolerance if inputs.key_tolerance is None else inputs.key_tolerance)
    key_softness = int(cfg.sprite.key_softness if inputs.key_softness is None else inputs.key_softness)
    key_alpha_floor = int(cfg.sprite.key_alpha_floor if inputs.key_alpha_floor is None else inputs.key_alpha_floor)
    key_despill = bool(cfg.sprite.key_despill if inputs.key_despill is None else inputs.key_despill)
    max_colors = int(inputs.pixelize_params.colors or cfg.sprite.colors)
    effective_prompt = build_sprite_sheet_prompt(
        cfg,
        description,
        target_size=pixel_size,
        rows=rows,
        cols=cols,
        max_colors=max_colors,
        key_tolerance=key_tolerance,
    )
    _write_sprite_input_debug(
        run_dir / "00_input.txt",
        raw_prompt=inputs.prompt,
        normalized_description=description,
        effective_prompt=effective_prompt,
        rows=rows,
        cols=cols,
        pixel_size=pixel_size,
        colors=max_colors,
        key_color=key_hex,
        key_tolerance=key_tolerance,
    )
    source_path = run_dir / "01_sprite_grid.png"
    preprocessed_sheet_path = run_dir / "02_perfect_pixel_sheet.png"
    alpha_sheet_path = run_dir / "03_color_to_alpha_sheet.png"
    raw_dir = run_dir / "04_frames_raw"
    frames_dir = run_dir / "05_frames"
    sheet_path = run_dir / "06_sprite_sheet.png"
    gif_path = run_dir / "07_sprite.gif"
    cache = Cache(cfg.cache.dir, enabled=cfg.cache.enabled and inputs.use_cache)
    material = {
        "prompt": effective_prompt,
        "user_prompt": inputs.prompt,
        "rows": rows,
        "cols": cols,
        "size": inputs.image_size or cfg.image_gen.size,
        "quality": inputs.image_quality or cfg.sprite.image_quality,
        "model": inputs.image_model or cfg.image_gen.model,
        "output_format": cfg.image_gen.output_format,
    }
    cached = None if inputs.refresh_cache else cache.lookup("sprite_imagegen", material, "png")
    if cached is not None:
        source_path.write_bytes(cached.read_bytes())
        notify("sprite_source_ready", {"path": str(source_path), "mode": "cache"})
    else:
        notify("sprite_image_gen_start", {"prompt": effective_prompt, **material})
        generate_image(
            cfg,
            effective_prompt,
            source_path,
            size=inputs.image_size or cfg.image_gen.size,
            quality=inputs.image_quality or cfg.sprite.image_quality,
            model=inputs.image_model,
        )
        cache.store_copy("sprite_imagegen", material, "png", source_path)
        notify("sprite_source_ready", {"path": str(source_path), "mode": "generated"})

    with _local_stage(inputs.local_stage_context):
        split = split_sprite_sheet(
            source_path,
            raw_dir,
            rows=rows,
            cols=cols,
            key_color=key_hex,
            tolerance=key_tolerance,
            crop_padding=cfg.sprite.crop_padding,
            crop_square=cfg.sprite.crop_square,
            key_mode=key_mode,
            key_softness=key_softness,
            key_alpha_floor=key_alpha_floor,
            key_despill=key_despill,
            target_size=pixel_size,
            cfg=cfg,
            generated_preprocess_method=inputs.pixelize_params.generated_preprocess_method,
            preprocessed_sheet_path=preprocessed_sheet_path,
            alpha_sheet_path=alpha_sheet_path,
        )
        notify("sprite_frames_split", {"count": len(split.raw_frames), "dir": str(raw_dir)})

        params = PixelizeParams(
            output_size=pixel_size,
            colors=max_colors,
            dither=inputs.pixelize_params.dither,
            preset=inputs.pixelize_params.preset,
            preview_scale=0,
            edge_enhance=inputs.pixelize_params.edge_enhance,
            saturation=inputs.pixelize_params.saturation,
            resample=inputs.pixelize_params.resample,
            snap_to_grid=inputs.pixelize_params.snap_to_grid,
            remove_bg=False,
            bg_tolerance=cfg.sprite.bg_tolerance,
            bg_feather=inputs.pixelize_params.bg_feather,
            edge_style=inputs.pixelize_params.edge_style,
            auto_crop=False,
            crop_padding=cfg.sprite.crop_padding,
            crop_square=cfg.sprite.crop_square,
            palette_mode="auto",
        )
        frame_paths, frame_meta = pixelize_sprite_frames(
            split.raw_frames,
            frames_dir,
            params,
            shared_palette=cfg.sprite.shared_palette,
            cfg=cfg,
            source_description=inputs.prompt,
        )
        notify("sprite_frames_finalized", {"count": len(frame_paths), "dir": str(frames_dir)})

        compose_horizontal_sprite_sheet(frame_paths, sheet_path)
        duration_ms = int(inputs.duration_ms or cfg.sprite.duration_ms)
        loop = int(cfg.sprite.loop if inputs.loop is None else inputs.loop)
        compose_gif(frame_paths, gif_path, duration_ms=duration_ms, loop=loop)
        notify("sprite_outputs_ready", {"sheet": str(sheet_path), "gif": str(gif_path)})

        frames = [
            SpriteFrame(
                index=index,
                row=(index - 1) // cols,
                col=(index - 1) % cols,
                raw_path=raw,
                path=path,
                bbox=split.bboxes[index - 1] if index - 1 < len(split.bboxes) else None,
            )
            for index, (raw, path) in enumerate(zip(split.raw_frames, frame_paths, strict=True), start=1)
        ]
    meta = {
        "version": __version__,
        "input": {
            "prompt": inputs.prompt,
            "effective_prompt": effective_prompt,
        },
        "prompt_guard": prompt_guard_meta,
        "image_gen": {
            "model": inputs.image_model or cfg.image_gen.model,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.sprite.image_quality,
            "output_format": cfg.image_gen.output_format,
            "used": True,
            "mode": "sprite_sheet",
        },
        "sprite": {
            "rows": rows,
            "cols": cols,
            "count": len(frames),
            "frame_size": list(pixel_size),
            "colors": params.colors,
            "duration_ms": duration_ms,
            "loop": loop,
            "green_screen_color": key_hex,
            "green_screen_tolerance": key_tolerance,
            "frame_background_flow": "sheet_perfect_pixel_to_color_to_alpha_equal_split_transparent_pad",
            "key_mode": key_mode,
            "key_softness": key_softness,
            "key_alpha_floor": key_alpha_floor,
            "key_despill": key_despill,
            "crop_box": list(split.crop_box) if split.crop_box else None,
            "preprocess": split.preprocess_meta,
            "source_sheet": source_path.name,
            "perfect_pixel_sheet": preprocessed_sheet_path.name,
            "color_to_alpha_sheet": alpha_sheet_path.name,
            "sheet_canvas_size": list(split.sheet_canvas_size) if split.sheet_canvas_size else None,
            "split_cell_size": list(split.cell_size) if split.cell_size else None,
            "frame_canvas_size": list(split.frame_canvas_size) if split.frame_canvas_size else None,
            "raw_frames_dir": raw_dir.name,
            "frames_dir": frames_dir.name,
            "horizontal_sheet": sheet_path.name,
            "gif": gif_path.name,
            "frames": [frame.to_metadata(run_dir) for frame in frames],
            "pixelize": frame_meta,
        },
        "cache": {"enabled": cache.enabled, "refresh": inputs.refresh_cache},
        "outputs": {
            "source": source_path.name,
            "perfect_pixel_sheet": preprocessed_sheet_path.name,
            "color_to_alpha_sheet": alpha_sheet_path.name,
            "sprite_frames": frames_dir.name,
            "sprite_sheet": sheet_path.name,
            "sprite_gif": gif_path.name,
            "pixelized": sheet_path.name,
            "preview": gif_path.name,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return SpritePipelineResult(
        run_dir=run_dir,
        source_path=source_path,
        frame_paths=frame_paths,
        pixel_path=sheet_path,
        preview_path=gif_path,
        meta_path=meta_path,
        meta=meta,
    )
