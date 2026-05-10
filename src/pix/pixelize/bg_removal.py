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
    outline_mask = np.zeros(mask_bg.shape, dtype=bool)
    current = foreground.copy()
    for _ in range(max(1, strength)):
        expanded = _dilate_mask_8(current)
        layer = expanded & mask_bg & ~outline_mask
        # 避免直接在画布最外圈生成贴边框。
        if layer.shape[0] > 2 and layer.shape[1] > 2:
            layer[0, :] = False
            layer[-1, :] = False
            layer[:, 0] = False
            layer[:, -1] = False
        outline_mask |= layer
        current = expanded
    rgba[mask_bg, 3] = 0
    rgba[outline_mask, :3] = outline_rgb
    rgba[outline_mask, 3] = 255


def _infer_outline_rgb(rgba: np.ndarray, foreground: np.ndarray) -> tuple[int, int, int]:
    pixels = rgba[foreground, :3]
    if pixels.size == 0:
        return (16, 16, 16)
    luma = pixels[:, 0].astype(np.float32) * 0.2126 + pixels[:, 1].astype(np.float32) * 0.7152 + pixels[:, 2].astype(np.float32) * 0.0722
    darkest = pixels[int(np.argmin(luma))]
    if float(luma.min()) < 70:
        return tuple(int(v) for v in darkest)
    return tuple(max(0, int(v * 0.36)) for v in darkest)


def _dilate_mask_8(mask: np.ndarray) -> np.ndarray:
    """8 邻域膨胀；图像外侧不参与膨胀，避免引入画布外假背景。"""
    result = mask.copy()
    h, w = mask.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
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
