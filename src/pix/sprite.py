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
from pix.pixelize.core import PixelizeParams, pixelize
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


def build_sprite_sheet_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int] | None = None,
    rows: int | None = None,
    cols: int | None = None,
) -> str:
    """构造专用于 3×3 动画关键帧九宫格的受控 prompt。"""

    sprite_cfg = cfg.sprite
    safe_rows = max(1, int(rows or sprite_cfg.rows))
    safe_cols = max(1, int(cols or sprite_cfg.cols))
    width, height = target_size or sprite_cfg.pixel_size
    key_hex, _key_rgb = resolve_key_color(sprite_cfg.green_screen_color, description)
    values = {
        "description": description.strip(),
        "rows": safe_rows,
        "cols": safe_cols,
        "count": safe_rows * safe_cols,
        "green": key_hex,
        "key_color": key_hex,
        "key_tolerance": int(sprite_cfg.green_screen_tolerance),
        "max_colors": int(sprite_cfg.colors),
        "width": int(width),
        "height": int(height),
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
        f"Each grid cell must be one {values['width']}x{values['height']} sprite frame, "
        "where each pixel is one square grid cell. Use large, chunky readable pixels, limited colors, "
        "and a clear silhouette in every frame. "
        f"Use no more than {values['max_colors']} visible subject/effect colors per frame; background color does not count. "
        "Read order is left-to-right, top-to-bottom. Keep the same character, camera angle, scale, anchor point, "
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
) -> SpriteSplitResult:
    """把模型生成的九宫格动画图切成连续帧，并统一裁剪区域。

    每帧先按素材同款顺序执行 perfectPixel 网格对齐，再用四角纯色作为 key 的
    Color-to-Alpha 去背景；随后把不同检测尺寸居中到共同透明画布，再计算 9 帧联合裁剪框。
    key_* 参数保留为历史兼容字段，当前不再走 sprite 专用 key 透明分支。
    """

    _ = (key_color, key_mode, key_softness, key_alpha_floor, key_despill)
    source_path = Path(image_path)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    transparent_cells: list[Image.Image] = []
    normalized_cells: list[Image.Image] = []
    bboxes: list[tuple[int, int, int, int] | None] = []
    raw_frames: list[Path] = []
    crop_box: tuple[int, int, int, int] | None = None

    with Image.open(source_path) as opened:
        image = opened.convert("RGBA")
        cell_w = image.width / safe_cols
        cell_h = image.height / safe_rows
        for row in range(safe_rows):
            for col in range(safe_cols):
                left = int(round(col * cell_w))
                top = int(round(row * cell_h))
                right = int(round((col + 1) * cell_w))
                bottom = int(round((row + 1) * cell_h))
                cell = image.crop((left, top, right, bottom))
                preprocessed = preprocess_generated_image(
                    cell,
                    method=generated_preprocess_method,
                    target_size=target_size,
                ).image
                transparent = remove_background(
                    preprocessed,
                    tolerance=max(0, int(tolerance)),
                    feather=0,
                    edge_style="hard",
                    keep_border_bleed=True,
                    **_sprite_bg_removal_options(cfg, tolerance=tolerance),
                )
                transparent_cells.append(remove_translucent_edge_halo(transparent))

    if transparent_cells:
        canvas_size = (
            max(frame.width for frame in transparent_cells),
            max(frame.height for frame in transparent_cells),
        )
        normalized_cells = [_center_on_transparent_canvas(frame, canvas_size) for frame in transparent_cells]
        bboxes = [_visible_bbox(frame) for frame in normalized_cells]

    union = _union_bboxes(bboxes)
    if union is not None and normalized_cells:
        crop_box = _expand_crop_box(
            union,
            normalized_cells[0].size,
            padding=crop_padding,
            square=crop_square,
        )

    for index, cell in enumerate(normalized_cells, start=1):
        frame = cell.crop(crop_box) if crop_box is not None else cell
        frame_path = dest / f"frame_{index:02d}.png"
        frame.save(frame_path)
        raw_frames.append(frame_path)

    return SpriteSplitResult(
        source_path=source_path,
        raw_frames=raw_frames,
        bboxes=bboxes,
        crop_box=crop_box,
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
    """逐帧像素化，并可用共享调色板统一全部帧。"""

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    frame_params = PixelizeParams(
        output_size=params.output_size,
        colors=params.colors,
        dither=params.dither,
        preset=params.preset,
        preview_scale=0,
        edge_enhance=params.edge_enhance,
        saturation=params.saturation,
        resample=params.resample,
        snap_to_grid=params.snap_to_grid,
        remove_bg=False,
        bg_tolerance=params.bg_tolerance,
        bg_feather=params.bg_feather,
        edge_style=params.edge_style,
        auto_crop=False,
        crop_padding=params.crop_padding,
        crop_square=params.crop_square,
        palette_mode="auto",
    )
    images: list[Image.Image] = []
    per_frame_meta: list[dict[str, Any]] = []
    for raw in raw_frames:
        frame_img, _preview, meta = pixelize(
            raw,
            frame_params,
            cfg=cfg,
            source_description=source_description,
            auto_skip_redundant_bg=True,
        )
        images.append(frame_img.convert("RGBA"))
        per_frame_meta.append(meta)

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
    (run_dir / "00_input.txt").write_text(f"prompt={inputs.prompt}\n", encoding="utf-8")

    try:
        guard = validate_user_prompt(cfg, inputs.prompt)
    except PromptPolicyError as exc:
        notify("prompt_guard_rejected", exc.result.to_metadata())
        raise ValueError(str(exc)) from exc
    prompt_guard_meta = guard.to_metadata()
    description = guard.normalized_description or inputs.prompt
    notify("prompt_guard_ready", prompt_guard_meta)

    pixel_size = _size_tuple(inputs.pixelize_params.output_size, tuple(cfg.sprite.pixel_size))
    effective_prompt = build_sprite_sheet_prompt(
        cfg,
        description,
        target_size=pixel_size,
        rows=rows,
        cols=cols,
    )
    key_hex, _key_rgb = resolve_key_color(cfg.sprite.green_screen_color, description)
    key_mode = _normalized_key_mode(inputs.key_mode or cfg.sprite.key_mode)
    key_tolerance = int(cfg.sprite.green_screen_tolerance if inputs.key_tolerance is None else inputs.key_tolerance)
    key_softness = int(cfg.sprite.key_softness if inputs.key_softness is None else inputs.key_softness)
    key_alpha_floor = int(cfg.sprite.key_alpha_floor if inputs.key_alpha_floor is None else inputs.key_alpha_floor)
    key_despill = bool(cfg.sprite.key_despill if inputs.key_despill is None else inputs.key_despill)
    source_path = run_dir / "01_sprite_grid.png"
    raw_dir = run_dir / "02_frames_raw"
    frames_dir = run_dir / "03_frames"
    sheet_path = run_dir / "04_sprite_sheet.png"
    gif_path = run_dir / "05_sprite.gif"
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
        )
        notify("sprite_frames_split", {"count": len(split.raw_frames), "dir": str(raw_dir)})

        params = PixelizeParams(
            output_size=pixel_size,
            colors=int(inputs.pixelize_params.colors or cfg.sprite.colors),
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
        notify("sprite_frames_pixelized", {"count": len(frame_paths), "dir": str(frames_dir)})

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
            "frame_background_flow": "perfect_pixel_to_color_to_alpha",
            "key_mode": key_mode,
            "key_softness": key_softness,
            "key_alpha_floor": key_alpha_floor,
            "key_despill": key_despill,
            "crop_box": list(split.crop_box) if split.crop_box else None,
            "source_sheet": source_path.name,
            "frames_dir": frames_dir.name,
            "horizontal_sheet": sheet_path.name,
            "gif": gif_path.name,
            "frames": [frame.to_metadata(run_dir) for frame in frames],
            "pixelize": frame_meta,
        },
        "cache": {"enabled": cache.enabled, "refresh": inputs.refresh_cache},
        "outputs": {
            "source": source_path.name,
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
