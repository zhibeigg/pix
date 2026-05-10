"""像素化主算法。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from pix.analysis.schema import PixAnalysis
from pix.config import PixelizeConfig
from pix.pixelize.bg_removal import remove_background
from pix.pixelize.palette import (
    build_palette_image,
    hex_to_rgb,
    kmeans_palette,
    merge_palette,
    swatches_to_rgb_list,
)
from pix.pixelize.presets import Preset, load_preset
from pix.pixelize.roi import apply_semantic_regions


Dither = Literal["none", "ordered", "floyd_steinberg"]
ResampleMode = Literal["smart", "box", "bicubic", "lanczos", "nearest"]


@dataclass
class PixelizeParams:
    output_size: tuple[int, int] = (128, 128)
    colors: int = 16
    dither: Dither = "floyd_steinberg"
    preset: str = "auto"
    preview_scale: int = 4
    edge_enhance: float = 0.1
    saturation: float = 1.0
    resample: ResampleMode = "smart"
    snap_to_grid: bool = True
    remove_bg: bool = False
    bg_tolerance: int = 12
    bg_feather: int = 0

    @classmethod
    def from_config(cls, cfg: PixelizeConfig) -> "PixelizeParams":
        return cls(
            output_size=tuple(cfg.output_size),  # type: ignore[arg-type]
            colors=cfg.colors,
            dither=cfg.dither,  # type: ignore[arg-type]
            preset=cfg.preset,
            preview_scale=cfg.preview_scale,
            edge_enhance=cfg.edge_enhance,
            saturation=cfg.saturation,
            resample=getattr(cfg, "resample", "smart"),  # type: ignore[arg-type]
            snap_to_grid=getattr(cfg, "snap_to_grid", True),
            remove_bg=getattr(cfg, "remove_bg", False),
            bg_tolerance=getattr(cfg, "bg_tolerance", 12),
            bg_feather=getattr(cfg, "bg_feather", 0),
        )


def _resolve_preset(params: PixelizeParams, analysis: PixAnalysis | None) -> Preset | None:
    """合并预设：显式指定 > analysis 推荐 > None。"""
    if params.preset and params.preset != "auto":
        return load_preset(params.preset)
    if analysis is not None:
        name = analysis.style.recommended_preset
        if name and name != "auto":
            return load_preset(name)
    return None


def _effective_params(
    params: PixelizeParams, preset: Preset | None, analysis: PixAnalysis | None
) -> PixelizeParams:
    """将用户传入 params 与预设、analysis 合并；用户显式值优先，但我们只在"值等于默认"时才用预设兜底。

    简化策略：这里由调用方保证 params 已经是 "用户覆盖 ∪ 默认值" 后的结果，
    我们只在 preset 存在且 params 的对应字段还是 **配置默认值** 的情况下填充；
    这通过引入 "sentinel" 来做不实用。
    实际策略：preset 只在 params.preset 明确指定或 analysis 推荐时启用；
    启用后，preset 字段如果为非 None 就生效，用户自己再在 CLI 里覆盖具体字段。
    """
    if preset is None and analysis is None:
        return params

    eff = PixelizeParams(
        output_size=params.output_size,
        colors=params.colors,
        dither=params.dither,
        preset=params.preset,
        preview_scale=params.preview_scale,
        edge_enhance=params.edge_enhance,
        saturation=params.saturation,
    )

    if preset is not None:
        if preset.output_size is not None:
            eff.output_size = preset.output_size
        if preset.colors is not None:
            eff.colors = preset.colors
        if preset.dither is not None:
            eff.dither = preset.dither  # type: ignore[assignment]
        if preset.edge_enhance is not None:
            eff.edge_enhance = preset.edge_enhance
        if preset.saturation is not None:
            eff.saturation = preset.saturation

    if analysis is not None:
        if analysis.style.target_color_count:
            # analysis 提供的色数只在没有 preset 指定时生效
            if preset is None or preset.colors is None:
                eff.colors = max(2, min(256, int(analysis.style.target_color_count)))
        if analysis.style.suggested_dither and (preset is None or preset.dither is None):
            eff.dither = analysis.style.suggested_dither  # type: ignore[assignment]

    return eff


def _detect_grid_size(image: Image.Image, max_probe: int = 24) -> int:
    """粗略检测输入图的"像素格"边长（多少个原始像素对应 1 个像素块）。

    原理：对亮度通道沿 x / y 各取差分，统计"变化剧烈"行/列之间的间距，
    取众数近似格子尺寸。对整齐的像素画、大色块图效果很好；对自然照片会返回 1。
    """
    small = image.convert("L")
    w, h = small.size
    # 大图先统一降到一个工作尺寸，加速且避免长尾极值
    max_side = 512
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        small = small.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
        w, h = small.size

    arr = np.asarray(small, dtype=np.int16)
    # 用邻列差平均值判定"这列是否是色块边界"
    col_edge = np.abs(np.diff(arr, axis=1)).mean(axis=0)
    row_edge = np.abs(np.diff(arr, axis=0)).mean(axis=1)

    threshold = max(10.0, float(col_edge.mean() * 1.8))

    def _periods(edge: np.ndarray) -> list[int]:
        idxs = np.where(edge > threshold)[0]
        if len(idxs) < 3:
            return []
        deltas = np.diff(idxs)
        return [int(d) for d in deltas if 2 <= d <= max_probe]

    periods = _periods(col_edge) + _periods(row_edge)
    if not periods:
        return 1
    # 取众数
    vals, counts = np.unique(periods, return_counts=True)
    best = int(vals[int(counts.argmax())])
    return max(1, best)


def _downsample(
    image: Image.Image,
    size: tuple[int, int],
    mode: ResampleMode = "smart",
    snap: bool = True,
) -> Image.Image:
    """下采样到目标尺寸。

    - smart: 如果探测到输入有明显像素网格，先按网格 BOX 聚合，再 BOX 缩到目标
      否则退化到"BICUBIC→BOX"两段式，比纯 bicubic 边缘锐一些
    - box: 纯平均采样（对像素画最忠实）
    - bicubic: Pillow 经典平滑缩
    - lanczos: 最锐利的插值，容易有 ringing
    - nearest: 硬采样，保留像素感但会丢细节
    """
    target = size
    mode_map = {
        "box": Image.Resampling.BOX,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
        "nearest": Image.Resampling.NEAREST,
    }

    if mode != "smart":
        return image.resize(target, mode_map.get(mode, Image.Resampling.BICUBIC))

    w, h = image.size
    tw, th = target

    # smart：先对齐输入像素网格
    if snap:
        grid = _detect_grid_size(image)
        if grid >= 2:
            # 聚合到"每个 grid 变成 1 个像素"的中间尺寸
            inter_w = max(1, w // grid)
            inter_h = max(1, h // grid)
            image = image.resize((inter_w, inter_h), Image.Resampling.BOX)
            w, h = image.size

    # 若已经小于等于目标，改用 NEAREST 保留像素感
    if w <= tw and h <= th:
        return image.resize(target, Image.Resampling.NEAREST)

    # 还比目标大：用 BOX 做面积平均（对硬边友好，不会糊）
    return image.resize(target, Image.Resampling.BOX)


def _apply_enhancements(image: Image.Image, saturation: float, edge: float) -> Image.Image:
    img = image
    if abs(saturation - 1.0) > 1e-3:
        img = ImageEnhance.Color(img).enhance(saturation)
    if edge > 1e-3:
        # Pillow 的 EDGE_ENHANCE 是滤镜，强度不可调；用 UnsharpMask 近似
        img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=int(edge * 150), threshold=2))
    return img


def _quantize(
    image: Image.Image,
    palette_rgb: list[tuple[int, int, int]],
    dither: Dither,
) -> Image.Image:
    pal_img = build_palette_image(palette_rgb)
    dither_method = (
        Image.Dither.FLOYDSTEINBERG if dither == "floyd_steinberg"
        else Image.Dither.ORDERED if dither == "ordered"
        else Image.Dither.NONE
    )
    # 保留可能的 alpha：先量化 RGB，再把原 alpha 贴回
    alpha = image.split()[-1] if image.mode == "RGBA" else None
    quantized = image.convert("RGB").quantize(
        palette=pal_img,
        dither=dither_method,
    )
    rgb = quantized.convert("RGB")
    if alpha is not None:
        rgba = rgb.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba
    return rgb


def _build_palette(
    image: Image.Image,
    params: PixelizeParams,
    preset: Preset | None,
    analysis: PixAnalysis | None,
) -> list[tuple[int, int, int]]:
    target_k = max(2, min(256, params.colors))
    locked: list[tuple[int, int, int]] = []
    if preset and preset.palette_lock:
        locked = [hex_to_rgb(h) for h in preset.palette_lock]
        # 锁定调色板意味着 target_k 上限可能被 preset 色数限制；按 params.colors 与锁定数取大
        target_k = max(target_k, len(locked))

    # analysis 的调色板作为首选"附加候选"
    analysis_colors: list[tuple[int, int, int]] = []
    if analysis is not None and analysis.palette:
        analysis_colors = swatches_to_rgb_list(analysis.palette)

    # 用 k-means 从图里再抽若干，作为兜底
    km = kmeans_palette(image, max(2, target_k))

    extra = analysis_colors + km
    palette = merge_palette(locked, extra, target_k)
    # 保底：至少 2 色，且去除重复
    if len(palette) < 2:
        palette = list(dict.fromkeys(palette + km))[:target_k]
    return palette


def pixelize(
    source: Image.Image | str | Path,
    params: PixelizeParams,
    analysis: PixAnalysis | None = None,
) -> tuple[Image.Image, Image.Image | None, dict]:
    """执行像素化。

    Returns:
        (pixel_image, preview_image_or_None, meta_dict)
    """
    if not isinstance(source, Image.Image):
        source = Image.open(source)
    img = source.convert("RGB")

    preset = _resolve_preset(params, analysis)
    eff = _effective_params(params, preset, analysis)

    # 1. 下采样到目标尺寸（smart/box/bicubic/lanczos/nearest）
    detected_grid: int | None = None
    if eff.resample == "smart" and eff.snap_to_grid:
        detected_grid = _detect_grid_size(img)
    down = _downsample(img, eff.output_size, mode=eff.resample, snap=eff.snap_to_grid)
    # 2. 轻微增强
    down = _apply_enhancements(down, eff.saturation, eff.edge_enhance)
    # 3. 语义区域最近邻替换（可选，早期做可以引导后续量化）
    if analysis and analysis.semantic_regions:
        down = apply_semantic_regions(down, analysis.semantic_regions)
    # 4. 构建调色板
    palette_rgb = _build_palette(down, eff, preset, analysis)
    # 5. 量化 + 抖动
    pixelized = _quantize(down, palette_rgb, eff.dither)

    # 6. 可选：抠背景（在量化后做最准——背景块已经是纯色）
    if eff.remove_bg:
        pixelized = remove_background(
            pixelized,
            tolerance=max(0, int(eff.bg_tolerance)),
            feather=max(0, int(eff.bg_feather)),
        )

    # 7. 可选预览（最近邻放大）
    preview: Image.Image | None = None
    scale = max(0, int(eff.preview_scale))
    if scale > 1:
        preview = pixelized.resize(
            (pixelized.width * scale, pixelized.height * scale),
            Image.Resampling.NEAREST,
        )

    meta = {
        "effective_params": {
            "output_size": list(eff.output_size),
            "colors": eff.colors,
            "dither": eff.dither,
            "preset": preset.name if preset else (params.preset or "auto"),
            "preview_scale": eff.preview_scale,
            "edge_enhance": eff.edge_enhance,
            "saturation": eff.saturation,
            "resample": eff.resample,
            "snap_to_grid": eff.snap_to_grid,
            "remove_bg": eff.remove_bg,
            "bg_tolerance": eff.bg_tolerance,
            "bg_feather": eff.bg_feather,
        },
        "palette": ["#{:02X}{:02X}{:02X}".format(*c) for c in palette_rgb],
        "palette_size": len(palette_rgb),
        "used_analysis": analysis is not None,
        "detected_grid": detected_grid,
    }
    return pixelized, preview, meta
