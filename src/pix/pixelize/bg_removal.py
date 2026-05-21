"""背景去除：flood-fill 从四个角向内抠连通背景色。

设计原则：
- 不依赖 rembg 这种重模型；对"单主体 + 纯色底"的图片效果最好
- 对已经像素化的图操作最稳，因为边缘清晰、色块整齐
- 提供 tolerance（颜色容差）与 feather（透明边缘羽化）参数
"""

from __future__ import annotations

from collections import deque
from typing import Iterable, Literal

import numpy as np
from PIL import Image


def key_color_mask(
    rgba: np.ndarray,
    key_rgb: tuple[int, int, int],
    *,
    tolerance: int = 48,
    visible_only: bool = True,
) -> np.ndarray:
    """识别接近指定 key color 的像素，支持封闭孔洞背景。

    与 flood-fill 不同，这里不要求背景连通到四角，因此能清理手链、光环、镂空框
    内部残留的纯色背景。调用方应使用与 prompt 匹配的动态 key color，避免误伤素材
    自身颜色。
    """
    if rgba.ndim != 3 or rgba.shape[-1] < 4:
        raise ValueError("key_color_mask 需要 RGBA 数组")
    rgb = rgba[..., :3].astype(np.int32)
    ref = np.asarray(key_rgb, dtype=np.int32)
    dist_sq = ((rgb - ref) ** 2).sum(axis=2)
    mask = dist_sq <= max(0, int(tolerance)) ** 2 * 3
    if visible_only:
        mask &= rgba[..., 3] > 0
    return mask


def remove_key_color(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int],
    tolerance: int = 48,
    spill_tolerance: int | None = None,
    edge_speckle: bool = False,
    edge_speckle_max_area: int = 18,
    edge_speckle_max_thickness: int = 3,
    edge_speckle_radius: int = 2,
    edge_speckle_passes: int = 2,
    edge_spill: bool = False,
    edge_spill_radius: int = 3,
    edge_spill_passes: int = 3,
    edge_spill_outline: bool = False,
) -> Image.Image:
    """全局移除指定纯色背景，并可清理边缘 key-color 碎点与量化溢色。"""
    rgba = np.asarray(image.convert("RGBA")).copy()
    mask = key_color_mask(rgba, key_rgb, tolerance=tolerance, visible_only=True)
    outline_mask = np.zeros(rgba.shape[:2], dtype=bool)
    if spill_tolerance is not None and int(spill_tolerance) > int(tolerance):
        spill = key_color_mask(rgba, key_rgb, tolerance=int(spill_tolerance), visible_only=True)
        # 只清理已经靠近透明背景或本轮 key-color 背景的溢色边，避免误伤远离背景的正常同色装饰。
        near_transparent = _dilate_mask_8((rgba[..., 3] == 0) | mask)
        mask |= spill & near_transparent
    if edge_speckle:
        for _ in range(max(1, int(edge_speckle_passes))):
            probe = rgba.copy()
            if mask.any():
                probe[mask, :3] = 0
                probe[mask, 3] = 0
            speckle = key_color_edge_speckle_mask(
                probe,
                key_rgb,
                base_mask=None,
                max_area=edge_speckle_max_area,
                max_thickness=edge_speckle_max_thickness,
                radius=edge_speckle_radius,
            )
            speckle &= ~mask
            if not speckle.any():
                break
            mask |= speckle
    if edge_spill:
        # 量化/缩放可能把 #FF00FF 压成 #C400C4、#420347 这类同色相暗紫边。
        # 这类残留不一定与原 key color 距离足够近，因此用色相相似度 + 透明边界邻近度保守剥离。
        for _ in range(max(1, int(edge_spill_passes))):
            probe = rgba.copy()
            if mask.any():
                probe[mask, :3] = 0
                probe[mask, 3] = 0
            spill = key_color_edge_spill_mask(
                probe,
                key_rgb,
                base_mask=mask,
                radius=edge_spill_radius,
            )
            spill &= ~mask
            if not spill.any():
                break
            if edge_spill_outline:
                outline_mask |= _key_color_spill_outline_mask(probe, spill)
            mask |= spill
    if mask.any():
        rgba[mask, :3] = 0
        rgba[mask, 3] = 0
    if edge_spill_outline and outline_mask.any():
        foreground = (rgba[..., 3] > 0) & ~outline_mask
        outline_rgb = _infer_outline_rgb(rgba, foreground)
        rgba[outline_mask, :3] = outline_rgb
        rgba[outline_mask, 3] = 255
    # 透明像素的 RGB 也清零，避免某些预览器/工具忽略 alpha 时显示 key color 底色。
    transparent = rgba[..., 3] == 0
    if transparent.any():
        rgba[transparent, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def key_color_edge_speckle_mask(
    rgba: np.ndarray,
    key_rgb: tuple[int, int, int],
    *,
    base_mask: np.ndarray | None = None,
    max_area: int = 18,
    max_thickness: int = 3,
    radius: int = 2,
) -> np.ndarray:
    """只标记透明边界附近、小面积或很薄的 key-color 残留。

    这用于处理像素化/量化把 #FF00FF 之类 key color 压成暗紫小点或细条的情况。
    它不会处理厚块区域，也不会进入主体内部，避免把真实内容扣掉。
    """
    if rgba.ndim != 3 or rgba.shape[-1] < 4:
        raise ValueError("key_color_edge_speckle_mask 需要 RGBA 数组")
    alpha = rgba[..., 3]
    transparent = alpha == 0
    near = transparent.copy()
    seed = transparent | (base_mask if base_mask is not None else False)
    near = seed.copy()
    for _ in range(max(1, int(radius))):
        near = _dilate_mask_8(near)

    rgb = rgba[..., :3].astype(np.float32)
    key = np.asarray(key_rgb, dtype=np.float32)
    key_norm = float(np.linalg.norm(key)) or 1.0
    rgb_norm = np.linalg.norm(rgb, axis=2)
    dot = (rgb * key).sum(axis=2)
    cosine = np.zeros(alpha.shape, dtype=np.float32)
    valid_norm = rgb_norm > 1e-6
    cosine[valid_norm] = dot[valid_norm] / (rgb_norm[valid_norm] * key_norm)
    channel_max = rgb.max(axis=2)
    channel_min = rgb.min(axis=2)
    chroma = channel_max - channel_min
    candidates = (alpha > 0) & near & (cosine >= 0.94) & (channel_max >= 40) & (chroma >= 24)
    if base_mask is not None:
        candidates &= ~base_mask
    return _edge_residue_component_mask(
        candidates,
        max_area=max(1, int(max_area)),
        max_thickness=max(1, int(max_thickness)),
    )


def key_color_edge_spill_mask(
    rgba: np.ndarray,
    key_rgb: tuple[int, int, int],
    *,
    base_mask: np.ndarray | None = None,
    radius: int = 3,
    cosine_min: float = 0.86,
    min_channel: int = 32,
    min_chroma: int = 24,
) -> np.ndarray:
    """标记透明边界附近的 key-color 同色相量化溢色。

    生图背景虽然要求纯 key color，但缩放/量化后常会在主体黑边外形成
    #C400C4、#420347 之类与 key color 同色相的暗紫边。这些颜色与原 key
    的欧氏距离很远，普通 tolerance 抠不到；但它们只应贴着透明背景出现。
    """
    if rgba.ndim != 3 or rgba.shape[-1] < 4:
        raise ValueError("key_color_edge_spill_mask 需要 RGBA 数组")
    alpha = rgba[..., 3]
    seed = alpha == 0
    if base_mask is not None:
        seed |= base_mask
    near = seed.copy()
    for _ in range(max(1, int(radius))):
        near = _dilate_mask_8(near)

    rgb = rgba[..., :3].astype(np.float32)
    key = np.asarray(key_rgb, dtype=np.float32)
    key_norm = float(np.linalg.norm(key)) or 1.0
    rgb_norm = np.linalg.norm(rgb, axis=2)
    dot = (rgb * key).sum(axis=2)
    cosine = np.zeros(alpha.shape, dtype=np.float32)
    valid_norm = rgb_norm > 1e-6
    cosine[valid_norm] = dot[valid_norm] / (rgb_norm[valid_norm] * key_norm)
    channel_max = rgb.max(axis=2)
    channel_min = rgb.min(axis=2)
    chroma = channel_max - channel_min
    candidates = (
        (alpha > 0)
        & near
        & (cosine >= float(cosine_min))
        & (channel_max >= max(0, int(min_channel)))
        & (chroma >= max(0, int(min_chroma)))
    )
    if base_mask is not None:
        candidates &= ~base_mask
    return candidates


def remove_translucent_edge_halo(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int] | None = None,
    alpha_cutoff: int = 128,
    key_alpha_cutoff: int = 224,
    radius: int = 2,
    passes: int = 2,
) -> Image.Image:
    """清理透明主体外缘的半透明背景色残留。

    精灵帧从 key-color 背景抠图后，缩放/量化前常会留下低 alpha 的
    紫/绿/红色边缘。这些像素在透明棋盘或深色背景上会显得像一圈脏边。
    该函数只处理透明边界附近像素：
    - alpha 很低的边缘像素直接抠透明；
    - 若提供 key_rgb，则额外清理 alpha 较高但色相仍接近 key color 的边缘像素。
    """
    rgba = np.asarray(image.convert("RGBA")).copy()
    safe_alpha = max(0, min(255, int(alpha_cutoff)))
    safe_key_alpha = max(safe_alpha, min(255, int(key_alpha_cutoff)))
    safe_radius = max(1, int(radius))
    for _ in range(max(1, int(passes))):
        alpha = rgba[..., 3]
        visible = alpha > 0
        if not visible.any():
            break
        near = alpha == 0
        for _distance in range(safe_radius):
            near = _dilate_mask_8(near)
        remove = visible & near & (alpha <= safe_alpha)
        if key_rgb is not None:
            rgb = rgba[..., :3].astype(np.float32)
            key = np.asarray(key_rgb, dtype=np.float32)
            key_norm = float(np.linalg.norm(key)) or 1.0
            rgb_norm = np.linalg.norm(rgb, axis=2)
            dot = (rgb * key).sum(axis=2)
            cosine = np.zeros(alpha.shape, dtype=np.float32)
            valid_norm = rgb_norm > 1e-6
            cosine[valid_norm] = dot[valid_norm] / (rgb_norm[valid_norm] * key_norm)
            channel_max = rgb.max(axis=2)
            channel_min = rgb.min(axis=2)
            chroma = channel_max - channel_min
            key_spill = (
                visible
                & near
                & (alpha <= safe_key_alpha)
                & (cosine >= 0.88)
                & (channel_max >= 36)
                & (chroma >= 24)
            )
            remove |= key_spill
        if not remove.any():
            break
        rgba[remove, :3] = 0
        rgba[remove, 3] = 0
    transparent = rgba[..., 3] == 0
    if transparent.any():
        rgba[transparent, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def remove_detached_dark_edges(
    image: Image.Image,
    *,
    max_distance: int = 4,
    luma_threshold: int = 62,
    max_channel: int = 96,
    chroma_threshold: int = 58,
    max_area: int = 160,
    max_thickness: int = 4,
    max_density: float = 0.16,
    neutral_chroma_threshold: int = 42,
    neutral_max_luma: int = 128,
    neutral_light_max_channel: int = 245,
    passes: int = 5,
) -> Image.Image:
    """移除贴近主体但没有接触主体的漂浮低饱和细线/碎点。"""
    rgba = np.asarray(image.convert("RGBA")).copy()
    for _ in range(max(1, int(passes))):
        alpha = rgba[..., 3]
        visible = alpha > 0
        if not visible.any():
            break

        rgb = rgba[..., :3].astype(np.int16)
        channel_max = rgb.max(axis=2)
        channel_min = rgb.min(axis=2)
        luma = _rgb_luma(rgba[..., :3])
        chroma = channel_max - channel_min
        dark_edge = (
            visible
            & (luma <= max(0, int(luma_threshold)))
            & (channel_max <= max(0, int(max_channel)))
            & (chroma <= max(0, int(chroma_threshold)))
        )
        neutral_edge = (
            visible
            & (chroma <= max(0, int(neutral_chroma_threshold)))
            & (luma <= max(0, int(neutral_max_luma)))
            & (channel_max <= max(0, int(neutral_light_max_channel)))
        )
        edge_fragment = dark_edge | neutral_edge
        foreground = visible & ~edge_fragment
        if not edge_fragment.any() or not foreground.any():
            break

        adjacent_foreground = _dilate_mask_8(foreground)
        # 只处理背景边界附近且没有贴住主体色的低饱和细线，避免误删主体内部的黑色五官/阴影。
        near_transparent = _dilate_mask_8(alpha == 0)
        detached_candidates = edge_fragment & ~adjacent_foreground & near_transparent
        detached = _edge_residue_component_mask(
            detached_candidates,
            max_area=max(1, int(max_area)),
            max_thickness=max(1, int(max_thickness)),
            max_density=float(max_density),
        )
        if not detached.any():
            break
        rgba[detached, :3] = 0
        rgba[detached, 3] = 0

    transparent = rgba[..., 3] == 0
    if transparent.any():
        rgba[transparent, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def remove_tiny_alpha_islands(
    image: Image.Image,
    *,
    max_area: int = 32,
    max_axis: int = 12,
) -> Image.Image:
    """移除很小的独立可见碎片，作为最终透明素材清理。"""
    rgba = np.asarray(image.convert("RGBA")).copy()
    visible = rgba[..., 3] > 0
    h, w = visible.shape
    visited = np.zeros(visible.shape, dtype=bool)
    remove = np.zeros(visible.shape, dtype=bool)
    for y in range(h):
        for x in range(w):
            if not visible[y, x] or visited[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
            visited[y, x] = True
            pixels: list[tuple[int, int]] = []
            while q:
                cy, cx = q.popleft()
                pixels.append((cy, cx))
                for ny in range(max(0, cy - 1), min(h, cy + 2)):
                    for nx in range(max(0, cx - 1), min(w, cx + 2)):
                        if ny == cy and nx == cx:
                            continue
                        if visible[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            q.append((ny, nx))
            ys = [py for py, _px in pixels]
            xs = [px for _py, px in pixels]
            width = max(xs) - min(xs) + 1
            height = max(ys) - min(ys) + 1
            if len(pixels) <= max(1, int(max_area)) and max(width, height) <= max(1, int(max_axis)):
                for py, px in pixels:
                    remove[py, px] = True
    if remove.any():
        rgba[remove, :3] = 0
        rgba[remove, 3] = 0
    transparent = rgba[..., 3] == 0
    if transparent.any():
        rgba[transparent, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _key_color_spill_outline_mask(rgba: np.ndarray, spill: np.ndarray) -> np.ndarray:
    """把贴着主体的 key-color 溢色改成描边，而不是抠成透明缝。"""
    if not spill.any():
        return np.zeros(spill.shape, dtype=bool)
    alpha = rgba[..., 3]
    foreground = (alpha > 0) & ~spill
    if not foreground.any():
        return np.zeros(spill.shape, dtype=bool)
    # 只补回紧贴主体的一圈溢色；更外层仍抠透明，避免凭空加粗轮廓。
    return spill & _dilate_mask_8(foreground)


def _edge_residue_component_mask(
    mask: np.ndarray,
    *,
    max_area: int,
    max_thickness: int,
    max_density: float | None = None,
) -> np.ndarray:
    """返回小面积、薄条形或低密度稀疏的 8 连通分量。"""
    h, w = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    result = np.zeros(mask.shape, dtype=bool)
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or visited[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
            visited[y, x] = True
            pixels: list[tuple[int, int]] = []
            while q:
                cy, cx = q.popleft()
                pixels.append((cy, cx))
                for ny in range(max(0, cy - 1), min(h, cy + 2)):
                    for nx in range(max(0, cx - 1), min(w, cx + 2)):
                        if ny == cy and nx == cx:
                            continue
                        if mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            q.append((ny, nx))
            ys = [py for py, _px in pixels]
            xs = [px for _py, px in pixels]
            width = max(xs) - min(xs) + 1
            height = max(ys) - min(ys) + 1
            density = len(pixels) / max(1, width * height)
            sparse = max_density is not None and density <= float(max_density)
            if len(pixels) <= max_area or min(width, height) <= max_thickness or sparse:
                for py, px in pixels:
                    result[py, px] = True
    return result


def _sample_corner_colors(
    arr: np.ndarray, sample: int = 3
) -> list[tuple[int, int, int]]:
    """从四个角取一小块，取众数作为候选背景色（抗一两个噪点）。"""
    h, w, _ = arr.shape
    s = max(1, min(sample, min(h, w) // 2))
    corners = [
        arr[:s, :s],           # 左上
        arr[:s, w - s:],       # 右上
        arr[h - s:, :s],       # 左下
        arr[h - s:, w - s:],   # 右下
    ]
    seeds: list[tuple[int, int, int]] = []
    for block in corners:
        flat = block.reshape(-1, 3)
        uniq, counts = np.unique(flat, axis=0, return_counts=True)
        dominant = uniq[int(counts.argmax())]
        seeds.append((int(dominant[0]), int(dominant[1]), int(dominant[2])))
    return seeds


def _sample_edge_colors(
    arr: np.ndarray,
    *,
    max_colors: int = 4,
    bin_size: int = 8,
) -> list[tuple[int, int, int]]:
    """从整圈边缘抽取主要背景色，兼容白灰棋盘格假透明背景。"""
    h, w, _ = arr.shape
    bw = max(1, min(8, min(h, w) // 16 or 1))
    border = np.concatenate(
        [
            arr[:bw, :, :].reshape(-1, 3),
            arr[h - bw :, :, :].reshape(-1, 3),
            arr[:, :bw, :].reshape(-1, 3),
            arr[:, w - bw :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    if border.size == 0:
        return []
    # 轻微分箱后统计，避免抗锯齿/压缩导致同一背景色裂成大量近似色。
    q = (border.astype(np.uint16) // max(1, bin_size)) * max(1, bin_size)
    uniq, counts = np.unique(q.astype(np.uint8), axis=0, return_counts=True)
    order = np.argsort(counts)[::-1]
    refs: list[tuple[int, int, int]] = []
    for idx in order:
        key = uniq[int(idx)]
        mask = np.all(q == key, axis=1)
        if not mask.any():
            continue
        mean = border[mask].mean(axis=0)
        rgb = tuple(int(round(v)) for v in mean[:3])
        if all(sum((rgb[i] - old[i]) ** 2 for i in range(3)) > (bin_size * 2) ** 2 for old in refs):
            refs.append(rgb)
        if len(refs) >= max_colors:
            break
    return refs


def _flood_fill_mask(
    arr: np.ndarray,
    seeds: Iterable[tuple[int, int]],
    ref_colors: list[tuple[int, int, int]],
    tolerance: int,
) -> np.ndarray:
    """从若干 (y, x) seed 开始做 BFS flood fill，返回 bool 掩码（True = 背景）。"""
    h, w, _ = arr.shape
    visited = np.zeros((h, w), dtype=bool)
    # 注意：int16 不够——单通道最大差 255, 差平方 65025 会溢出；用 int32
    ref = np.array(ref_colors, dtype=np.int32)   # [K, 3]
    tol_sq = tolerance * tolerance * 3           # 用欧氏距离平方阈值

    q: deque[tuple[int, int]] = deque()
    for sy, sx in seeds:
        if 0 <= sy < h and 0 <= sx < w and not visited[sy, sx]:
            visited[sy, sx] = True
            q.append((sy, sx))

    while q:
        y, x = q.popleft()
        pixel = arr[y, x].astype(np.int32)
        diff = ref - pixel
        # 与最接近的 seed 色距离
        dist = (diff * diff).sum(axis=1).min()
        if dist > tol_sq:
            visited[y, x] = False
            continue
        # 4 邻域入队
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    return visited


def remove_background(
    image: Image.Image,
    *,
    tolerance: int = 12,
    feather: int = 0,
    edge_style: Literal["hard", "feather", "outline"] = "hard",
    keep_border_bleed: bool = True,
) -> Image.Image:
    """把图片四角连通的背景色抠成透明。

    Args:
        image: 原图（RGB 或 RGBA）
        tolerance: 每个通道的颜色容差（0 = 只抠完全相同色；12 是默认）
        feather: 边缘强度。edge_style=feather 时表示 alpha 羽化半径；
            edge_style=outline 时表示描边宽度；hard 时不生效。
        edge_style: hard=硬边透明；feather=主体边缘 alpha 羽化；outline=主体外侧补深色描边。
        keep_border_bleed: True 时如果主体压到边缘（四角色与主体色相近），不硬抠
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    arr = np.asarray(image.convert("RGB"))
    corner_seeds = _sample_corner_colors(arr)
    edge_refs = _sample_edge_colors(arr)
    seeds = list(dict.fromkeys(corner_seeds + edge_refs))

    if keep_border_bleed:
        unique_corners = {tuple(int(c) for c in s) for s in corner_seeds}
        if len(unique_corners) > 2:
            # 四角色差异大，说明主体可能压到边，贸然抠会毁图
            return image

    h, w, _ = arr.shape
    # 从四角各放若干 seed 点，不只角点一个
    seed_points = [
        (0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1),
        (0, w // 2), (h - 1, w // 2),
        (h // 2, 0), (h // 2, w - 1),
    ]
    mask_bg = _flood_fill_mask(arr, seed_points, seeds, tolerance)

    rgba = np.asarray(image).copy()
    style = edge_style if edge_style in ("hard", "feather", "outline") else "hard"
    strength = max(0, int(feather))
    if style == "outline" and strength > 0:
        _apply_outline_edge(rgba, mask_bg, strength)
    else:
        _apply_alpha_feather(rgba, mask_bg, strength if style == "feather" else 0)
    transparent = rgba[..., 3] == 0
    if transparent.any():
        rgba[transparent, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _apply_alpha_feather(rgba: np.ndarray, mask_bg: np.ndarray, radius: int) -> None:
    """把背景设为透明，并对主体边缘做 8 邻域 alpha 羽化。"""
    original_alpha = rgba[..., 3].copy()
    rgba[mask_bg, 3] = 0
    if radius <= 0:
        return

    foreground = (~mask_bg) & (original_alpha > 0)
    reached = mask_bg.copy()
    assigned = np.zeros(mask_bg.shape, dtype=bool)
    for distance in range(1, radius + 1):
        reached = _dilate_mask_8(reached)
        layer = foreground & reached & ~assigned
        if not layer.any():
            continue
        alpha = int(round(255 * distance / (radius + 1)))
        alpha = max(1, min(254, alpha))
        rgba[layer, 3] = np.minimum(rgba[layer, 3], alpha)
        assigned |= layer


def _apply_outline_edge(rgba: np.ndarray, mask_bg: np.ndarray, strength: int) -> None:
    """背景透明，同时在主体外侧补不透明深色描边。"""
    foreground = (~mask_bg) & (rgba[..., 3] > 0)
    outline_rgb = _infer_outline_rgb(rgba, foreground)
    # 很多生图本身已经带黑色像素轮廓。旧实现会从这些黑边继续向外膨胀，
    # 在斜边和凹角处形成 2~3 像素厚的黑块。这里把已存在的暗色边界当作
    # 屏障，只从非轮廓主体色向透明背景补缺口。
    existing_outline = _existing_outline_boundary(rgba, foreground, mask_bg, outline_rgb)
    source = foreground & ~existing_outline
    if not source.any():
        source = foreground

    outline_mask = np.zeros(mask_bg.shape, dtype=bool)
    current = source.copy()
    for _ in range(max(1, strength)):
        expanded = _dilate_mask_4(current)
        layer = expanded & mask_bg & ~outline_mask
        # 避免直接在画布最外圈生成贴边框。
        if layer.shape[0] > 2 and layer.shape[1] > 2:
            layer[0, :] = False
            layer[-1, :] = False
            layer[:, 0] = False
            layer[:, -1] = False
        outline_mask |= layer
        # 可以穿过本轮新增的外描边继续加宽，但不能穿过输入里已有的黑边，
        # 否则会把已有轮廓再次加粗。
        current = (current | layer | (expanded & foreground & ~existing_outline))
    rgba[mask_bg, 3] = 0
    rgba[outline_mask, :3] = outline_rgb
    rgba[outline_mask, 3] = 255


def _infer_outline_rgb(rgba: np.ndarray, foreground: np.ndarray) -> tuple[int, int, int]:
    pixels = rgba[foreground, :3]
    if pixels.size == 0:
        return (16, 16, 16)
    luma = _rgb_luma(pixels)
    darkest = pixels[int(np.argmin(luma))]
    if float(luma.min()) < 70:
        return tuple(int(v) for v in darkest)
    return tuple(max(0, int(v * 0.36)) for v in darkest)


def _existing_outline_boundary(
    rgba: np.ndarray,
    foreground: np.ndarray,
    mask_bg: np.ndarray,
    outline_rgb: tuple[int, int, int],
) -> np.ndarray:
    """找出输入图里已经存在的深色边界，避免对它二次外扩。"""
    if not foreground.any():
        return np.zeros(mask_bg.shape, dtype=bool)
    luma = _rgb_luma(rgba[..., :3])
    outline_luma = _rgb_luma(np.asarray([outline_rgb], dtype=np.uint8))[0]
    dark_boundary = foreground & _dilate_mask_8(mask_bg) & (luma <= max(72.0, float(outline_luma) + 28.0))
    if not dark_boundary.any():
        return dark_boundary
    brighter_neighbor = np.zeros(mask_bg.shape, dtype=bool)
    h, w = mask_bg.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            src_y0 = max(0, -dy)
            src_y1 = min(h, h - dy)
            src_x0 = max(0, -dx)
            src_x1 = min(w, w - dx)
            dst_y0 = max(0, dy)
            dst_y1 = min(h, h + dy)
            dst_x0 = max(0, dx)
            dst_x1 = min(w, w + dx)
            neighbor_fg = foreground[src_y0:src_y1, src_x0:src_x1]
            neighbor_luma = luma[src_y0:src_y1, src_x0:src_x1]
            own_luma = luma[dst_y0:dst_y1, dst_x0:dst_x1]
            brighter_neighbor[dst_y0:dst_y1, dst_x0:dst_x1] |= neighbor_fg & (neighbor_luma >= own_luma + 30.0)
    return dark_boundary & brighter_neighbor


def _rgb_luma(rgb: np.ndarray) -> np.ndarray:
    arr = rgb.astype(np.float32)
    return arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722


def _dilate_mask_4(mask: np.ndarray) -> np.ndarray:
    """4 邻域膨胀；用于外描边，避免斜角处额外变厚。"""
    return _dilate_mask(mask, offsets=((-1, 0), (1, 0), (0, -1), (0, 1)))


def _dilate_mask_8(mask: np.ndarray) -> np.ndarray:
    """8 邻域膨胀；图像外侧不参与膨胀，避免引入画布外假背景。"""
    return _dilate_mask(
        mask,
        offsets=(
            (-1, -1), (0, -1), (1, -1),
            (-1, 0), (1, 0),
            (-1, 1), (0, 1), (1, 1),
        ),
    )


def _dilate_mask(mask: np.ndarray, *, offsets: tuple[tuple[int, int], ...]) -> np.ndarray:
    result = mask.copy()
    h, w = mask.shape
    for dx, dy in offsets:
        shifted = np.zeros_like(mask, dtype=bool)
        src_y0 = max(0, -dy)
        src_y1 = min(h, h - dy)
        src_x0 = max(0, -dx)
        src_x1 = min(w, w - dx)
        dst_y0 = max(0, dy)
        dst_y1 = min(h, h + dy)
        dst_x0 = max(0, dx)
        dst_x1 = min(w, w + dx)
        shifted[dst_y0:dst_y1, dst_x0:dst_x1] = mask[src_y0:src_y1, src_x0:src_x1]
        result |= shifted
    return result
