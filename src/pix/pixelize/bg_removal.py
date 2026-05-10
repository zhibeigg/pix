"""背景去除：flood-fill 从四个角向内抠连通背景色。

设计原则：
- 不依赖 rembg 这种重模型；对"单主体 + 纯色底"的图片效果最好
- 对已经像素化的图操作最稳，因为边缘清晰、色块整齐
- 提供 tolerance（颜色容差）与 feather（透明边缘羽化）参数
"""

from __future__ import annotations

from collections import deque
from typing import Iterable

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
    keep_border_bleed: bool = True,
) -> Image.Image:
    """把图片四角连通的背景色抠成透明。

    Args:
        image: 原图（RGB 或 RGBA）
        tolerance: 每个通道的颜色容差（0 = 只抠完全相同色；12 是默认）
        feather: 若 > 0，对掩码做腐蚀，让主体边缘保留一圈"不抠"的像素
            —— 对像素画有奇效：避免抗锯齿被误伤
        keep_border_bleed: True 时如果主体压到边缘（四角色与主体色相近），不硬抠
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    arr = np.asarray(image.convert("RGB"))
    seeds = _sample_corner_colors(arr)

    if keep_border_bleed:
        unique_colors = {tuple(int(c) for c in s) for s in seeds}
        if len(unique_colors) > 2:
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

    if feather > 0:
        mask_bg = _erode_mask(mask_bg, feather)

    # 应用透明：背景位置的 alpha 设为 0
    rgba = np.asarray(image).copy()
    rgba[mask_bg, 3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _erode_mask(mask: np.ndarray, iterations: int) -> np.ndarray:
    """对背景掩码做 N 次 1 像素腐蚀，让抠除区域向内收缩。"""
    result = mask.copy()
    for _ in range(iterations):
        # 邻域 4 方向都为 True 时才保留
        up = np.roll(result, 1, axis=0)
        down = np.roll(result, -1, axis=0)
        left = np.roll(result, 1, axis=1)
        right = np.roll(result, -1, axis=1)
        up[0, :] = False
        down[-1, :] = False
        left[:, 0] = False
        right[:, -1] = False
        result = result & up & down & left & right
    return result
