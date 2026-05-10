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


_ROLE_ORDER = ("outline", "shadow", "primary", "secondary", "accent", "highlight")


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
    source_path = Path(image_path)
    with Image.open(source_path) as opened:
        image = opened.convert("RGBA" if ("A" in opened.getbands() or "transparency" in opened.info) else "RGB")

    original_size = image.size
    crop_bbox: tuple[int, int, int, int] | None = None
    if params.auto_crop:
        image, crop_bbox = _auto_crop(
            image,
            bg_tolerance=params.bg_tolerance,
            padding=params.crop_padding,
            square=params.crop_square,
        )

    if params.remove_bg:
        image = remove_background(
            image,
            tolerance=max(0, int(params.bg_tolerance)),
            feather=0,
            keep_border_bleed=True,
        )
    else:
        image = image.convert("RGBA")

    detected_grid = _detect_grid_size(image.convert("RGB"))
    width, height = params.output_size
    colors, transparent_mask = _sample_cells(
        image,
        output_size=params.output_size,
        alpha_threshold=params.alpha_threshold,
        sample_ratio=params.sample_ratio,
    )
    if params.remove_bg:
        transparent_mask = _mark_border_background_transparent(
            colors,
            transparent_mask,
            output_size=params.output_size,
            tolerance=params.bg_tolerance,
        )
    palette_rgb, pixels = _cluster_cell_colors(
        colors,
        transparent_mask,
        output_size=params.output_size,
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
        "crop_bbox": list(crop_bbox) if crop_bbox else None,
        "detected_grid": detected_grid,
        "source_cell_size": [image.width / width, image.height / height],
        "grid_confidence": _grid_confidence(image.size, params.output_size, detected_grid),
        "max_colors": params.max_colors,
        "remove_bg": params.remove_bg,
        "bg_tolerance": params.bg_tolerance,
        "sample_ratio": params.sample_ratio,
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
    ratio = min(1.0, max(0.1, float(sample_ratio)))
    colors: list[tuple[int, int, int] | None] = []
    transparent: list[bool] = []

    for y in range(out_h):
        y0 = int(round(y * img_h / out_h))
        y1 = int(round((y + 1) * img_h / out_h))
        for x in range(out_w):
            x0 = int(round(x * img_w / out_w))
            x1 = int(round((x + 1) * img_w / out_w))
            patch = rgba[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1), :]
            patch = _center_crop_patch(patch, ratio)
            alpha = patch[..., 3]
            visible = alpha > max(0, int(alpha_threshold))
            if visible.mean() < 0.28:
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


def _mark_border_background_transparent(
    colors: list[tuple[int, int, int] | None],
    transparent: list[bool],
    *,
    output_size: tuple[int, int],
    tolerance: int,
) -> list[bool]:
    """从采样网格边缘推断连通背景，并标为透明。

    这一步专门处理“高清白底伪像素图裁剪后 remove_background 失效”的情况：
    即使源图 alpha 全不透明，也可以根据边缘主色把白底 cell 转成 -1。
    """
    width, height = output_size
    if len(colors) != width * height:
        return transparent

    def _idx(x: int, y: int) -> int:
        return y * width + x

    border_colors: list[tuple[int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if x not in (0, width - 1) and y not in (0, height - 1):
                continue
            i = _idx(x, y)
            if transparent[i] or colors[i] is None:
                continue
            border_colors.append(colors[i])
    if not border_colors:
        return transparent

    ref = tuple(int(v) for v in np.median(np.asarray(border_colors, dtype=np.float32), axis=0))
    tol_sq = max(0, int(tolerance)) ** 2 * 3
    visible_colors = [c for c, t in zip(colors, transparent) if not t and c is not None]
    if visible_colors:
        close_ratio = sum(1 for c in visible_colors if _rgb_distance_sq(c, ref) <= tol_sq) / len(visible_colors)
        # 如果几乎整张图都接近边缘色，说明主体可能已经被裁到铺满画布，
        # 贸然把边缘连通色当背景会把主体整张抠空。
        if close_ratio > 0.85:
            return transparent
    result = list(transparent)
    seen = set()
    queue: list[tuple[int, int]] = []
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.pop(0)
        if (x, y) in seen:
            continue
        seen.add((x, y))
        i = _idx(x, y)
        if result[i]:
            pass
        else:
            color = colors[i]
            if color is None or _rgb_distance_sq(color, ref) > tol_sq:
                continue
            result[i] = True
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen:
                queue.append((nx, ny))
    return result


def _cluster_cell_colors(
    colors: list[tuple[int, int, int] | None],
    transparent: list[bool],
    *,
    output_size: tuple[int, int],
    max_colors: int,
) -> tuple[list[tuple[int, int, int]], list[list[int]]]:
    visible = [c for c, is_transparent in zip(colors, transparent) if not is_transparent and c is not None]
    if not visible:
        return [(0, 0, 0)], _reshape_pixels([-1 for _ in colors], output_size)

    unique = list(dict.fromkeys(visible))
    k = min(max_colors, len(unique))
    palette = _make_palette(unique, k)
    flat_pixels: list[int] = []
    for color, is_transparent in zip(colors, transparent):
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
