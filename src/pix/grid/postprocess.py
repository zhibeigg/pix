"""Pixel Grid 后处理：清噪、统一轮廓、调色板整理。"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from pix.grid.schema import PixelGrid, PixelGridAxes, PixelGridCanvas, PixelGridColor
from pix.pixelize.palette import hex_to_rgb, rgb_to_hex


@dataclass(frozen=True)
class GridPostprocessParams:
    cleanup: bool = True
    outline: bool = True
    outline_strength: int = 1
    min_neighbors: int = 1
    max_colors: int = 12


def polish_pixel_grid(
    grid: PixelGrid,
    *,
    cleanup: bool = True,
    outline: bool = True,
    outline_strength: int = 1,
    min_neighbors: int = 1,
    max_colors: int | None = None,
) -> PixelGrid:
    """对 PixelGrid 做确定性后处理，返回新的 Grid。"""
    params = GridPostprocessParams(
        cleanup=cleanup,
        outline=outline,
        outline_strength=max(0, int(outline_strength)),
        min_neighbors=max(0, int(min_neighbors)),
        max_colors=max(2, int(max_colors or len(grid.palette) or 2)),
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
        outline_id, palette = _ensure_outline_color(palette, pixels, grid.canvas.transparent_index)
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
        "min_neighbors": params.min_neighbors,
        "max_colors": params.max_colors,
    }
    return polished


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
) -> tuple[int, list[PixelGridColor]]:
    used = {v for row in pixels for v in row if v != transparent}
    used_palette = [c for c in palette if c.id in used]
    if not used_palette:
        return 0, [PixelGridColor(id=0, hex="#101010", role="outline")]
    outline_candidates = [c for c in palette if c.role == "outline"]
    if outline_candidates:
        return min(outline_candidates, key=lambda c: _luma(hex_to_rgb(c.hex))).id, palette
    darkest = min(used_palette, key=lambda c: _luma(hex_to_rgb(c.hex)))
    # 若最暗色已经够暗，直接作为 outline；避免增加颜色数。
    if _luma(hex_to_rgb(darkest.hex)) < 90:
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
    return sum((x - y) ** 2 for x, y in zip(a, b))
