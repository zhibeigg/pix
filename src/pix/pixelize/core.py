"""像素化主算法。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageFilter

from pix.analysis.schema import PixAnalysis
from pix.config import PixelizeConfig
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


@dataclass
class PixelizeParams:
    output_size: tuple[int, int] = (128, 128)
    colors: int = 16
    dither: Dither = "floyd_steinberg"
    preset: str = "auto"
    preview_scale: int = 4
    edge_enhance: float = 0.1
    saturation: float = 1.0

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


def _downsample(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """两段式下采样：先 bicubic 缩到 2x，再 bicubic 缩到目标。"""
    target = size
    intermediate = (target[0] * 2, target[1] * 2)
    img = image.resize(intermediate, Image.Resampling.BICUBIC)
    img = img.resize(target, Image.Resampling.BICUBIC)
    return img


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
    # 使用 FLOYDSTEINBERG + 目标调色板把 RGB 图量化到 P 模式
    quantized = image.convert("RGB").quantize(
        palette=pal_img,
        dither=dither_method,
    )
    return quantized.convert("RGB")


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

    # 1. 下采样到目标尺寸
    down = _downsample(img, eff.output_size)
    # 2. 轻微增强
    down = _apply_enhancements(down, eff.saturation, eff.edge_enhance)
    # 3. 语义区域最近邻替换（可选，早期做可以引导后续量化）
    if analysis and analysis.semantic_regions:
        down = apply_semantic_regions(down, analysis.semantic_regions)
    # 4. 构建调色板
    palette_rgb = _build_palette(down, eff, preset, analysis)
    # 5. 量化 + 抖动
    pixelized = _quantize(down, palette_rgb, eff.dither)

    # 6. 可选预览（最近邻放大）
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
        },
        "palette": ["#{:02X}{:02X}{:02X}".format(*c) for c in palette_rgb],
        "palette_size": len(palette_rgb),
        "used_analysis": analysis is not None,
    }
    return pixelized, preview, meta
