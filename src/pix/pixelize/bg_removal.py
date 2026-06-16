"""背景去除：pixel_bg 双阈值连通域 + 二值 Alpha。

设计原则：
- 不依赖 rembg 这种重模型；对"像素主体 + 纯色 key 背景"的图片效果最好
- 对齐 `C:\\Users\\78574\\Downloads\\test` 项目方法：边框中位数背景色、core/grow 双阈值、连通域、去溢色、硬边透明
- 默认会清理主体内部封闭 key 背景区，并保留旧函数名/参数以兼容现有调用链
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

import numpy as np
from PIL import Image
from scipy import ndimage


@dataclass
class RemovalConfig:
    """像素素材背景去除配置。

    该配置对齐 `C:\\Users\\78574\\Downloads\\test` 项目的 pixel_bg 方法：
    自动探测/指定 key 背景色 → 双阈值连通域区域生长 → 去溢色 → 二值 alpha。
    """

    t_core: float = 60.0
    t_grow: float = 120.0
    connectivity: int = 8
    border_width: int = 2
    despill: bool = True
    remove_enclosed_background: bool = True
    min_subject_area: int = 0
    uniformity_guard: float = 30.0
    bg_color: tuple[int, int, int] | None = None
    enforce_uniformity_guard: bool = True

    def __post_init__(self) -> None:
        if self.t_core >= self.t_grow:
            raise ValueError("t_core 必须小于 t_grow")


@dataclass
class RemovalResult:
    image: Image.Image
    bg_color: tuple[int, int, int]
    confidence: str
    stats: dict[str, Any] = field(default_factory=dict)


def _config_from_legacy_tolerance(
    tolerance: int,
    *,
    bg_color: tuple[int, int, int] | None = None,
    remove_enclosed_background: bool = True,
    enforce_uniformity_guard: bool = True,
) -> RemovalConfig:
    """把项目历史 bg_tolerance 映射到 pixel_bg 双阈值。

    26 是当前素材直出的默认容差，映射为参考项目默认 t_core=60 / t_grow=120。
    更低容差会同比收紧；高于 26 时保持参考默认，避免旧 green_screen_tolerance=48
    被放大成过度 aggressive 的阈值。
    """
    safe = max(0, int(tolerance))
    if safe <= 0:
        return RemovalConfig(
            t_core=0.5,
            t_grow=0.51,
            bg_color=bg_color,
            remove_enclosed_background=remove_enclosed_background,
            enforce_uniformity_guard=enforce_uniformity_guard,
        )
    scale = min(1.0, safe / 26.0)
    return RemovalConfig(
        t_core=max(1.0, 60.0 * scale),
        t_grow=max(2.0, 120.0 * scale),
        bg_color=bg_color,
        remove_enclosed_background=remove_enclosed_background,
        enforce_uniformity_guard=enforce_uniformity_guard,
    )


def _border_pixels(rgb: np.ndarray, border_width: int) -> np.ndarray:
    """返回边框带的所有像素，形状 (N, 3)。"""
    h, w = rgb.shape[:2]
    bw = max(1, min(int(border_width), max(1, h // 2), max(1, w // 2)))
    top = rgb[:bw, :, :].reshape(-1, 3)
    bottom = rgb[-bw:, :, :].reshape(-1, 3)
    left = rgb[:, :bw, :].reshape(-1, 3)
    right = rgb[:, -bw:, :].reshape(-1, 3)
    return np.concatenate([top, bottom, left, right], axis=0)


def detect_background_color(rgb: np.ndarray, border_width: int) -> tuple[np.ndarray, float]:
    """从边框带探测背景参考色；返回 (每通道中位数背景色, 平均色距方差指标)。"""
    border = _border_pixels(rgb, border_width).astype(np.float64)
    bg = np.median(border, axis=0)
    dist = np.sqrt(((border - bg) ** 2).sum(axis=1))
    return bg, float(dist.mean())


def color_distance(rgb: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """每像素到背景色的 RGB 欧氏距离，返回 (H, W) float64。"""
    diff = rgb.astype(np.float64) - np.asarray(bg, dtype=np.float64)
    return np.sqrt((diff ** 2).sum(axis=2))


def _adaptive_thresholds(config: RemovalConfig, variance: float) -> tuple[float, float, bool]:
    """根据边框纯度收紧双阈值，避免纯色 key 背景吞掉相近主体色。

    旧默认 tolerance=26 会映射到 t_core=60/t_grow=120。对边框极纯的洋红、绿幕、
    白底素材来说，120 的 loose 阈值会把橙棕皮革等距离约 100 的主体色也连成背景。
    边框越纯，说明真实背景颜色越稳定，grow 阈值可以更保守；边框复杂时保持旧阈值。
    """
    t_core = float(config.t_core)
    t_grow = float(config.t_grow)
    if not config.enforce_uniformity_guard and config.bg_color is not None:
        return t_core, t_grow, False
    if variance > float(config.uniformity_guard):
        return t_core, t_grow, False
    adaptive_grow = max(t_core + 8.0, 36.0 + float(variance) * 3.0)
    next_grow = min(t_grow, adaptive_grow)
    return t_core, next_grow, next_grow < t_grow


def compute_background_mask(
    distance: np.ndarray,
    t_core: float,
    t_grow: float,
    connectivity: int = 8,
    *,
    require_border: bool = True,
) -> np.ndarray:
    """pixel_bg 双阈值区域生长背景掩码。

    背景 = 含高置信度种子 (distance < t_core) 的 loose (distance < t_grow) 连通域。
    require_border=False 时也会清除被主体包围的封闭 key 色背景区。
    """
    seed = distance < float(t_core)
    loose = distance < float(t_grow)

    structure = ndimage.generate_binary_structure(2, 2 if int(connectivity) == 8 else 1)
    labels, _count = ndimage.label(loose, structure=structure)

    seed_labels = set(np.unique(labels[seed]).tolist())
    seed_labels.discard(0)

    keep = seed_labels
    if require_border:
        border_ids = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
        border_labels = set(np.unique(border_ids).tolist())
        border_labels.discard(0)
        keep = seed_labels & border_labels

    if not keep:
        return np.zeros(distance.shape, dtype=bool)
    return np.isin(labels, list(keep))


def _despill_key_color(rgb: np.ndarray, bg_mask: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """按参考项目 despill_magenta 思路中和 key 色溢色，并泛化到动态 key 色。"""
    out = rgb.copy()
    subject = ~bg_mask
    if not subject.any():
        return out
    edge = subject & ndimage.binary_dilation(bg_mask)
    key = np.asarray(bg, dtype=np.float64)
    key_max = float(key.max())
    key_min = float(key.min())
    high_channels = key >= key_max - 16.0
    low_channels = key <= key_min + 16.0
    if not high_channels.any() or not low_channels.any():
        return out

    arr = out.astype(np.int16)
    high = arr[..., high_channels]
    low = arr[..., low_channels]
    low_mean = np.rint(low.mean(axis=2)).astype(np.int16)
    leans = edge & (high.min(axis=2) > low_mean)
    if not leans.any():
        return out
    for channel, is_high in enumerate(high_channels.tolist()):
        if is_high:
            channel_values = arr[..., channel]
            out[..., channel] = np.where(leans, np.minimum(channel_values, low_mean), channel_values).astype(np.uint8)
    return out


def apply_binary_alpha(
    rgb: np.ndarray,
    bg_mask: np.ndarray,
    min_subject_area: int = 0,
) -> np.ndarray:
    """生成硬边 RGBA：背景 alpha=0，主体 alpha=255。"""
    alpha = np.where(bg_mask, 0, 255).astype(np.uint8)

    if int(min_subject_area) > 0:
        subject = ~bg_mask
        labels, n_labels = ndimage.label(subject)
        if n_labels > 0:
            sizes = ndimage.sum(
                np.ones_like(labels),
                labels,
                index=np.arange(1, n_labels + 1),
            )
            small_ids = [i + 1 for i, size in enumerate(sizes) if size < int(min_subject_area)]
            if small_ids:
                remove = np.isin(labels, small_ids)
                alpha = np.where(remove, 0, alpha).astype(np.uint8)

    out = np.dstack([rgb[..., :3], alpha])
    transparent = out[..., 3] == 0
    if transparent.any():
        out[transparent, :3] = 0
    return out


def remove_background_with_result(
    image: Image.Image,
    config: RemovalConfig | None = None,
) -> RemovalResult:
    """pixel_bg 参考方法：返回带 confidence/stats 的结果对象。"""
    config = config or RemovalConfig()
    rgba = image.convert("RGBA")
    arr = np.asarray(rgba).copy()
    rgb = arr[..., :3]

    if _border_transparency_ratio(arr) >= 0.05:
        transparent = arr[..., 3] == 0
        if transparent.any():
            arr[transparent, :3] = 0
        return RemovalResult(
            image=Image.fromarray(arr, mode="RGBA"),
            bg_color=(0, 0, 0),
            confidence="high",
            stats={"reason": "already_transparent_border", "bg_ratio": float(transparent.mean())},
        )

    if config.bg_color is None:
        bg, variance = detect_background_color(rgb, config.border_width)
    else:
        bg = np.asarray(config.bg_color, dtype=np.float64)
        border = _border_pixels(rgb, config.border_width).astype(np.float64)
        variance = float(np.sqrt(((border - bg) ** 2).sum(axis=1)).mean())
    bg_tuple = tuple(int(round(float(channel))) for channel in bg[:3])

    if config.enforce_uniformity_guard and variance > float(config.uniformity_guard):
        return RemovalResult(
            image=rgba,
            bg_color=bg_tuple,
            confidence="low",
            stats={"reason": "border_not_uniform", "variance": variance},
        )

    t_core, t_grow, thresholds_adapted = _adaptive_thresholds(config, variance)
    distance = color_distance(rgb, bg)
    bg_mask = compute_background_mask(
        distance,
        t_core,
        t_grow,
        config.connectivity,
        require_border=not config.remove_enclosed_background,
    )

    work_rgb = rgb.copy()
    if config.despill:
        work_rgb = _despill_key_color(work_rgb, bg_mask, bg)

    out_arr = apply_binary_alpha(work_rgb, bg_mask, config.min_subject_area)
    out_img = Image.fromarray(out_arr, mode="RGBA")
    return RemovalResult(
        image=out_img,
        bg_color=bg_tuple,
        confidence="high",
        stats={
            "bg_ratio": float(bg_mask.mean()),
            "variance": variance,
            "t_core": float(t_core),
            "t_grow": float(t_grow),
            "thresholds_adapted": bool(thresholds_adapted),
        },
    )


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
    """兼容旧 key-color 入口，实际统一走 pixel_bg 双阈值连通域方法。"""
    _ = (
        spill_tolerance,
        edge_speckle,
        edge_speckle_max_area,
        edge_speckle_max_thickness,
        edge_speckle_radius,
        edge_speckle_passes,
        edge_spill,
        edge_spill_radius,
        edge_spill_passes,
        edge_spill_outline,
    )
    return apply_pixel_bg_alpha(image, key_rgb=key_rgb, tolerance=tolerance)


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


def _corner_colors_consistent(
    colors: list[tuple[int, int, int]],
    tolerance: int,
) -> bool:
    """判断四角主色是否只是同一背景的轻微波动。"""
    if len(colors) <= 1:
        return True
    tol_sq = max(0, int(tolerance)) ** 2 * 3
    refs = [np.asarray(color, dtype=np.int32) for color in colors]
    for i, left in enumerate(refs):
        for right in refs[i + 1:]:
            diff = left - right
            if int((diff * diff).sum()) > tol_sq:
                return False
    return True


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


def _is_single_solid_background_reference(
    ref_colors: list[tuple[int, int, int]],
    tolerance: int,
) -> bool:
    """判断边缘背景是否足够接近单一纯色，避免把棋盘格内高光当孔洞删除。"""
    if not ref_colors:
        return False
    refs = np.asarray(ref_colors, dtype=np.int16)
    channel_span = refs.max(axis=0) - refs.min(axis=0)
    # 只在背景近似单一纯色时清理封闭孔洞；假透明棋盘格通常会超过该范围。
    max_channel_span = max(4, min(12, int(tolerance) // 2))
    return bool((channel_span <= max_channel_span).all())


def _is_chroma_key_background_reference(
    ref_colors: list[tuple[int, int, int]],
    tolerance: int,
) -> bool:
    """判断角点是否属于同一 chroma-key 背景，即使亮度/混色有轻微波动。

    PerfectPixel 自动采样后，纯 key 背景角点可能从 #fb03f8 变成
    #ee22ec 这类同色相混色。它不满足严格单色 channel span，但仍应走
    Color-to-Alpha；否则 fallback flood-fill 会把整圈边缘里的主体暗色采作背景
    seed，导致主体边缘被误删。
    """
    if not ref_colors:
        return False
    refs = np.asarray(ref_colors, dtype=np.float32)
    key = np.median(refs, axis=0)
    if not _looks_like_chroma_key(key):
        return False
    distances = np.linalg.norm(refs - key, axis=1)
    max_distance = max(float(tolerance) * 2.0, 48.0)
    if bool((distances > max_distance).any()):
        return False
    tinted = _key_tinted_mask(refs.reshape((len(refs), 1, 3)), key, min_chroma=24.0).reshape(-1)
    return bool(tinted.all())


def _background_color_mask(
    arr: np.ndarray,
    ref_colors: list[tuple[int, int, int]],
    tolerance: int,
) -> np.ndarray:
    """返回所有接近背景参考色的像素，不要求与边缘连通。"""
    h, w, _ = arr.shape
    if not ref_colors:
        return np.zeros((h, w), dtype=bool)
    rgb = arr.astype(np.int32)
    tol_sq = max(0, int(tolerance)) ** 2 * 3
    mask = np.zeros((h, w), dtype=bool)
    for ref_color in ref_colors:
        ref = np.asarray(ref_color, dtype=np.int32)
        diff = rgb - ref
        mask |= (diff * diff).sum(axis=2) <= tol_sq
    return mask


def _closed_background_hole_mask(
    background_like: np.ndarray,
    border_connected: np.ndarray,
    *,
    max_area_ratio: float = 0.35,
) -> np.ndarray:
    """找出被主体轮廓封闭、但颜色仍像背景色的孔洞区域。"""
    candidates = background_like & ~border_connected
    h, w = candidates.shape
    visited = np.zeros(candidates.shape, dtype=bool)
    result = np.zeros(candidates.shape, dtype=bool)
    max_area = max(1, int(round(h * w * float(max_area_ratio))))
    for y in range(h):
        for x in range(w):
            if not candidates[y, x] or visited[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
            visited[y, x] = True
            pixels: list[tuple[int, int]] = []
            touches_border = False
            while q:
                cy, cx = q.popleft()
                pixels.append((cy, cx))
                touches_border |= cy in (0, h - 1) or cx in (0, w - 1)
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and candidates[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        q.append((ny, nx))
            if not touches_border and len(pixels) <= max_area:
                for py, px in pixels:
                    result[py, px] = True
    return result


def _fuzzy_color_match_mask(
    rgb: np.ndarray,
    ref_colors: Iterable[tuple[int, int, int]],
    tolerance: int,
) -> np.ndarray:
    """返回 ImageMagick fuzz 语义下可视为目标背景色的像素。

    项目使用 0-255 的 tolerance。这里保留历史容差手感：单通道轻微波动可被视为
    同色，同时仍用 RGB 距离避免大范围误删。
    """
    if rgb.ndim != 3 or rgb.shape[-1] < 3:
        raise ValueError("_fuzzy_color_match_mask 需要 RGB/RGBA 数组")
    refs = list(ref_colors)
    h, w = rgb.shape[:2]
    if not refs:
        return np.zeros((h, w), dtype=bool)
    safe_tolerance = max(0, int(tolerance))
    tol_sq = safe_tolerance * safe_tolerance * 3
    rgb_i = rgb[..., :3].astype(np.int32)
    match = np.zeros((h, w), dtype=bool)
    for ref_color in refs:
        ref = np.asarray(ref_color, dtype=np.int32)
        diff = rgb_i - ref
        match |= (diff * diff).sum(axis=2) <= tol_sq
    return match



def _border_transparency_ratio(rgba: np.ndarray) -> float:
    """返回图像四边中 alpha=0 的比例，用于避免透明 RGB 被当作背景色。"""
    if rgba.ndim != 3 or rgba.shape[-1] < 4:
        return 0.0
    h, w = rgba.shape[:2]
    if h == 0 or w == 0:
        return 0.0
    border_parts = [rgba[0, :, 3], rgba[h - 1, :, 3]]
    if h > 2:
        border_parts.extend([rgba[1:h - 1, 0, 3], rgba[1:h - 1, w - 1, 3]])
    border = np.concatenate([part.reshape(-1) for part in border_parts if part.size > 0])
    if border.size == 0:
        return 0.0
    return float((border == 0).sum() / border.size)



def _border_seed_points(mask: np.ndarray) -> list[tuple[int, int]]:
    """返回 mask 中位于图像四边的 seed 点。"""
    if mask.ndim != 2:
        raise ValueError("_border_seed_points 需要二维 mask")
    h, w = mask.shape
    if h == 0 or w == 0:
        return []
    seeds: list[tuple[int, int]] = []
    for x in range(w):
        if mask[0, x]:
            seeds.append((0, x))
        if h > 1 and mask[h - 1, x]:
            seeds.append((h - 1, x))
    for y in range(1, max(1, h - 1)):
        if mask[y, 0]:
            seeds.append((y, 0))
        if w > 1 and mask[y, w - 1]:
            seeds.append((y, w - 1))
    return seeds



def _scanline_floodfill_mask(mask: np.ndarray, seeds: Iterable[tuple[int, int]]) -> np.ndarray:
    """基于预先算好的 fuzzy mask 做 scanline flood fill。"""
    if mask.ndim != 2:
        raise ValueError("_scanline_floodfill_mask 需要二维 mask")
    h, w = mask.shape
    filled = np.zeros((h, w), dtype=bool)
    stack: deque[tuple[int, int]] = deque()
    for sy, sx in seeds:
        if 0 <= sy < h and 0 <= sx < w and mask[sy, sx] and not filled[sy, sx]:
            stack.append((sy, sx))

    while stack:
        y, x = stack.pop()
        if not (0 <= y < h and 0 <= x < w) or filled[y, x] or not mask[y, x]:
            continue

        left = x
        while left > 0 and mask[y, left - 1] and not filled[y, left - 1]:
            left -= 1
        right = x
        while right + 1 < w and mask[y, right + 1] and not filled[y, right + 1]:
            right += 1
        filled[y, left:right + 1] = True

        for ny in (y - 1, y + 1):
            if ny < 0 or ny >= h:
                continue
            nx = left
            while nx <= right:
                while nx <= right and (filled[ny, nx] or not mask[ny, nx]):
                    nx += 1
                if nx <= right:
                    stack.append((ny, nx))
                    while nx <= right and (not filled[ny, nx]) and mask[ny, nx]:
                        nx += 1
    return filled



def apply_imagemagick_fuzz_floodfill_alpha(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int] | None = None,
    ref_colors: Iterable[tuple[int, int, int]] | None = None,
    seeds: Iterable[tuple[int, int]] | None = None,
    tolerance: int = 12,
    clear_transparent_rgb: bool = True,
) -> Image.Image:
    """兼容旧函数名，实际改用 pixel_bg 双阈值连通域背景去除。

    `key_rgb` 会作为显式背景色；未传时从边框中位数自动探测。`ref_colors` / `seeds`
    是旧 ImageMagick floodfill 兼容参数，新算法不再依赖 seed floodfill。
    """
    _ = (ref_colors, seeds)
    config = _config_from_legacy_tolerance(
        tolerance,
        bg_color=key_rgb,
        remove_enclosed_background=True,
        # 显式 key 色常用于 sprite/contact sheet：主体可能触边，不能因为边框方差高就跳过抠图。
        enforce_uniformity_guard=key_rgb is None,
    )
    out = remove_background_with_result(image, config).image
    if clear_transparent_rgb:
        rgba = np.asarray(out.convert("RGBA")).copy()
        transparent = rgba[..., 3] == 0
        if transparent.any():
            rgba[transparent, :3] = 0
        out = Image.fromarray(rgba, mode="RGBA")
    return out


def apply_pixel_bg_alpha(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int] | None = None,
    tolerance: int = 12,
    clear_transparent_rgb: bool = True,
) -> Image.Image:
    """新命名入口：使用 pixel_bg 双阈值连通域生成透明 alpha。"""
    return apply_imagemagick_fuzz_floodfill_alpha(
        image,
        key_rgb=key_rgb,
        tolerance=tolerance,
        clear_transparent_rgb=clear_transparent_rgb,
    )



def _interpolate_alpha(value: np.ndarray, interpolation: str | None) -> np.ndarray:
    mode = (interpolation or "linear").strip().lower()
    if mode == "power":
        return value ** 2
    if mode == "root":
        return np.sqrt(value)
    if mode == "smooth":
        return (np.sin(np.pi / 2 * value)) ** 2
    if mode in {"inverse-sin", "inverse_sin"}:
        return np.arcsin(2 * value - 1) / np.pi + 0.5
    return value


def _color_distance(rgb: np.ndarray, key: np.ndarray, shape: str) -> np.ndarray:
    mode = (shape or "sphere").strip().lower()
    diff = np.abs(rgb.astype(np.float32) - key.astype(np.float32))
    if mode == "cube":
        return diff.max(axis=2)
    return np.linalg.norm(diff, axis=2)


def apply_color_to_alpha(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int],
    transparency_threshold: int = 48,
    opacity_threshold: int = 255,
    shape: str = "sphere",
    interpolation: str | None = "linear",
    protect_non_key_tinted: bool = True,
    min_key_chroma: float = 24.0,
) -> Image.Image:
    """兼容旧 Color-to-Alpha 入口，实际统一走 pixel_bg 双阈值连通域方法。"""
    _ = (
        opacity_threshold,
        shape,
        interpolation,
        protect_non_key_tinted,
        min_key_chroma,
    )
    return apply_pixel_bg_alpha(
        image,
        key_rgb=key_rgb,
        tolerance=max(0, int(transparency_threshold)),
    )


def apply_key_color_soft_matte(
    image: Image.Image,
    *,
    key_rgb: tuple[int, int, int],
    background_mask: np.ndarray | None = None,
    tolerance: int = 48,
    softness: int = 220,
    alpha_floor: int = 8,
    radius: int = 2,
    passes: int = 3,
) -> Image.Image:
    """用 key color 软抠 + despill 清理半透明/混色背景边缘。

    硬抠只能删除接近纯 key color 的像素；模型生成、缩放或抗锯齿后，边缘常会变成
    `前景 * alpha + key * (1-alpha)` 的混色。这里按与 key color 的距离估算 alpha，
    再反混合去掉 RGB 里的 key 污染，只作用在透明背景附近，避免误伤主体内部颜色。
    """
    rgba = np.asarray(image.convert("RGBA")).copy()
    _apply_key_color_soft_matte(
        rgba,
        key_rgb=key_rgb,
        background_mask=background_mask,
        tolerance=tolerance,
        softness=softness,
        alpha_floor=alpha_floor,
        radius=radius,
        passes=passes,
    )
    transparent = rgba[..., 3] == 0
    if transparent.any():
        rgba[transparent, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _apply_key_color_soft_matte(
    rgba: np.ndarray,
    *,
    key_rgb: tuple[int, int, int],
    background_mask: np.ndarray | None,
    tolerance: int,
    softness: int = 220,
    alpha_floor: int = 8,
    radius: int = 2,
    passes: int = 3,
) -> dict:
    if rgba.ndim != 3 or rgba.shape[-1] < 4:
        return {"applied": False, "reason": "not_rgba"}
    key = np.asarray(key_rgb, dtype=np.float32)
    if not _looks_like_chroma_key(key):
        return {"applied": False, "reason": "background_not_chroma_key"}

    h, w = rgba.shape[:2]
    soft = max(float(tolerance) + 1.0, min(255.0, float(softness)))
    hard = max(0.0, float(tolerance))
    floor = max(0.0, min(255.0, float(alpha_floor))) / 255.0
    safe_radius = max(1, int(radius))
    changed = 0

    if background_mask is not None and background_mask.shape == (h, w):
        seed = background_mask.copy()
    else:
        seed = rgba[..., 3] == 0

    for _ in range(max(1, int(passes))):
        alpha = rgba[..., 3].astype(np.float32) / 255.0
        visible = alpha > 0.0
        if not visible.any():
            break
        near = seed | (rgba[..., 3] == 0)
        for _distance in range(safe_radius):
            near = _dilate_mask_8(near)

        rgb = rgba[..., :3].astype(np.float32)
        dist = np.sqrt(((rgb - key) ** 2).sum(axis=2))
        key_tinted = _key_tinted_mask(rgb, key, min_chroma=24.0)
        candidates = visible & near & key_tinted & (dist <= soft)
        if background_mask is not None and background_mask.shape == (h, w):
            candidates &= ~background_mask
        if not candidates.any():
            break

        estimated_alpha = np.clip((dist - hard) / max(1.0, soft - hard), 0.0, 1.0)
        new_alpha = np.minimum(alpha, estimated_alpha)
        improve = candidates & (new_alpha < alpha - (1.0 / 255.0))
        if not improve.any():
            break

        safe_alpha = np.maximum(new_alpha[improve], 1.0 / 255.0)
        rgb_improve = rgb[improve]
        decontaminated = (rgb_improve - key * (1.0 - safe_alpha[:, None])) / safe_alpha[:, None]
        rgba[improve, :3] = np.clip(decontaminated, 0, 255).astype(np.uint8)
        rgba[improve, 3] = np.clip(np.rint(new_alpha[improve] * 255.0), 0, 255).astype(np.uint8)
        low_alpha = improve & (new_alpha <= floor)
        if low_alpha.any():
            rgba[low_alpha, :3] = 0
            rgba[low_alpha, 3] = 0
            seed |= low_alpha
        changed += int(improve.sum())

    return {
        "applied": changed > 0,
        "changed_pixels": changed,
        "tolerance": int(tolerance),
        "softness": int(soft),
        "alpha_floor": int(alpha_floor),
        "radius": safe_radius,
    }


def _looks_like_chroma_key(rgb: np.ndarray) -> bool:
    channel_max = float(rgb.max())
    channel_min = float(rgb.min())
    return bool(channel_max >= 160.0 and (channel_max - channel_min) >= 96.0)


def _key_tinted_mask(rgb: np.ndarray, key: np.ndarray, *, min_chroma: float = 24.0) -> np.ndarray:
    """只匹配具有 key 色方向的混色像素，避免误伤灰/白/金属色。

    例如 #FF00FF 背景的真实残留应表现为 R/B 明显高于 G；普通灰白色虽然
    到品红的欧氏距离也可能小于 255，但不具有这种通道方向，不能被当成 key halo。
    """
    key_max = float(key.max())
    key_min = float(key.min())
    high_channels = key >= key_max - 16.0
    low_channels = key <= key_min + 16.0
    if not high_channels.any() or not low_channels.any():
        return np.zeros(rgb.shape[:2], dtype=bool)
    high = rgb[..., high_channels].mean(axis=2)
    low = rgb[..., low_channels].mean(axis=2)
    return (high - low) >= float(min_chroma)


def apply_transparent_edge_style(
    image: Image.Image,
    *,
    feather: int = 0,
    edge_style: Literal["hard", "feather", "outline"] = "hard",
) -> Image.Image:
    """对已有透明背景的图片应用羽化或描边边缘处理。"""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    rgba = np.asarray(image).copy()
    mask_bg = rgba[..., 3] == 0
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


def remove_background(
    image: Image.Image,
    *,
    tolerance: int = 12,
    feather: int = 0,
    edge_style: Literal["hard", "feather", "outline"] = "hard",
    keep_border_bleed: bool = True,
    bg_removal_algorithm: str = "auto",
    color_to_alpha_shape: str = "sphere",
    color_to_alpha_transparency: int = 48,
    color_to_alpha_opacity: int = 255,
    color_to_alpha_interpolation: str = "linear",
) -> Image.Image:
    """去背景入口：统一使用参考项目 pixel_bg 算法。

    流程为：边框中位数探测背景色 → 双阈值连通域区域生长 → key 色去溢色 → 二值 alpha。
    旧的 `bg_removal_algorithm` / Color-to-Alpha 配置仅保留兼容，不再改变实现路径。
    """
    _ = (
        keep_border_bleed,
        bg_removal_algorithm,
        color_to_alpha_shape,
        color_to_alpha_transparency,
        color_to_alpha_opacity,
        color_to_alpha_interpolation,
    )
    config = _config_from_legacy_tolerance(
        tolerance,
        remove_enclosed_background=True,
        enforce_uniformity_guard=True,
    )
    out = remove_background_with_result(image, config).image
    style = edge_style if edge_style in ("hard", "feather", "outline") else "hard"
    strength = max(0, int(feather))
    if style in {"feather", "outline"} and strength > 0:
        out = apply_transparent_edge_style(out, feather=strength, edge_style=style)
    return out


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
