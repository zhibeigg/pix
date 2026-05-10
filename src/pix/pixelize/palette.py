"""调色板构建与量化。"""

from __future__ import annotations

from typing import Iterable

import numpy as np
from PIL import Image

from pix.analysis.schema import ColorSwatch


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def swatches_to_rgb_list(swatches: Iterable[ColorSwatch]) -> list[tuple[int, int, int]]:
    ranked = sorted(swatches, key=lambda s: s.weight, reverse=True)
    return [hex_to_rgb(s.hex) for s in ranked]


def kmeans_palette(image: Image.Image, k: int, sample: int = 16384) -> list[tuple[int, int, int]]:
    """用 k-means 从图片提取 k 个主要颜色。"""
    if k <= 0:
        return []
    k = max(1, k)
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[..., 3]
    rgb = rgba[..., :3]
    if (alpha < 255).any():
        visible = rgb[alpha > 8]
        if visible.size > 0:
            arr = visible.astype(np.float32).reshape(-1, 3)
        else:
            arr = rgb.reshape(-1, 3).astype(np.float32)
    else:
        arr = rgb.reshape(-1, 3).astype(np.float32)
    if arr.shape[0] > sample:
        idx = np.random.default_rng(42).choice(arr.shape[0], size=sample, replace=False)
        arr = arr[idx]

    try:
        from sklearn.cluster import KMeans

        km = KMeans(n_clusters=k, n_init=4, random_state=42)
        km.fit(arr)
        centers = km.cluster_centers_
    except Exception:  # pragma: no cover - fallback 到 Pillow quantize
        tmp = image.convert("RGB").quantize(colors=k, method=Image.Quantize.FASTOCTREE)
        pal = tmp.getpalette() or []
        return [(pal[i], pal[i + 1], pal[i + 2]) for i in range(0, k * 3, 3)]

    centers = np.clip(centers, 0, 255).astype(np.int32)
    return [tuple(int(x) for x in c) for c in centers]


def merge_palette(
    locked: list[tuple[int, int, int]],
    extra: list[tuple[int, int, int]],
    target_k: int,
) -> list[tuple[int, int, int]]:
    """locked 在前（必须保留），不足部分用 extra 填到 target_k，并去重。"""
    result: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for rgb in list(locked) + list(extra):
        if rgb in seen:
            continue
        seen.add(rgb)
        result.append(rgb)
        if len(result) >= target_k:
            break
    return result


def build_palette_image(palette: list[tuple[int, int, int]]) -> Image.Image:
    """构造 Pillow 可用的 "P" 模式调色板图。"""
    # Pillow 要求 256*3 的扁平 list
    flat: list[int] = []
    for rgb in palette:
        flat.extend(rgb)
    # 不足 256 色补黑，Pillow 会忽略
    pad = 256 - len(palette)
    flat.extend([0, 0, 0] * max(0, pad))
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(flat[: 256 * 3])
    return pal_img
