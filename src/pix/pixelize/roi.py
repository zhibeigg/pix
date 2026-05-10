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
    """对每个语义区域做最近邻颜色替换，并保留输入 alpha。

    透明素材常见于图标生成。早期实现会 `convert("RGB")`，导致透明背景的 alpha
    被丢弃，随后量化阶段会把隐藏 RGB 当成可见颜色，出现大块浅色矩形背景。
    """
    if not regions:
        return image
    had_alpha = "A" in image.getbands() or "transparency" in image.info
    img = image.convert("RGBA" if had_alpha else "RGB")
    raw = np.asarray(img, dtype=np.uint8)
    rgb_arr = raw[..., :3].astype(np.int32).copy()
    alpha = raw[..., 3].copy() if had_alpha else None
    h, w, _ = rgb_arr.shape
    visible = alpha > 8 if alpha is not None else None

    for region in regions:
        if not region.palette_hint:
            continue
        # 覆盖整张图的语义区域通常是 aura / background / sparkles 的全局提示。
        # 若直接应用，会把真实或假透明背景也映射成调色板颜色，形成整块色底。
        if region.bbox_norm.w >= 0.98 and region.bbox_norm.h >= 0.98:
            continue
        x0, y0, bw, bh = bbox_to_pixels(region.bbox_norm, w, h)
        patch = rgb_arr[y0 : y0 + bh, x0 : x0 + bw, :]
        if patch.size == 0:
            continue
        if visible is not None:
            patch_visible = visible[y0 : y0 + bh, x0 : x0 + bw]
            if not patch_visible.any():
                continue
        else:
            patch_visible = None
        palette = np.array([hex_to_rgb(h_) for h_ in region.palette_hint], dtype=np.int32)
        # 计算 patch 每个可见像素到调色板的欧氏距离，取最小。
        if patch_visible is not None:
            flat = patch[patch_visible]
        else:
            flat = patch.reshape(-1, 3)
        diff = flat[:, None, :] - palette[None, :, :]
        dist = np.sum(diff * diff, axis=2)
        idx = np.argmin(dist, axis=1)
        mapped = palette[idx]
        if patch_visible is not None:
            patch[patch_visible] = mapped
        else:
            patch[:, :, :] = mapped.reshape(patch.shape)
        rgb_arr[y0 : y0 + bh, x0 : x0 + bw, :] = patch

    rgb = np.clip(rgb_arr, 0, 255).astype(np.uint8)
    if alpha is not None:
        rgba = np.dstack([rgb, alpha]).astype(np.uint8)
        return Image.fromarray(rgba, mode="RGBA")
    return Image.fromarray(rgb, mode="RGB")
