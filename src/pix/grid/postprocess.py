"""Pixel Grid 后处理：清噪、统一轮廓、调色板整理。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pix.grid.schema import PixelGrid, PixelGridAxes, PixelGridCanvas, PixelGridColor
from pix.pixelize.palette import hex_to_rgb, rgb_to_hex


FitCanvasMode = Literal["smart", "contain", "stretch"]


@dataclass(frozen=True)
class GridPostprocessParams:
    cleanup: bool = True
    outline: bool = True
    outline_strength: int = 1
    min_neighbors: int = 1
    max_colors: int = 12
    force_new_outline: bool = False


@dataclass(frozen=True)
class GridFitCanvasParams:
    padding: int = 1
    mode: FitCanvasMode = "smart"
    min_axis_coverage: float = 0.7


def polish_pixel_grid(
    grid: PixelGrid,
    *,
    cleanup: bool = True,
    outline: bool = True,
    outline_strength: int = 1,
    min_neighbors: int = 1,
    max_colors: int | None = None,
    force_new_outline: bool = False,
) -> PixelGrid:
    """对 PixelGrid 做确定性后处理，返回新的 Grid。"""
    params = GridPostprocessParams(
        cleanup=cleanup,
        outline=outline,
        outline_strength=max(0, int(outline_strength)),
        min_neighbors=max(0, int(min_neighbors)),
        max_colors=max(2, int(max_colors or len(grid.palette) or 2)),
        force_new_outline=bool(force_new_outline),
    )
    pixels = [list(row) for row in grid.pixels]
    palette = [c.model_copy(deep=True) for c in grid.palette]

    meta_steps: list[str] = []
    if params.cleanup:
        pixels = _cleanup_isolated_pixels(
            pixels,
            transparent=grid.canvas.transparent_index,
            min_neighbors=params.min_neighbors,
        )
        meta_steps.append("cleanup")
    if params.outline and params.outline_strength > 0:
        outline_id, palette = _ensure_outline_color(
            palette,
            pixels,
            grid.canvas.transparent_index,
            force_new=params.force_new_outline,
        )
        pixels = _apply_outline(
            pixels,
            transparent=grid.canvas.transparent_index,
            outline_id=outline_id,
            strength=params.outline_strength,
        )
        meta_steps.append("outline")

    polished = _compact_palette(grid, palette, pixels, max_colors=params.max_colors)
    polished.metadata["postprocess"] = {
        "steps": meta_steps,
        "cleanup": params.cleanup,
        "outline": params.outline,
        "outline_strength": params.outline_strength,
        "force_new_outline": params.force_new_outline,
        "min_neighbors": params.min_neighbors,
        "max_colors": params.max_colors,
    }
    return polished


def fit_pixel_grid_to_canvas(
    grid: PixelGrid,
    *,
    padding: int = 1,
    mode: FitCanvasMode = "smart",
    min_axis_coverage: float = 0.7,
) -> PixelGrid:
    """把非透明主体确定性缩放/居中到目标画布内。

    `pix asset` 的输入常是非方形 UI 元件。仅靠生图 prompt 和自动裁剪时，
    横条/面板会出现“宽度接近画布、高度只有一半”的空洞。这里在 PixelGrid
    层处理：先按 alpha/透明索引找主体 bbox，再用 nearest-neighbor 重新采样，
    保留硬边、透明背景和调色板 id。
    """
    normalized_mode = _normalize_fit_canvas_mode(mode)
    width = grid.canvas.width
    height = grid.canvas.height
    transparent = grid.canvas.transparent_index
    pixels = [list(row) for row in grid.pixels]
    bbox = _pixel_bbox(pixels, transparent)
    metadata = dict(grid.metadata)

    if bbox is None:
        metadata["fit_canvas"] = {
            "skipped": True,
            "reason": "empty_subject",
            "mode": normalized_mode,
        }
        return _copy_grid_with_pixels(grid, pixels, metadata=metadata)

    left, top, right, bottom = bbox
    src = [row[left:right] for row in pixels[top:bottom]]
    src_w = max(1, right - left)
    src_h = max(1, bottom - top)
    pad_x = min(max(0, int(padding)), max(0, (width - 1) // 2))
    pad_y = min(max(0, int(padding)), max(0, (height - 1) // 2))
    available_w = max(1, width - pad_x * 2)
    available_h = max(1, height - pad_y * 2)
    dst_w, dst_h = _fit_canvas_dimensions(
        src_w,
        src_h,
        canvas_size=(width, height),
        available_size=(available_w, available_h),
        mode=normalized_mode,
        min_axis_coverage=min_axis_coverage,
    )
    scaled = _resize_pixels_nearest(src, dst_w, dst_h)
    out = [[transparent for _ in range(width)] for _ in range(height)]
    dst_left = pad_x + max(0, (available_w - dst_w) // 2)
    dst_top = pad_y + max(0, (available_h - dst_h) // 2)
    for y, row in enumerate(scaled):
        target_y = dst_top + y
        if target_y < 0 or target_y >= height:
            continue
        for x, value in enumerate(row):
            target_x = dst_left + x
            if target_x < 0 or target_x >= width:
                continue
            out[target_y][target_x] = value

    metadata["fit_canvas"] = {
        "skipped": False,
        "mode": normalized_mode,
        "padding": [pad_x, pad_y],
        "min_axis_coverage": float(min_axis_coverage),
        "old_bbox": [left, top, right, bottom],
        "new_bbox": list(_pixel_bbox(out, transparent) or (0, 0, 0, 0)),
        "source_size": [src_w, src_h],
        "target_size": [dst_w, dst_h],
        "old_axis_coverage": [src_w / max(1, width), src_h / max(1, height)],
        "new_axis_coverage": [dst_w / max(1, width), dst_h / max(1, height)],
    }
    return _copy_grid_with_pixels(grid, out, metadata=metadata)


def _cleanup_isolated_pixels(
    pixels: list[list[int]],
    *,
    transparent: int,
    min_neighbors: int,
) -> list[list[int]]:
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    out = [list(row) for row in pixels]
    for y in range(h):
        for x in range(w):
            val = pixels[y][x]
            if val == transparent:
                continue
            neighbors = [_safe_get(pixels, nx, ny, transparent) for nx, ny in _neighbors8(x, y)]
            solid = [n for n in neighbors if n != transparent]
            if len(solid) < min_neighbors:
                out[y][x] = transparent
                continue
            same = sum(1 for n in solid if n == val)
            if same == 0 and len(solid) >= 3:
                out[y][x] = Counter(solid).most_common(1)[0][0]
    return out


def _ensure_outline_color(
    palette: list[PixelGridColor],
    pixels: list[list[int]],
    transparent: int,
    *,
    force_new: bool = False,
) -> tuple[int, list[PixelGridColor]]:
    used = {v for row in pixels for v in row if v != transparent}
    used_palette = [c for c in palette if c.id in used]
    if not used_palette:
        return 0, [PixelGridColor(id=0, hex="#101010", role="outline")]
    outline_candidates = [c for c in palette if c.role == "outline"]
    if outline_candidates:
        return min(outline_candidates, key=lambda c: _luma(hex_to_rgb(c.hex))).id, palette
    darkest = min(used_palette, key=lambda c: _luma(hex_to_rgb(c.hex)))
    # 默认配置后处理沿用“最暗色足够暗就复用”的保守策略；
    # 用户显式选择描边时强制生成更深的 outline，避免选项看起来没有生效。
    if not force_new and _luma(hex_to_rgb(darkest.hex)) < 90:
        darkest.role = "outline"
        return darkest.id, palette
    rgb = hex_to_rgb(darkest.hex)
    darkened = tuple(max(0, int(v * 0.42)) for v in rgb)
    new_id = max([c.id for c in palette] + [-1]) + 1
    palette.append(PixelGridColor(id=new_id, hex=rgb_to_hex(darkened), role="outline"))
    return new_id, palette


def _apply_outline(
    pixels: list[list[int]],
    *,
    transparent: int,
    outline_id: int,
    strength: int,
) -> list[list[int]]:
    result = [list(row) for row in pixels]
    for _ in range(strength):
        result = _apply_outline_once(result, transparent=transparent, outline_id=outline_id)
    return result


def _apply_outline_once(
    pixels: list[list[int]],
    *,
    transparent: int,
    outline_id: int,
) -> list[list[int]]:
    """向主体外侧补轮廓，尽量不覆盖主体内部颜色。

    早期实现会把所有边界主体像素改成 outline，细小图标容易被黑边“吃掉”。
    这里改为在透明邻居处补 outline，并避开画布最外圈，避免资源贴边。
    """
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    out = [list(row) for row in pixels]
    for y in range(h):
        for x in range(w):
            if pixels[y][x] != transparent:
                continue
            if x <= 0 or y <= 0 or x >= w - 1 or y >= h - 1:
                continue
            solid_neighbors = [
                _safe_get(pixels, nx, ny, transparent)
                for nx, ny in _neighbors8(x, y)
                if _safe_get(pixels, nx, ny, transparent) != transparent
            ]
            if not solid_neighbors:
                continue
            # 只补贴着主体的上下左右透明格；不再因为对角邻居补色，
            # 避免斜边/凹角处被填成 2x2 黑块。
            cardinal_solid = any(
                _safe_get(pixels, nx, ny, transparent) != transparent
                for nx, ny in _neighbors4(x, y)
            )
            if cardinal_solid:
                out[y][x] = outline_id
    return out


def _compact_palette(
    original: PixelGrid,
    palette: list[PixelGridColor],
    pixels: list[list[int]],
    *,
    max_colors: int,
) -> PixelGrid:
    transparent = original.canvas.transparent_index
    used = sorted({v for row in pixels for v in row if v != transparent})
    palette_by_id = {c.id: c for c in palette}
    used_colors = [palette_by_id[i] for i in used if i in palette_by_id]
    if len(used_colors) > max_colors:
        pixels, used_colors = _merge_extra_colors(pixels, used_colors, max_colors=max_colors, transparent=transparent)
    id_map = {c.id: idx for idx, c in enumerate(used_colors)}
    new_palette = [
        PixelGridColor(id=id_map[c.id], hex=c.hex, role=c.role, name=c.name)
        for c in used_colors
    ]
    new_pixels = [
        [transparent if v == transparent else id_map.get(v, transparent) for v in row]
        for row in pixels
    ]
    metadata = dict(original.metadata)
    metadata["palette_compacted"] = True
    return PixelGrid(
        version=original.version,
        canvas=PixelGridCanvas(
            width=original.canvas.width,
            height=original.canvas.height,
            transparent_index=transparent,
        ),
        axes=PixelGridAxes(x=list(original.axes.x), y=list(original.axes.y)),
        palette=new_palette,
        pixels=new_pixels,
        metadata=metadata,
    )


def _merge_extra_colors(
    pixels: list[list[int]],
    colors: list[PixelGridColor],
    *,
    max_colors: int,
    transparent: int,
) -> tuple[list[list[int]], list[PixelGridColor]]:
    protected = [c for c in colors if c.role == "outline"]
    rest = [c for c in colors if c.role != "outline"]
    keep = protected[:1] + rest[: max(0, max_colors - len(protected[:1]))]
    if not keep:
        keep = colors[:max_colors]
    keep_ids = {c.id for c in keep}
    keep_rgb = {c.id: hex_to_rgb(c.hex) for c in keep}
    remap: dict[int, int] = {}
    for c in colors:
        if c.id in keep_ids:
            remap[c.id] = c.id
        else:
            rgb = hex_to_rgb(c.hex)
            nearest = min(keep, key=lambda k: _distance_sq(rgb, keep_rgb[k.id]))
            remap[c.id] = nearest.id
    new_pixels = [
        [transparent if v == transparent else remap.get(v, transparent) for v in row]
        for row in pixels
    ]
    return new_pixels, keep


def _copy_grid_with_pixels(
    original: PixelGrid,
    pixels: list[list[int]],
    *,
    metadata: dict | None = None,
) -> PixelGrid:
    return PixelGrid(
        version=original.version,
        canvas=PixelGridCanvas(
            width=original.canvas.width,
            height=original.canvas.height,
            transparent_index=original.canvas.transparent_index,
        ),
        axes=PixelGridAxes(x=list(original.axes.x), y=list(original.axes.y)),
        palette=[c.model_copy(deep=True) for c in original.palette],
        pixels=[list(row) for row in pixels],
        metadata=dict(original.metadata if metadata is None else metadata),
    )


def _normalize_fit_canvas_mode(mode: str) -> FitCanvasMode:
    value = str(mode).strip().lower()
    if value not in {"smart", "contain", "stretch"}:
        raise ValueError(f"fit canvas mode must be smart|contain|stretch, got {mode!r}")
    return value  # type: ignore[return-value]


def _pixel_bbox(
    pixels: list[list[int]],
    transparent: int,
) -> tuple[int, int, int, int] | None:
    left: int | None = None
    top: int | None = None
    right = 0
    bottom = 0
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value == transparent:
                continue
            left = x if left is None else min(left, x)
            top = y if top is None else min(top, y)
            right = max(right, x + 1)
            bottom = max(bottom, y + 1)
    if left is None or top is None:
        return None
    return left, top, right, bottom


def _fit_canvas_dimensions(
    src_w: int,
    src_h: int,
    *,
    canvas_size: tuple[int, int],
    available_size: tuple[int, int],
    mode: FitCanvasMode,
    min_axis_coverage: float,
) -> tuple[int, int]:
    canvas_w, canvas_h = canvas_size
    available_w, available_h = available_size
    src_w = max(1, int(src_w))
    src_h = max(1, int(src_h))
    available_w = max(1, int(available_w))
    available_h = max(1, int(available_h))

    if mode == "stretch":
        return available_w, available_h
    if mode == "contain":
        return _contain_dimensions(src_w, src_h, available_w, available_h)

    threshold = min(1.0, max(0.0, float(min_axis_coverage)))
    width_coverage = src_w / max(1, canvas_w)
    height_coverage = src_h / max(1, canvas_h)
    under_w = width_coverage < threshold
    under_h = height_coverage < threshold
    if under_w and under_h:
        return _contain_dimensions(src_w, src_h, available_w, available_h)
    if under_w or under_h:
        return (
            available_w if under_w else min(src_w, available_w),
            available_h if under_h else min(src_h, available_h),
        )
    return min(src_w, available_w), min(src_h, available_h)


def _contain_dimensions(src_w: int, src_h: int, available_w: int, available_h: int) -> tuple[int, int]:
    scale = min(available_w / max(1, src_w), available_h / max(1, src_h))
    dst_w = max(1, min(available_w, int(round(src_w * scale))))
    dst_h = max(1, min(available_h, int(round(src_h * scale))))
    return dst_w, dst_h


def _resize_pixels_nearest(
    pixels: list[list[int]],
    dst_w: int,
    dst_h: int,
) -> list[list[int]]:
    src_h = len(pixels)
    src_w = len(pixels[0]) if src_h else 0
    if src_w <= 0 or src_h <= 0:
        return []
    dst_w = max(1, int(dst_w))
    dst_h = max(1, int(dst_h))
    out: list[list[int]] = []
    for y in range(dst_h):
        src_y = min(src_h - 1, int(y * src_h / dst_h))
        row: list[int] = []
        for x in range(dst_w):
            src_x = min(src_w - 1, int(x * src_w / dst_w))
            row.append(pixels[src_y][src_x])
        out.append(row)
    return out


def _safe_get(pixels: list[list[int]], x: int, y: int, default: int) -> int:
    if y < 0 or y >= len(pixels):
        return default
    if x < 0 or x >= len(pixels[y]):
        return default
    return pixels[y][x]


def _neighbors4(x: int, y: int):
    yield x - 1, y
    yield x + 1, y
    yield x, y - 1
    yield x, y + 1


def _neighbors8(x: int, y: int):
    for ny in (y - 1, y, y + 1):
        for nx in (x - 1, x, x + 1):
            if nx == x and ny == y:
                continue
            yield nx, ny


def _luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _distance_sq(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True))
