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
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.pixelize.presets import Preset, load_preset
from pix.pixelize.ramp import (
    RampPalette,
    RampValidationError,
    build_local_ramp,
    quantize_to_ramp,
    ramp_from_vl,
    ramp_to_meta,
)


Dither = Literal["none", "ordered", "floyd_steinberg"]
ResampleMode = Literal["smart", "box", "bicubic", "lanczos", "nearest"]
EdgeStyle = Literal["hard", "feather", "outline"]
PaletteMode = Literal["auto", "ramp", "kmeans"]
GeneratedPreprocessMode = Literal["legacy", "none", "perfect_pixel"]
LOW_PIXEL_OUTLINE_MAX_AXIS = 32


def _bg_removal_options(cfg) -> dict:
    asset = getattr(cfg, "asset", None)
    if asset is None:
        return {}
    return {
        "bg_removal_algorithm": getattr(asset, "bg_removal_algorithm", "auto"),
        "color_to_alpha_shape": getattr(asset, "color_to_alpha_shape", "sphere"),
        "color_to_alpha_transparency": getattr(asset, "color_to_alpha_transparency", 48),
        "color_to_alpha_opacity": getattr(asset, "color_to_alpha_opacity", 255),
        "color_to_alpha_interpolation": getattr(asset, "color_to_alpha_interpolation", "linear"),
    }


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
    edge_style: EdgeStyle = "hard"
    auto_crop: bool = False
    crop_padding: float = 0.12
    crop_square: bool = True
    palette_mode: PaletteMode = "auto"
    # 仅当 pipeline 标记输入来自 AI 生图/图生图时使用；本地 pixelize 默认仍走旧流程。
    generated_preprocess_method: GeneratedPreprocessMode = "perfect_pixel"

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
            edge_style=getattr(cfg, "edge_style", "hard"),
            auto_crop=getattr(cfg, "auto_crop", False),
            crop_padding=getattr(cfg, "crop_padding", 0.12),
            crop_square=getattr(cfg, "crop_square", True),
            palette_mode=getattr(cfg, "palette_mode", "auto"),  # type: ignore[arg-type]
            generated_preprocess_method=getattr(cfg, "generated_preprocess_method", "perfect_pixel"),  # type: ignore[arg-type]
        )


def _resolve_preset(params: PixelizeParams, analysis: PixAnalysis | None) -> Preset | None:
    """解析预设。

    只有用户明确选择的预设才会覆盖尺寸、色数等参数；VL 的 recommended_preset
    仅作为分析信息保留，不再自动改写网站表单中的用户选择。
    """
    if params.preset and params.preset != "auto":
        return load_preset(params.preset)
    return None


def _effective_params(
    params: PixelizeParams, preset: Preset | None, analysis: PixAnalysis | None
) -> PixelizeParams:
    """将用户传入 params 与预设、analysis 合并；用户显式值优先，但我们只在"值等于默认"时才用预设兜底。

    简化策略：这里由调用方保证 params 已经是 "用户覆盖 ∪ 默认值" 后的结果，
    我们只在 preset 存在且 params 的对应字段还是 **配置默认值** 的情况下填充；
    这通过引入 "sentinel" 来做不实用。
    实际策略：preset 只在 params.preset 明确指定或 analysis 推荐时启用；
    启用后，preset 字段如果为非 None 就生效，调用方仍可覆盖具体字段。
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
        resample=params.resample,
        snap_to_grid=params.snap_to_grid,
        remove_bg=params.remove_bg,
        bg_tolerance=params.bg_tolerance,
        bg_feather=params.bg_feather,
        edge_style=params.edge_style,
        auto_crop=params.auto_crop,
        crop_padding=params.crop_padding,
        crop_square=params.crop_square,
        palette_mode=params.palette_mode,
        generated_preprocess_method=params.generated_preprocess_method,
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

    return eff


def _has_transparent_alpha(image: Image.Image) -> bool:
    if "A" not in image.getbands():
        return False
    alpha = image.getchannel("A")
    extrema = alpha.getextrema()
    return bool(extrema and extrema[0] < 255)


def _transparency_ratio(image: Image.Image) -> float:
    """返回 image 中完全透明（alpha=0）像素占比；用于判断源图是否已经抠好背景。"""
    if "A" not in image.getbands():
        return 0.0
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    if not histogram:
        return 0.0
    total = max(1, sum(histogram))
    return histogram[0] / total


def _apply_low_pixel_edge_policy(params: PixelizeParams, *, has_transparency: bool) -> dict:
    """记录低像素透明素材的边缘策略，但不覆盖用户选择。"""
    width, height = params.output_size
    low_pixel = max(int(width), int(height)) <= LOW_PIXEL_OUTLINE_MAX_AXIS
    needs_transparent_edge_policy = bool(params.remove_bg or has_transparency)
    if not low_pixel or not needs_transparent_edge_policy:
        return {"applied": False, "reason": "not_low_pixel_or_no_transparency"}
    selected = {"edge_style": params.edge_style, "bg_feather": params.bg_feather}
    return {
        "applied": False,
        "reason": "user_edge_style_respected",
        "max_axis": LOW_PIXEL_OUTLINE_MAX_AXIS,
        "source_alpha": bool(has_transparency),
        "background_removal": bool(params.remove_bg),
        "selected": selected,
    }


def _image_mode_for_pixelize(source: Image.Image) -> Image.Image:
    """转换为像素化工作模式，尽量保留输入透明通道。"""
    has_alpha = "A" in source.getbands() or "transparency" in source.info
    return source.convert("RGBA" if has_alpha else "RGB")


def _alpha_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    """返回 alpha 中非透明主体 bbox；坐标为 Pillow crop 的右开区间。"""
    if "A" not in image.getbands():
        return None
    alpha = image.getchannel("A")
    if threshold <= 0:
        return alpha.getbbox()
    mask = alpha.point(lambda v: 255 if v > threshold else 0)
    return mask.getbbox()


def _foreground_bbox(image: Image.Image, bg_tolerance: int) -> tuple[int, int, int, int] | None:
    """优先用 alpha；否则临时四角抠背景来估计主体 bbox。"""
    bbox = _alpha_bbox(image)
    if bbox is not None:
        return bbox
    probe = remove_background(
        image,
        tolerance=max(0, int(bg_tolerance)),
        feather=0,
        keep_border_bleed=True,
    )
    return _alpha_bbox(probe)


def _expand_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
    *,
    padding: float,
    square: bool,
) -> tuple[int, int, int, int]:
    """外扩 bbox，并可保持正方形，最终裁剪范围限制在图片内。"""
    w, h = image_size
    left, top, right, bottom = bbox
    bw = max(1, right - left)
    bh = max(1, bottom - top)
    pad = max(0.0, float(padding))
    left -= int(round(bw * pad))
    right += int(round(bw * pad))
    top -= int(round(bh * pad))
    bottom += int(round(bh * pad))

    if square:
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        side = max(right - left, bottom - top)
        left = int(round(cx - side / 2))
        right = left + side
        top = int(round(cy - side / 2))
        bottom = top + side

    crop_w = right - left
    crop_h = bottom - top
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > w:
        left -= right - w
        right = w
    if bottom > h:
        top -= bottom - h
        bottom = h

    left = max(0, left)
    top = max(0, top)
    right = min(w, max(left + 1, right))
    bottom = min(h, max(top + 1, bottom))

    # 如果贴边修正导致尺寸塌缩，至少尽量保留原扩展尺寸范围。
    if square:
        side = min(max(crop_w, crop_h), w, h)
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        left = int(round(cx - side / 2))
        top = int(round(cy - side / 2))
        left = max(0, min(left, w - side))
        top = max(0, min(top, h - side))
        right = left + side
        bottom = top + side

    return int(left), int(top), int(right), int(bottom)


def _auto_crop(
    image: Image.Image,
    *,
    bg_tolerance: int,
    padding: float,
    square: bool,
    tight: bool = False,
) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    """按透明通道或四角背景估计主体并裁剪。

    tight=True 时直接使用主体 bbox，不加 padding、不强制正方形；用于 perfectPixel
    之后的低分辨率网格，避免 03_auto_crop 继续保留多余背景格。
    """
    bbox = _foreground_bbox(image, bg_tolerance)
    if bbox is None:
        return image, None
    w, h = image.size
    left, top, right, bottom = bbox
    # 全图都被视作前景时不要裁，避免误伤背景复杂的输入。
    if left <= 0 and top <= 0 and right >= w and bottom >= h:
        return image, None
    if tight:
        return image.crop(bbox), bbox
    expanded = _expand_bbox(bbox, image.size, padding=padding, square=square)
    return image.crop(expanded), expanded


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
    """按原始比例适配到目标尺寸。

    输出画布始终是 ``size``，内容按原始宽高比缩放后居中放置，避免非等比目标尺寸
    把主体横向或纵向拉伸。RGBA 输入会用透明像素补边；RGB 输入用边角主色补边。

    - smart: 如果探测到输入有明显像素网格，先按网格 BOX 聚合，再 BOX 缩到目标
      否则退化到面积采样，比纯 bicubic 边缘锐一些
    - box: 纯平均采样（对像素画最忠实）
    - bicubic: Pillow 经典平滑缩
    - lanczos: 最锐利的插值，容易有 ringing
    - nearest: 硬采样，保留像素感但会丢细节
    """
    target = size
    content_size, offset = _aspect_fit_geometry(image.size, target)
    resized = _resize_exact(image, content_size, mode=mode, snap=snap)
    if resized.size == target:
        return resized
    canvas = Image.new(resized.mode, target, _letterbox_fill(image))
    canvas.paste(resized, offset)
    return canvas


def _resize_exact(
    image: Image.Image,
    size: tuple[int, int],
    *,
    mode: ResampleMode,
    snap: bool,
) -> Image.Image:
    """缩放到指定尺寸；调用方保证该尺寸已经保持原始比例。"""
    mode_map = {
        "box": Image.Resampling.BOX,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
        "nearest": Image.Resampling.NEAREST,
    }

    if mode != "smart":
        return image.resize(size, mode_map.get(mode, Image.Resampling.BICUBIC))

    w, h = image.size
    tw, th = size

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
        return image.resize(size, Image.Resampling.NEAREST)

    # 还比目标大：用 BOX 做面积平均（对硬边友好，不会糊）
    return image.resize(size, Image.Resampling.BOX)


def _aspect_fit_geometry(
    source_size: tuple[int, int],
    target_size: tuple[int, int],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """返回保持比例后的内容尺寸和居中偏移。"""
    sw, sh = max(1, source_size[0]), max(1, source_size[1])
    tw, th = max(1, target_size[0]), max(1, target_size[1])
    scale = min(tw / sw, th / sh)
    cw = max(1, min(tw, int(round(sw * scale))))
    ch = max(1, min(th, int(round(sh * scale))))
    return (cw, ch), ((tw - cw) // 2, (th - ch) // 2)


def _letterbox_fill(image: Image.Image):
    """为保持比例产生的补边选择填充色。"""
    if "A" in image.getbands():
        return (0, 0, 0, 0)
    arr = np.asarray(image.convert("RGB"), dtype=np.uint8)
    if arr.size == 0:
        return (0, 0, 0)
    h, w, _ = arr.shape
    corners = np.asarray([arr[0, 0], arr[0, w - 1], arr[h - 1, 0], arr[h - 1, w - 1]])
    rgb = np.median(corners, axis=0).astype(np.uint8)
    return tuple(int(v) for v in rgb)


def _apply_enhancements(image: Image.Image, saturation: float, edge: float) -> Image.Image:
    img = image
    if abs(saturation - 1.0) > 1e-3:
        img = ImageEnhance.Color(img).enhance(saturation)
    if edge > 1e-3:
        # Pillow 的 EDGE_ENHANCE 是滤镜，强度不可调；用 UnsharpMask 近似
        img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=int(edge * 150), threshold=2))
    return img


def _dilate_mask_4(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def _outline_rgb_from_foreground(rgba: np.ndarray, foreground: np.ndarray) -> tuple[int, int, int]:
    pixels = rgba[foreground, :3]
    if pixels.size == 0:
        return (16, 16, 16)
    luma = pixels[:, 0].astype(np.float32) * 0.2126 + pixels[:, 1].astype(np.float32) * 0.7152 + pixels[:, 2].astype(np.float32) * 0.0722
    darkest = pixels[int(np.argmin(luma))]
    if float(luma.min()) < 72:
        return tuple(int(v) for v in darkest)
    return tuple(max(0, int(v * 0.36)) for v in darkest)


def _apply_low_pixel_alpha_outline(image: Image.Image, *, strength: int) -> Image.Image:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    rgba = np.asarray(image).copy()
    alpha = rgba[..., 3]
    foreground = alpha >= 96
    if not foreground.any() or foreground.all():
        rgba[..., 3] = np.where(foreground, 255, 0).astype(np.uint8)
        return Image.fromarray(rgba, mode="RGBA")
    outline_rgb = _outline_rgb_from_foreground(rgba, foreground)
    rgba[..., 3] = np.where(foreground, 255, 0).astype(np.uint8)
    outline_mask = np.zeros(foreground.shape, dtype=bool)
    current = foreground.copy()
    for _ in range(max(1, int(strength))):
        expanded = _dilate_mask_4(current)
        layer = expanded & ~foreground & ~outline_mask
        if layer.shape[0] > 2 and layer.shape[1] > 2:
            layer[0, :] = False
            layer[-1, :] = False
            layer[:, 0] = False
            layer[:, -1] = False
        outline_mask |= layer
        current = current | layer
    rgba[outline_mask, :3] = outline_rgb
    rgba[outline_mask, 3] = 255
    return Image.fromarray(rgba, mode="RGBA")


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


def _resolve_ramp_palette(
    image: Image.Image,
    params: PixelizeParams,
    analysis: PixAnalysis | None,
    *,
    cfg=None,  # AppConfig，避免此处循环引入
    image_path=None,
    description: str = "",
) -> tuple[RampPalette, dict]:
    """尝试获取 Ramp 调色板。先 VL，再本地兜底。

    Returns:
        (ramp_palette, ramp_meta_extra)
        ramp_meta_extra 里含 source / 错误信息 / 用了哪些底色提示。
    """
    info: dict = {"source": "local", "vl_error": None, "requested": params.palette_mode}
    draft_hex = [
        "#{:02X}{:02X}{:02X}".format(*rgb) for rgb in kmeans_palette(image, max(4, min(8, params.colors)))
    ]
    info["draft_palette"] = draft_hex
    if description:
        info["description"] = description

    want_vl = params.palette_mode in ("ramp",) and cfg is not None and image_path is not None
    if want_vl:
        try:
            ramp = ramp_from_vl(
                cfg,
                image_path,
                max_colors=max(3, params.colors),
                output_size=params.output_size,
                description=description,
                draft_palette_hex=draft_hex,
            )
            info["source"] = "vl"
            return ramp, info
        except (RampValidationError, Exception) as exc:  # noqa: BLE001 - 兜底到本地 ramp
            info["vl_error"] = str(exc)
            info["source"] = "local_fallback"

    ramp = build_local_ramp(image, max_colors=max(3, params.colors))
    info.setdefault("source", "local")
    return ramp, info


def pixelize(
    source: Image.Image | str | Path,
    params: PixelizeParams,
    analysis: PixAnalysis | None = None,
    *,
    cfg=None,
    source_description: str = "",
    auto_skip_redundant_bg: bool = False,
    generated_preprocess_method: str | None = None,
    preprocess_output_path: str | Path | None = None,
) -> tuple[Image.Image, Image.Image | None, dict]:
    """执行像素化。

    Args:
        source: 输入图片路径或 PIL Image。
        params: 像素化参数，`palette_mode` 控制走 kmeans 还是 ramp。
        analysis: 可选的 VL 分析 JSON。
        cfg: 若使用 VL ramp，需要传入 AppConfig（否则自动回退到本地 ramp）。
        source_description: 用户原始语义描述，辅助 VL ramp 判断题材。
        auto_skip_redundant_bg: 当源图本身已经是透明素材（alpha=0 占比 ≥10%）时，
            自动跳过 ``params.remove_bg`` / ``params.auto_crop``。仅在调用方知道
            源图是已抠图（如 pipeline 候选选出来的 01_source.png）时启用，
            避免重复抠图把主体压扁。直接用 ``pixelize()`` 处理任意图片时保持 False
            以保留原行为。
        generated_preprocess_method: 仅 pipeline 标记输入来自 AI 生图/图生图时传入。
            ``None`` 表示本地/直接调用，保持旧流程；``perfect_pixel`` 会先按目标网格
            做 perfectPixel 风格采样对齐。
        preprocess_output_path: 需要调试/追踪时保存 perfect pixel 预处理图。

    Returns:
        (pixel_image, preview_image_or_None, meta_dict)
    """
    source_path: Path | None = None
    if not isinstance(source, Image.Image):
        source_path = Path(source)
        source = Image.open(source_path)
    img = _image_mode_for_pixelize(source)
    input_has_transparency = _has_transparent_alpha(img)
    pre_transparency_ratio = _transparency_ratio(img)

    preset = _resolve_preset(params, analysis)
    eff = _effective_params(params, preset, analysis)
    edge_policy = _apply_low_pixel_edge_policy(eff, has_transparency=input_has_transparency)

    # 源图本身已经抠好背景（alpha=0 占比超过阈值）时，自动跳过 remove_bg / auto_crop，
    # 避免对已抠图重复抠图导致主体被误压缩。仅在调用方传入 auto_skip_redundant_bg=True
    # 时启用；普通 pixelize 调用方默认不开，保留显式 remove_bg / auto_crop 的语义。
    skipped_remove_bg = (
        auto_skip_redundant_bg
        and pre_transparency_ratio >= 0.10
        and bool(eff.remove_bg)
    )
    skipped_auto_crop = (
        auto_skip_redundant_bg
        and pre_transparency_ratio >= 0.10
        and bool(eff.auto_crop)
    )

    # 1. AI 生成结果首先走 perfectPixel 网格对齐；本地直接 pixelize 默认不启用。
    generated_method = generated_preprocess_method if generated_preprocess_method is not None else "legacy"
    generated_preprocess = preprocess_generated_image(
        img,
        method=generated_method,
        target_size=eff.output_size,
    )
    img = generated_preprocess.image
    generated_preprocess_meta = generated_preprocess.meta
    if preprocess_output_path is not None and generated_preprocess_meta.get("method") == "perfect_pixel":
        preprocess_path = Path(preprocess_output_path)
        preprocess_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(preprocess_path)
        generated_preprocess_meta["output_path"] = str(preprocess_path)

    # 2. 可选前置抠背景：处理模型画出来的纯色/棋盘格假透明背景。
    if eff.remove_bg and not skipped_remove_bg:
        img = remove_background(
            img,
            tolerance=max(0, int(eff.bg_tolerance)),
            feather=0,
            keep_border_bleed=True,
            **_bg_removal_options(cfg),
        )

    # 3. 可选主体裁剪：在 perfectPixel 对齐后的像素网格上贴边裁剪主体。
    crop_bbox: tuple[int, int, int, int] | None = None
    tight_crop = bool(generated_preprocess_meta.get("applied"))
    if eff.auto_crop and not skipped_auto_crop:
        img, crop_bbox = _auto_crop(
            img,
            bg_tolerance=eff.bg_tolerance,
            padding=0.0 if tight_crop else eff.crop_padding,
            square=False if tight_crop else eff.crop_square,
            tight=tight_crop,
        )

    # 4. 下采样到目标尺寸（smart/box/bicubic/lanczos/nearest）
    detected_grid: int | None = None
    if eff.resample == "smart" and eff.snap_to_grid:
        detected_grid = _detect_grid_size(img)
    aspect_content_size, aspect_offset = _aspect_fit_geometry(img.size, eff.output_size)
    down = _downsample(img, eff.output_size, mode=eff.resample, snap=eff.snap_to_grid)
    # 2. 轻微增强
    down = _apply_enhancements(down, eff.saturation, eff.edge_enhance)

    # 3. 构建调色板。
    #   palette_mode=ramp: VL（或本地兜底）给 Ramp → Lab 最近色量化
    #   palette_mode=kmeans / auto: 保留原 K-means 路径
    #   auto：默认走 kmeans，后续可改为按尺寸自动启用 ramp（M4 做）
    ramp_palette: RampPalette | None = None
    ramp_info: dict | None = None
    use_ramp = eff.palette_mode == "ramp"
    if use_ramp:
        ramp_palette, ramp_info = _resolve_ramp_palette(
            down,
            eff,
            analysis,
            cfg=cfg,
            image_path=source_path,
            description=source_description,
        )
        palette_rgb = ramp_palette.rgb_list
    else:
        palette_rgb = _build_palette(down, eff, preset, analysis)

    # 5. 量化 + 抖动
    if ramp_palette is not None:
        dither_mode = "floyd_steinberg" if eff.dither == "floyd_steinberg" else "none"
        pixelized = quantize_to_ramp(down, ramp_palette, dither=dither_mode)
    else:
        pixelized = _quantize(down, palette_rgb, eff.dither)

    # 6. 可选：抠背景（在量化后做最准——背景块已经是纯色）
    if eff.remove_bg:
        pixelized = remove_background(
            pixelized,
            tolerance=max(0, int(eff.bg_tolerance)),
            feather=max(0, int(eff.bg_feather)),
            edge_style=eff.edge_style,
            **_bg_removal_options(cfg),
        )
    elif edge_policy.get("source_alpha") and eff.edge_style == "outline":
        pixelized = _apply_low_pixel_alpha_outline(pixelized, strength=max(1, int(eff.bg_feather)))

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
            "edge_style": eff.edge_style,
            "auto_crop": eff.auto_crop,
            "crop_padding": eff.crop_padding,
            "crop_square": eff.crop_square,
            "palette_mode": eff.palette_mode,
            "generated_preprocess_method": eff.generated_preprocess_method,
        },
        "palette": ["#{:02X}{:02X}{:02X}".format(*c) for c in palette_rgb],
        "palette_size": len(palette_rgb),
        "used_analysis": analysis is not None,
        "edge_policy": edge_policy,
        "input_transparency_ratio": round(pre_transparency_ratio, 4),
        "generated_preprocess": generated_preprocess_meta,
        "preprocess_order": ["perfect_pixel", "remove_background", "auto_crop"],
        "auto_crop_policy": "tight_after_perfect_pixel" if tight_crop else "configured_padding",
        "skipped_remove_bg": skipped_remove_bg,
        "skipped_auto_crop": skipped_auto_crop,
        "detected_grid": detected_grid,
        "crop_bbox": list(crop_bbox) if crop_bbox else None,
        "aspect_fit": {
            "source_size": list(img.size),
            "content_size": list(aspect_content_size),
            "offset": list(aspect_offset),
        },
    }
    if ramp_palette is not None:
        meta["ramp"] = ramp_to_meta(ramp_palette)
        meta["ramp_info"] = ramp_info
    return pixelized, preview, meta
