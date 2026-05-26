"""从高清伪像素图提取 Pixel Grid JSON。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

from pix.grid.schema import PixelGrid, PixelGridAxes, PixelGridCanvas, PixelGridColor
from pix.pixelize.bg_removal import remove_background
from pix.pixelize.core import _auto_crop, _detect_grid_size
from pix.pixelize.perfect_pixel import preprocess_generated_image


def _bg_removal_options(cfg) -> dict:
    asset = getattr(cfg, "asset", None)
    if asset is None:
        return {}
    return {
        "bg_removal_algorithm": getattr(asset, "bg_removal_algorithm", "auto"),
        "color_to_alpha_shape": getattr(asset, "color_to_alpha_shape", "sphere"),
        "color_to_alpha_transparency": getattr(asset, "color_to_alpha_transparency", 48),
        "color_to_alpha_opacity": getattr(asset, "color_to_alpha_opacity", 255),
        "color_to_alpha_interpolation": getattr(asset, "color_to_alpha_interpolation", "linear"),
    }


@dataclass(frozen=True)
class GridExtractParams:
    output_size: tuple[int, int] = (16, 16)
    max_colors: int = 12
    auto_crop: bool = True
    crop_padding: float = 0.12
    crop_square: bool = True
    remove_bg: bool = True
    bg_tolerance: int = 26
    alpha_threshold: int = 8
    sample_ratio: float = 0.62


@dataclass(frozen=True)
class GridAlignedSize:
    """源图按像素格对齐后的 draft 网格尺寸推断结果。"""

    output_size: tuple[int, int]
    original_size: tuple[int, int]
    processed_size: tuple[int, int]
    crop_bbox: tuple[int, int, int, int] | None
    detected_grid: int
    source_cell_size: tuple[float, float]
    capped: bool
    fallback: bool
    max_axis: int

    def to_metadata(self) -> dict:
        return {
            "output_size": list(self.output_size),
            "original_size": list(self.original_size),
            "processed_size": list(self.processed_size),
            "crop_bbox": list(self.crop_bbox) if self.crop_bbox else None,
            "detected_grid": self.detected_grid,
            "source_cell_size": list(self.source_cell_size),
            "capped": self.capped,
            "fallback": self.fallback,
            "max_axis": self.max_axis,
        }


_ROLE_ORDER = ("outline", "shadow", "primary", "secondary", "accent", "highlight")


def infer_grid_aligned_output_size(
    image_path: str | Path,
    *,
    auto_crop: bool = True,
    crop_padding: float = 0.12,
    crop_square: bool = True,
    remove_bg: bool = True,
    bg_tolerance: int = 26,
    max_axis: int = 64,
    generated_preprocess_method: str | None = None,
) -> GridAlignedSize:
    """从源图推断 draft 网格尺寸，用于辅助 extract 时对齐网格。

    优先使用输入图自身的像素格周期：例如 128x128 的源图若由 4x4 网格
    nearest 放大得到，会推断出 4x4，而不是硬压到最终 16x16。若没有明显
    像素格，则使用处理后源图比例并限制最大轴。
    """
    _source_path, image, original_size = _load_source_image(image_path)
    generated_preprocess = preprocess_generated_image(
        image,
        method=generated_preprocess_method if generated_preprocess_method is not None else "legacy",
        target_size=None,
    )
    image = generated_preprocess.image
    crop_bbox: tuple[int, int, int, int] | None = None
    if auto_crop:
        image, crop_bbox = _auto_crop(
            image,
            bg_tolerance=bg_tolerance,
            padding=crop_padding,
            square=crop_square,
        )
    if remove_bg:
        image = remove_background(
            image,
            tolerance=max(0, int(bg_tolerance)),
            feather=0,
            keep_border_bleed=True,
        )
    else:
        image = image.convert("RGBA")
    detected_grid = _detect_source_grid_size(
        image.convert("RGB"),
        max_probe=max(24, int(max_axis) * 4),
    )
    fallback = detected_grid <= 1
    if fallback:
        raw_size = image.size
        source_cell_size = (1.0, 1.0)
    else:
        raw_size = (
            max(1, int(round(image.width / detected_grid))),
            max(1, int(round(image.height / detected_grid))),
        )
        source_cell_size = (float(detected_grid), float(detected_grid))
    output_size, capped = _cap_size_to_max_axis(raw_size, max_axis=max_axis)
    return GridAlignedSize(
        output_size=output_size,
        original_size=original_size,
        processed_size=image.size,
        crop_bbox=crop_bbox,
        detected_grid=detected_grid,
        source_cell_size=source_cell_size,
        capped=capped,
        fallback=fallback,
        max_axis=max(1, int(max_axis)),
    )


def extract_pixel_grid(
    image_path: str | Path,
    *,
    output_size: tuple[int, int] = (16, 16),
    max_colors: int = 12,
    auto_crop: bool = True,
    crop_padding: float = 0.12,
    crop_square: bool = True,
    remove_bg: bool = True,
    bg_tolerance: int = 26,
    alpha_threshold: int = 8,
    sample_ratio: float = 0.62,
    metadata: dict | None = None,
    generated_preprocess_method: str | None = None,
    preprocess_output_path: str | Path | None = None,
    cfg=None,
) -> PixelGrid:
    """把一张伪像素图抽取成严格的 PixelGrid。

    关键思想：目标输出尺寸就是最终像素网格尺寸，Python 负责从每个 cell 的中心区域
    采样主色/透明度，再把相近颜色合并成有限调色板。
    """
    params = GridExtractParams(
        output_size=output_size,
        max_colors=max_colors,
        auto_crop=auto_crop,
        crop_padding=crop_padding,
        crop_square=crop_square,
        remove_bg=remove_bg,
        bg_tolerance=bg_tolerance,
        alpha_threshold=alpha_threshold,
        sample_ratio=sample_ratio,
    )
    source_path, image, original_size = _load_source_image(image_path)
    generated_preprocess = preprocess_generated_image(
        image,
        method=generated_preprocess_method if generated_preprocess_method is not None else "legacy",
        target_size=params.output_size,
    )
    image = generated_preprocess.image
    if preprocess_output_path is not None and generated_preprocess.meta.get("method") == "perfect_pixel":
        preprocess_path = Path(preprocess_output_path)
        preprocess_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(preprocess_path)
        generated_preprocess.meta["output_path"] = str(preprocess_path)
    crop_bbox: tuple[int, int, int, int] | None = None
    tight_crop = bool(generated_preprocess.meta.get("applied"))
    if params.remove_bg:
        image = remove_background(
            image,
            tolerance=max(0, int(params.bg_tolerance)),
            feather=0,
            keep_border_bleed=True,
            **_bg_removal_options(cfg),
        )
    else:
        image = image.convert("RGBA")
    if params.auto_crop:
        image, crop_bbox = _auto_crop(
            image,
            bg_tolerance=params.bg_tolerance,
            padding=0.0 if tight_crop else params.crop_padding,
            square=False if tight_crop else params.crop_square,
            tight=tight_crop,
        )

    requested_output_size = params.output_size
    effective_output_size = params.output_size
    canvas_pad_meta: dict = {"applied": False}
    if tight_crop and params.auto_crop:
        image, canvas_pad_meta = _pad_to_rounded_square_canvas(image)
        effective_output_size = image.size

    detected_grid = _detect_source_grid_size(
        image.convert("RGB"),
        max_probe=max(24, int(max(image.size) / max(1, min(effective_output_size)))),
    )
    width, height = effective_output_size
    colors, transparent_mask = _sample_cells(
        image,
        output_size=effective_output_size,
        alpha_threshold=params.alpha_threshold,
        sample_ratio=params.sample_ratio,
    )
    sampled_transparent_ratio = sum(1 for item in transparent_mask if item) / max(1, len(transparent_mask))
    palette_rgb, pixels = _cluster_cell_colors(
        colors,
        transparent_mask,
        output_size=effective_output_size,
        max_colors=max(2, min(256, int(params.max_colors))),
    )
    palette = [
        PixelGridColor(id=i, hex=_rgb_to_hex(rgb), role=_guess_role(rgb, palette_rgb))
        for i, rgb in enumerate(palette_rgb)
    ]

    meta = {
        "source": str(source_path),
        "original_size": list(original_size),
        "processed_size": list(image.size),
        "requested_output_size": list(requested_output_size),
        "effective_output_size": list(effective_output_size),
        "crop_bbox": list(crop_bbox) if crop_bbox else None,
        "detected_grid": detected_grid,
        "source_cell_size": [image.width / width, image.height / height],
        "grid_confidence": _grid_confidence(image.size, effective_output_size, detected_grid),
        "generated_preprocess": generated_preprocess.meta,
        "preprocess_order": ["perfect_pixel", "remove_background", "auto_crop", "transparent_canvas_pad"],
        "auto_crop_policy": "tight_after_perfect_pixel" if tight_crop else "configured_padding",
        "canvas_pad": canvas_pad_meta,
        "max_colors": params.max_colors,
        "remove_bg": params.remove_bg,
        "bg_tolerance": params.bg_tolerance,
        "sample_ratio": params.sample_ratio,
        "sampled_transparent_ratio": sampled_transparent_ratio,
    }
    if metadata:
        meta.update(metadata)

    return PixelGrid(
        canvas=PixelGridCanvas(width=width, height=height, transparent_index=-1),
        axes=PixelGridAxes(x=list(range(width)), y=list(range(height))),
        palette=palette,
        pixels=pixels,
        metadata=meta,
    )


def _load_source_image(image_path: str | Path) -> tuple[Path, Image.Image, tuple[int, int]]:
    source_path = Path(image_path)
    with Image.open(source_path) as opened:
        image = opened.convert("RGBA" if ("A" in opened.getbands() or "transparency" in opened.info) else "RGB")
    return source_path, image, image.size


CANVAS_SIZE_STEPS = (16, 24, 32, 48, 64, 96, 128, 256)


def _next_canvas_size(side: int, *, steps: tuple[int, ...] = CANVAS_SIZE_STEPS) -> int:
    safe_side = max(1, int(side))
    for value in steps:
        safe_value = int(value)
        if safe_side <= safe_value:
            return safe_value
    rounded = 256
    while rounded < safe_side:
        rounded *= 2
    return rounded


def _pad_to_rounded_square_canvas(
    image: Image.Image,
    *,
    size_steps: tuple[int, ...] = CANVAS_SIZE_STEPS,
) -> tuple[Image.Image, dict]:
    """不缩放图像，补透明画布到预设档位中的下一个正方形尺寸。"""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    side = max(width, height)
    rounded = _next_canvas_size(side, steps=size_steps)
    offset_x = (rounded - width) // 2
    offset_y = (rounded - height) // 2
    meta = {
        "applied": (rounded, rounded) != rgba.size,
        "source_size": [width, height],
        "output_size": [rounded, rounded],
        "size_steps": [int(value) for value in size_steps],
        "offset": [offset_x, offset_y],
    }
    if (rounded, rounded) == rgba.size:
        return rgba, meta
    canvas = Image.new("RGBA", (rounded, rounded), (0, 0, 0, 0))
    canvas.alpha_composite(rgba, (offset_x, offset_y))
    return canvas, meta


def _cap_size_to_max_axis(size: tuple[int, int], *, max_axis: int) -> tuple[tuple[int, int], bool]:
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    safe_max = max(1, int(max_axis))
    largest = max(width, height)
    if largest <= safe_max:
        return (width, height), False
    scale = safe_max / largest
    return (max(1, int(round(width * scale))), max(1, int(round(height * scale)))), True


def _detect_source_grid_size(image: Image.Image, *, max_probe: int = 128) -> int:
    """检测源图像素格边长，并在内部缩放后还原到源图尺度。"""
    gray = image.convert("L")
    orig_w, orig_h = gray.size
    scale = 1.0
    max_side = 512
    if max(orig_w, orig_h) > max_side:
        scale = max_side / max(orig_w, orig_h)
        gray = gray.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.BILINEAR)
    arr = np.asarray(gray, dtype=np.int16)
    if arr.shape[0] < 2 or arr.shape[1] < 2:
        return 1
    col_edge = np.abs(np.diff(arr, axis=1)).mean(axis=0)
    row_edge = np.abs(np.diff(arr, axis=0)).mean(axis=1)
    threshold = max(10.0, float(max(col_edge.mean(), row_edge.mean()) * 1.8))

    def _periods(edge: np.ndarray) -> list[int]:
        idxs = np.where(edge > threshold)[0]
        if len(idxs) < 3:
            return []
        max_probe_scaled = max(2, int(round(max_probe * scale)))
        deltas = np.diff(idxs)
        return [int(d) for d in deltas if 2 <= d <= max_probe_scaled]

    periods = _periods(col_edge) + _periods(row_edge)
    if not periods:
        return _detect_grid_size(image, max_probe=min(max_probe, 24))
    vals, counts = np.unique(periods, return_counts=True)
    best_scaled = int(vals[int(counts.argmax())])
    return max(1, int(round(best_scaled / scale)))


def _sample_cells(
    image: Image.Image,
    *,
    output_size: tuple[int, int],
    alpha_threshold: int,
    sample_ratio: float,
) -> tuple[list[tuple[int, int, int] | None], list[bool]]:
    """按目标网格采样，返回每个 cell 的 RGB 或 None，以及透明掩码。"""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    img_h, img_w, _ = rgba.shape
    out_w, out_h = output_size
    if img_h <= 0 or img_w <= 0 or out_w <= 0 or out_h <= 0:
        total = max(0, int(out_w) * int(out_h))
        return [None for _ in range(total)], [True for _ in range(total)]
    ratio = min(1.0, max(0.1, float(sample_ratio)))
    colors: list[tuple[int, int, int] | None] = []
    transparent: list[bool] = []

    for y in range(out_h):
        y0 = min(img_h - 1, max(0, int(round(y * img_h / out_h))))
        y1 = min(img_h, max(y0 + 1, int(round((y + 1) * img_h / out_h))))
        for x in range(out_w):
            x0 = min(img_w - 1, max(0, int(round(x * img_w / out_w))))
            x1 = min(img_w, max(x0 + 1, int(round((x + 1) * img_w / out_w))))
            patch = rgba[y0:y1, x0:x1, :]
            if patch.size == 0:
                colors.append(None)
                transparent.append(True)
                continue
            patch = _center_crop_patch(patch, ratio)
            alpha = patch[..., 3]
            visible = alpha > max(0, int(alpha_threshold))
            if visible.size == 0 or visible.mean() < 0.28:
                colors.append(None)
                transparent.append(True)
                continue
            rgb = patch[..., :3][visible]
            # 中位色比均值更抗抗锯齿/噪声。
            median = np.median(rgb.astype(np.float32), axis=0)
            color = tuple(int(v) for v in np.clip(np.rint(median), 0, 255))
            colors.append(color)
            transparent.append(False)
    return colors, transparent


def _center_crop_patch(patch: np.ndarray, ratio: float) -> np.ndarray:
    h, w = patch.shape[:2]
    ch = max(1, int(round(h * ratio)))
    cw = max(1, int(round(w * ratio)))
    y0 = max(0, (h - ch) // 2)
    x0 = max(0, (w - cw) // 2)
    return patch[y0:y0 + ch, x0:x0 + cw]



def _cluster_cell_colors(
    colors: list[tuple[int, int, int] | None],
    transparent: list[bool],
    *,
    output_size: tuple[int, int],
    max_colors: int,
) -> tuple[list[tuple[int, int, int]], list[list[int]]]:
    visible = [c for c, is_transparent in zip(colors, transparent, strict=True) if not is_transparent and c is not None]
    if not visible:
        return [(0, 0, 0)], _reshape_pixels([-1 for _ in colors], output_size)

    unique = list(dict.fromkeys(visible))
    k = min(max_colors, len(unique))
    palette = _make_palette(unique, k)
    flat_pixels: list[int] = []
    for color, is_transparent in zip(colors, transparent, strict=True):
        if is_transparent or color is None:
            flat_pixels.append(-1)
        else:
            flat_pixels.append(_nearest_palette_index(color, palette))
    return palette, _reshape_pixels(flat_pixels, output_size)


def _make_palette(colors: list[tuple[int, int, int]], k: int) -> list[tuple[int, int, int]]:
    if len(colors) <= k:
        return _sort_palette(colors)

    arr = np.asarray(colors, dtype=np.float32)
    try:
        from sklearn.cluster import KMeans

        km = KMeans(n_clusters=k, n_init=8, random_state=42)
        labels = km.fit_predict(arr)
        centers = []
        for label in range(k):
            cluster = arr[labels == label]
            if cluster.size == 0:
                continue
            centers.append(tuple(int(v) for v in np.clip(np.rint(np.median(cluster, axis=0)), 0, 255)))
        return _sort_palette(list(dict.fromkeys(centers)))
    except Exception:  # pragma: no cover - sklearn fallback
        # 简单 median-cut 风格 fallback：按亮度排序后分桶取中位色。
        sorted_colors = sorted(colors, key=lambda c: (c[0] + c[1] + c[2], c[0], c[1], c[2]))
        buckets = np.array_split(np.asarray(sorted_colors, dtype=np.float32), k)
        palette = []
        for bucket in buckets:
            if len(bucket) == 0:
                continue
            palette.append(tuple(int(v) for v in np.clip(np.rint(np.median(bucket, axis=0)), 0, 255)))
        return _sort_palette(list(dict.fromkeys(palette)))


def _sort_palette(colors: Iterable[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    # 暗色轮廓在前，高光在后，JSON 更易读。
    return sorted(dict.fromkeys(colors), key=lambda c: (_luma(c), c[0], c[1], c[2]))


def _nearest_palette_index(color: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> int:
    arr = np.asarray(palette, dtype=np.int32)
    c = np.asarray(color, dtype=np.int32)
    dist = ((arr - c) ** 2).sum(axis=1)
    return int(dist.argmin())


def _rgb_distance_sq(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    da = np.asarray(a, dtype=np.int32) - np.asarray(b, dtype=np.int32)
    return int((da * da).sum())


def _reshape_pixels(flat: list[int], output_size: tuple[int, int]) -> list[list[int]]:
    width, height = output_size
    expected = width * height
    if len(flat) != expected:
        raise ValueError(f"flat pixels 长度应为 {expected}，实际为 {len(flat)}")
    return [flat[i * width:(i + 1) * width] for i in range(height)]


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _guess_role(rgb: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> str:
    if not palette:
        return "primary"
    ordered = _sort_palette(palette)
    pos = ordered.index(rgb) if rgb in ordered else 0
    if len(ordered) == 1:
        return "primary"
    ratio = pos / max(1, len(ordered) - 1)
    idx = min(len(_ROLE_ORDER) - 1, int(round(ratio * (len(_ROLE_ORDER) - 1))))
    return _ROLE_ORDER[idx]


def _grid_confidence(
    image_size: tuple[int, int],
    output_size: tuple[int, int],
    detected_grid: int,
) -> float:
    if detected_grid <= 1:
        return 0.35
    expected = min(image_size[0] / output_size[0], image_size[1] / output_size[1])
    if expected <= 0:
        return 0.0
    ratio = min(detected_grid, expected) / max(detected_grid, expected)
    return round(float(max(0.0, min(1.0, ratio))), 3)
