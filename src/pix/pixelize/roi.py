"""ROI 与语义区域处理工具。"""

from __future__ import annotations

import numpy as np
from PIL import Image

from pix.analysis.schema import BBoxNorm, SemanticRegion
from pix.pixelize.palette import hex_to_rgb


def bbox_to_pixels(bbox: BBoxNorm, width: int, height: int) -> tuple[int, int, int, int]:
    x = int(round(bbox.x * width))
    y = int(round(bbox.y * height))
    w = max(1, int(round(bbox.w * width)))
    h = max(1, int(round(bbox.h * height)))
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = min(w, width - x)
    h = min(h, height - y)
    return x, y, w, h


def apply_semantic_regions(
    image: Image.Image, regions: list[SemanticRegion]
) -> Image.Image:
    """对每个语义区域做最近邻颜色替换：把区域内像素靠向 palette_hint 里的颜色。"""
    if not regions:
        return image
    img = image.convert("RGB")
    arr = np.asarray(img, dtype=np.int32).copy()
    h, w, _ = arr.shape
    for region in regions:
        if not region.palette_hint:
            continue
        x0, y0, bw, bh = bbox_to_pixels(region.bbox_norm, w, h)
        patch = arr[y0 : y0 + bh, x0 : x0 + bw, :]
        if patch.size == 0:
            continue
        palette = np.array([hex_to_rgb(h_) for h_ in region.palette_hint], dtype=np.int32)
        # 计算 patch 每个像素到调色板的欧氏距离，取最小
        flat = patch.reshape(-1, 3)
        diff = flat[:, None, :] - palette[None, :, :]
        dist = np.sum(diff * diff, axis=2)
        idx = np.argmin(dist, axis=1)
        mapped = palette[idx].reshape(patch.shape)
        arr[y0 : y0 + bh, x0 : x0 + bw, :] = mapped
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")
