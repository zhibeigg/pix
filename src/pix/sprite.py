"""逐帧序列帧生成流水线。"""

from __future__ import annotations

import json
import math
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterable

import numpy as np
from PIL import Image

from pix import __version__
from pix.api.image_gen import edit_image, generate_image
from pix.api.prompt_guard import PromptPolicyError, validate_user_prompt
from pix.cache import Cache
from pix.config import AppConfig
from pix.contact_sheet import resolve_key_color
from pix.io_utils import new_run_dir, sha256_of_file
from pix.pixelize.bg_removal import remove_background, remove_translucent_edge_halo
from pix.pixelize.core import PixelizeParams
from pix.pixelize.palette import build_palette_image, kmeans_palette, rgb_to_hex
from pix.pixelize.perfect_pixel import preprocess_generated_image


LocalStageContext = Callable[[], ContextManager[None]]
ProgressCb = Any


@dataclass(frozen=True)
class SpriteFrame:
    """单帧输出信息。"""

    index: int
    raw_path: Path
    reference_path: Path
    path: Path
    sheet_rect: dict[str, int]
    action_phase: str
    bbox: tuple[int, int, int, int] | None = None

    @property
    def row(self) -> int:
        return 0

    @property
    def col(self) -> int:
        return self.index - 1

    def to_metadata(self, run_dir: Path) -> dict[str, Any]:
        return {
            "index": self.index,
            "row": self.row,
            "col": self.col,
            "raw_path": _rel(self.raw_path, run_dir),
            "reference_path": _rel(self.reference_path, run_dir),
            "path": _rel(self.path, run_dir),
            "sheet_rect": dict(self.sheet_rect),
            "action_phase": self.action_phase,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class SpritePipelineInput:
    prompt: str
    image_size: str | None = None
    image_quality: str | None = None
    image_model: str | None = None
    pixelize_params: PixelizeParams = field(default_factory=PixelizeParams)
    out_root: str | Path | None = None
    use_cache: bool = True
    refresh_cache: bool = False
    duration_ms: int | None = None
    loop: int | None = None
    rows: int | None = None
    cols: int | None = None
    frame_count: int | None = None
    fps: int | None = None
    gif_export: bool | None = None
    key_mode: str | None = None
    key_tolerance: int | None = None
    key_softness: int | None = None
    key_alpha_floor: int | None = None
    key_despill: bool | None = None
    billing: dict[str, Any] | None = None
    local_stage_context: LocalStageContext | None = None


@dataclass
class SpritePipelineResult:
    run_dir: Path
    source_path: Path
    frame_paths: list[Path]
    pixel_path: Path
    preview_path: Path | None
    meta_path: Path
    meta: dict[str, Any]
    analysis_path: Path | None = None

    @property
    def gif_path(self) -> Path | None:
        return self.preview_path


@dataclass(frozen=True)
class _FrameDraft:
    index: int
    raw_path: Path
    reference_path: Path
    content: Image.Image
    bbox: tuple[int, int, int, int] | None
    action_phase: str
    effective_prompt: str
    generation_mode: str
    attempts: int
    preprocess_meta: dict[str, Any]
    postprocess_meta: dict[str, Any]


@dataclass(frozen=True)
class _SequenceSettings:
    frame_count: int
    fps: int
    duration_ms: int
    loop: int
    target_size: tuple[int, int]
    frame_size_step: int
    oversize_regenerate_threshold: float
    max_frame_retries: int
    gif_export: bool
    anchor: str
    key_color: str
    key_tolerance: int
    max_colors: int
    reference_policy_requested: str
    reference_policy_effective: str
    reference_policy_fallback_reason: str


def _noop(_step: str, _payload: dict) -> None:
    pass


def _local_stage(factory: LocalStageContext | None) -> ContextManager[None]:
    return factory() if factory is not None else nullcontext()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _size_tuple(value: tuple[int, int] | list[int] | None, fallback: tuple[int, int]) -> tuple[int, int]:
    if not value:
        return fallback
    try:
        return max(1, int(value[0])), max(1, int(value[1]))
    except (TypeError, ValueError, IndexError):
        return fallback


def _ceil_to_multiple(value: int, divisor: int) -> int:
    safe_divisor = max(1, int(divisor))
    safe_value = max(1, int(value))
    return ((safe_value + safe_divisor - 1) // safe_divisor) * safe_divisor


def _normalized_key_mode(value: str | None) -> str:
    mode = (value or "hard").strip().lower()
    if mode not in {"hard", "soft"}:
        raise ValueError("key_mode 必须是 hard 或 soft")
    return mode


def _visible_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = np.asarray(image.convert("RGBA"))[..., 3]
    visible = alpha > threshold
    if not visible.any():
        return None
    ys, xs = np.where(visible)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _compose_mosaic(frames: list[Image.Image]) -> Image.Image:
    if not frames:
        raise ValueError("没有可用于合成的帧")
    width = sum(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for frame in frames:
        sheet.alpha_composite(frame.convert("RGBA"), (x, (height - frame.height) // 2))
        x += frame.width
    return sheet


def _quantize_with_palette(
    image: Image.Image,
    palette_rgb: list[tuple[int, int, int]],
    *,
    dither: str,
) -> Image.Image:
    pal_img = build_palette_image(palette_rgb)
    dither_method = Image.Dither.FLOYDSTEINBERG if dither == "floyd_steinberg" else Image.Dither.NONE
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    quantized = rgba.convert("RGB").quantize(palette=pal_img, dither=dither_method)
    out = quantized.convert("RGBA")
    out.putalpha(alpha)
    return out


def _apply_shared_palette(images: list[Image.Image], *, colors: int, dither: str) -> tuple[list[Image.Image], list[str]]:
    if not images:
        return [], []
    mosaic = _compose_mosaic(images)
    palette = kmeans_palette(mosaic, max(2, min(256, int(colors))))
    return [_quantize_with_palette(img, palette, dither=dither) for img in images], [rgb_to_hex(rgb) for rgb in palette]


def compose_horizontal_sprite_sheet(frame_paths: list[Path], out_path: str | Path) -> Path:
    frames = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    sheet = _compose_mosaic(frames)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def compose_gif(frame_paths: list[Path], out_path: str | Path, *, duration_ms: int, loop: int = 0) -> Path:
    frames: list[Image.Image] = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    if not frames:
        raise ValueError("没有可用于合成 GIF 的帧")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    first, rest = frames[0], frames[1:]
    first.save(
        target,
        save_all=True,
        append_images=rest,
        duration=max(20, int(duration_ms)),
        loop=max(0, int(loop)),
        disposal=2,
    )
    return target


def _sprite_bg_removal_options(cfg: AppConfig | None, *, tolerance: int) -> dict[str, Any]:
    asset = getattr(cfg, "asset", None)
    if asset is None:
        return {
            "bg_removal_algorithm": "color_to_alpha",
            "color_to_alpha_transparency": max(0, int(tolerance)),
        }
    return {
        "bg_removal_algorithm": "color_to_alpha",
        "color_to_alpha_shape": getattr(asset, "color_to_alpha_shape", "sphere"),
        "color_to_alpha_transparency": max(0, int(tolerance)),
        "color_to_alpha_opacity": getattr(asset, "color_to_alpha_opacity", 255),
        "color_to_alpha_interpolation": getattr(asset, "color_to_alpha_interpolation", "linear"),
    }


def _target_frame_bounds(frame_count: int, width: int, height: int) -> list[dict[str, int]]:
    return [
        {"index": index, "x": (index - 1) * width, "y": 0, "w": width, "h": height}
        for index in range(1, frame_count + 1)
    ]


def _format_frame_bounds(bounds: Iterable[dict[str, int]]) -> str:
    return "; ".join(
        f"frame_{item['index']:03d}=x:{item['x']}, y:{item['y']}, w:{item['w']}, h:{item['h']}"
        for item in bounds
    )


def build_action_timeline(description: str, frame_count: int) -> list[str]:
    """根据整体动作描述生成轻量、可复现、可闭环的内部动作时间线。"""

    count = max(1, int(frame_count))
    if count == 1:
        return [f"单帧展示：完整呈现动作主体与关键姿势。动作描述：{description}"]
    phase_bank = [
        "闭环起始锚点：主体处于清晰待机/接触姿势，记录基准高度、锚点、朝向和轮廓，供最后一帧回接",
        "预备动作：主体轻微压缩或蓄力，锚点仍贴近起始位置，不改变身份和朝向",
        "离开起始：动作开始展开，主体向动作方向推进，但仍保留与第 1 帧一致的比例和轮廓语言",
        "中段推进：动作幅度继续增加，运动轨迹清楚，锚点变化平滑",
        "动作峰值：跳跃/挥动/释放达到最高或最远位置，是视觉重点最强的一帧",
        "回落/跟随：动作从峰值回收，拖尾或余势开始向起始锚点靠近",
        "落地/回收：主体接近起始高度和位置，可有轻微压缩或余波，但身份、比例和朝向不变",
        "闭环前一拍：几乎回到第 1 帧的锚点、高度、比例和轮廓，只保留极小余势，下一帧切回第 1 帧不能明显跳变",
    ]
    timeline: list[str] = []
    for index in range(1, count + 1):
        bank_index = round((index - 1) * (len(phase_bank) - 1) / max(1, count - 1))
        phase = phase_bank[max(0, min(len(phase_bank) - 1, bank_index))]
        timeline.append(f"第 {index}/{count} 帧：{phase}。动作描述：{description}")
    return timeline


def _reference_instruction(frame_index: int, frame_count: int) -> str:
    if frame_count > 2 and frame_index == frame_count:
        return (
            "The provided reference image is frame 1, the loop anchor. Use it to close the loop: keep this last frame very close to frame 1's anchor, scale, facing direction, ground/contact height, and silhouette, "
            "with only a tiny residual motion before returning to frame 1."
        )
    return "The provided reference image is the previous frame. Advance the motion smoothly while preserving identity, scale, facing direction, and anchor."


def _loop_closure_instruction(frame_index: int, frame_count: int) -> str:
    if frame_count <= 1:
        return ""
    if frame_index == 1:
        return (
            "Closed-loop contract: this first frame is the loop anchor. Make the pose readable and reusable as the frame that immediately follows the last frame. "
            "Keep the anchor, scale, facing direction, and silhouette easy to return to."
        )
    if frame_index == frame_count:
        return (
            "Closed-loop contract: this is the frame immediately before frame 1. It must return very close to frame 1's anchor, ground/contact height, scale, facing direction, and silhouette; "
            "do not end on a new pose, new location, or different size. Keep only a tiny amount of residual motion so the next displayed frame 1 feels seamless."
        )
    if frame_index == frame_count - 1:
        return (
            "Closed-loop contract: begin returning toward frame 1 now. Reduce motion amplitude and bring the anchor/ground contact back toward the starting pose so the final frame can close the loop."
        )
    return "Closed-loop contract: preserve the same anchor, scale, facing direction, and identity so all frames can loop back into frame 1 smoothly."


def build_sprite_sheet_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int] | None = None,
    rows: int | None = None,
    cols: int | None = None,
    max_colors: int | None = None,
    key_tolerance: int | None = None,
) -> str:
    """兼容旧调用名：构造序列帧第一帧 prompt。"""

    sprite_cfg = cfg.sprite
    frame_count = max(1, int((rows or sprite_cfg.frame_count) * (cols or 1))) if rows and cols else int(sprite_cfg.frame_count)
    frame_count = max(1, min(int(sprite_cfg.max_frame_count), frame_count))
    width, height = target_size or sprite_cfg.pixel_size
    key_hex, _key_rgb = resolve_key_color(sprite_cfg.green_screen_color, description)
    timeline = build_action_timeline(description, frame_count)
    return build_sequence_first_frame_prompt(
        cfg,
        description,
        target_size=(int(width), int(height)),
        frame_count=frame_count,
        action_phase=timeline[0],
        key_color=key_hex,
        key_tolerance=int(sprite_cfg.green_screen_tolerance if key_tolerance is None else key_tolerance),
        max_colors=int(sprite_cfg.colors if max_colors is None else max_colors),
        anchor=sprite_cfg.anchor,
    )


def build_sequence_first_frame_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int],
    frame_count: int,
    action_phase: str,
    key_color: str,
    key_tolerance: int,
    max_colors: int,
    anchor: str,
) -> str:
    width, height = target_size
    values = {
        "description": description.strip(),
        "normalized_description": description.strip(),
        "frame_index": 1,
        "frame_count": int(frame_count),
        "action_phase": action_phase,
        "width": int(width),
        "height": int(height),
        "target_frame_width": int(width),
        "target_frame_height": int(height),
        "green": key_color,
        "key_color": key_color,
        "key_tolerance": int(key_tolerance),
        "max_colors": int(max_colors),
        "colors": int(max_colors),
        "anchor": anchor,
        "loop_closure": _loop_closure_instruction(1, int(frame_count)),
    }
    template = (getattr(cfg.sprite, "prompt_template", "") or "").strip()
    if template:
        try:
            formatted = template.format(**values).strip()
            if values["loop_closure"] and "{loop_closure}" not in template:
                formatted = f"{formatted} {values['loop_closure']}".strip()
            return formatted
        except Exception:
            pass
    return _fallback_first_frame_prompt(**values)


def build_sequence_next_frame_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int],
    frame_index: int,
    frame_count: int,
    action_phase: str,
    previous_action_phase: str,
    key_color: str,
    key_tolerance: int,
    max_colors: int,
    anchor: str,
    retry_hint: str = "",
) -> str:
    width, height = target_size
    values = {
        "description": description.strip(),
        "normalized_description": description.strip(),
        "frame_index": int(frame_index),
        "frame_count": int(frame_count),
        "action_phase": action_phase,
        "previous_action_phase": previous_action_phase,
        "motion_delta_description": f"Advance smoothly from: {previous_action_phase}",
        "reference_instruction": _reference_instruction(int(frame_index), int(frame_count)),
        "width": int(width),
        "height": int(height),
        "target_frame_width": int(width),
        "target_frame_height": int(height),
        "green": key_color,
        "key_color": key_color,
        "key_tolerance": int(key_tolerance),
        "max_colors": int(max_colors),
        "colors": int(max_colors),
        "anchor": anchor,
        "loop_closure": _loop_closure_instruction(int(frame_index), int(frame_count)),
        "retry_hint": retry_hint.strip(),
    }
    template = (getattr(cfg.sprite, "next_frame_prompt_template", "") or "").strip()
    if template:
        try:
            formatted = template.format(**values).strip()
            if values["reference_instruction"] and "{reference_instruction}" not in template:
                formatted = f"{formatted} {values['reference_instruction']}".strip()
            if values["loop_closure"] and "{loop_closure}" not in template:
                formatted = f"{formatted} {values['loop_closure']}".strip()
            return formatted
        except Exception:
            pass
    return _fallback_next_frame_prompt(**values)


def _fallback_first_frame_prompt(**values: Any) -> str:
    return (
        f"Create frame 1 of a {values['frame_count']}-frame TRUE pixel-art animation sequence. "
        f"Subject/action: {values['description']}. "
        f"Action phase: {values['action_phase']}. "
        f"Canvas contract: one single frame only, target frame size {values['width']}x{values['height']} logical pixels, "
        "where each pixel is one square grid cell. The character/effect should fit inside this frame whenever possible. "
        f"Use no more than {values['max_colors']} visible subject/effect colors; background color does not count. "
        f"Use pure solid key-color {values['green']} for all empty/background pixels for chroma-key removal; "
        f"keep visible colors outside the maximum key-color tolerance ({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        f"Anchor: keep the subject aligned to {values['anchor']}. "
        f"{values['loop_closure']} "
        "Style: crisp pixel art, hard edges, limited palette, no painterly blending, no anti-aliased soft brush. "
        "Do not draw a sprite sheet, do not draw multiple frames, do not add text, watermark, UI, border, grid, labels, or shadows outside the sprite."
    )


def _fallback_next_frame_prompt(**values: Any) -> str:
    loop_closure = f" {values['loop_closure']}" if values.get("loop_closure") else ""
    retry_hint = f" {values['retry_hint']}" if values.get("retry_hint") else ""
    return (
        f"Generate frame {values['frame_index']} of {values['frame_count']} in the same TRUE pixel-art animation sequence. "
        f"{values['reference_instruction']} "
        f"Subject/action identity to preserve: {values['description']}. "
        "Keep the same character identity, costume, palette, outline thickness, camera, scale, facing direction, and anchor. "
        f"Previous phase: {values['previous_action_phase']}. "
        f"Current action phase: {values['action_phase']}. "
        f"Canvas contract: one single frame only, target frame size {values['width']}x{values['height']} logical pixels, where each pixel is one square grid cell. "
        "The subject should remain inside the frame and aligned consistently. "
        f"Use pure solid key-color {values['green']} for all empty/background pixels for chroma-key removal; "
        f"keep visible colors outside the maximum key-color tolerance ({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        f"Use no more than {values['max_colors']} visible subject/effect colors; background color does not count. "
        f"{loop_closure} "
        "Do not create a grid, collage, sprite sheet, duplicate character, text, watermark, background scene, labels, numbers, or extra frames."
        f"{retry_hint}"
    )


def _resolve_settings(cfg: AppConfig, inputs: SpritePipelineInput, description: str) -> _SequenceSettings:
    sprite = cfg.sprite
    max_frame_count = max(1, int(getattr(sprite, "max_frame_count", 12)))
    requested_count = int(inputs.frame_count or getattr(sprite, "frame_count", 9))
    if requested_count < 1 or requested_count > max_frame_count:
        raise ValueError(f"序列帧最多支持 {max_frame_count} 帧")
    fps = max(1, int(inputs.fps or getattr(sprite, "fps", 8)))
    duration_ms = max(20, int(round(1000 / fps)))
    target_size = _size_tuple(inputs.pixelize_params.output_size, tuple(sprite.pixel_size))
    key_hex, _key_rgb = resolve_key_color(sprite.green_screen_color, description)
    return _SequenceSettings(
        frame_count=requested_count,
        fps=fps,
        duration_ms=duration_ms,
        loop=int(sprite.loop if inputs.loop is None else inputs.loop),
        target_size=target_size,
        frame_size_step=max(1, int(getattr(sprite, "frame_size_step", 16))),
        oversize_regenerate_threshold=max(1.0, float(getattr(sprite, "oversize_regenerate_threshold", 1.5))),
        max_frame_retries=max(0, int(getattr(sprite, "max_frame_retries", 2))),
        gif_export=bool(getattr(sprite, "gif_export", False) if inputs.gif_export is None else inputs.gif_export),
        anchor=str(getattr(sprite, "anchor", "bottom_center") or "bottom_center"),
        key_color=key_hex,
        key_tolerance=int(sprite.green_screen_tolerance if inputs.key_tolerance is None else inputs.key_tolerance),
        max_colors=int(inputs.pixelize_params.colors or sprite.colors),
        reference_policy_requested=str(getattr(sprite, "reference_policy", "first_frame_and_previous_frame") or "first_frame_and_previous_frame"),
        reference_policy_effective="single_reference_previous_frames_with_final_frame_first_anchor",
        reference_policy_fallback_reason="Packy image edit wrapper currently exposes one multipart image field; middle frames use the previous frame, and the final frame uses frame 1 as loop-anchor reference.",
    )


def _prepare_reference(
    raw_path: Path,
    reference_path: Path,
    *,
    target_size: tuple[int, int],
    generated_preprocess_method: str | None,
) -> dict[str, Any]:
    with Image.open(raw_path) as opened:
        source = opened.convert("RGBA")
    preprocessed = preprocess_generated_image(
        source,
        method=generated_preprocess_method,
        target_size=target_size,
    )
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    preprocessed.image.convert("RGBA").save(reference_path)
    return dict(preprocessed.meta)


def _extract_frame_content(
    cfg: AppConfig,
    reference_path: Path,
    *,
    key_tolerance: int,
) -> tuple[Image.Image, tuple[int, int, int, int] | None, dict[str, Any]]:
    with Image.open(reference_path) as opened:
        image = opened.convert("RGBA")
    alpha_channel = np.asarray(image)[..., 3]
    corner_alpha = [
        int(alpha_channel[0, 0]),
        int(alpha_channel[0, -1]),
        int(alpha_channel[-1, 0]),
        int(alpha_channel[-1, -1]),
    ]
    if min(corner_alpha) <= 8:
        alpha = image
    else:
        alpha = remove_background(
            image,
            tolerance=max(0, int(key_tolerance)),
            feather=0,
            edge_style="hard",
            keep_border_bleed=True,
            **_sprite_bg_removal_options(cfg, tolerance=key_tolerance),
        )
    alpha = remove_translucent_edge_halo(alpha)
    bbox = _visible_bbox(alpha)
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), None, {
            "reference_size": list(image.size),
            "alpha_size": list(alpha.size),
            "bbox": None,
        }
    content = alpha.crop(bbox).convert("RGBA")
    return content, bbox, {
        "reference_size": list(image.size),
        "alpha_size": list(alpha.size),
        "bbox": list(bbox),
        "content_size": list(content.size),
    }


def _is_oversized(content: Image.Image, target_size: tuple[int, int], threshold: float) -> bool:
    return content.width > target_size[0] * threshold or content.height > target_size[1] * threshold


def _retry_hint(attempt: int) -> str:
    if attempt <= 0:
        return ""
    return (
        "Retry correction: keep the complete subject fully inside the target single-frame canvas, "
        "avoid oversized limbs/effects, do not crop the subject, and leave a few transparent/key-color pixels of padding."
    )


def _generate_or_load_first_frame(
    cfg: AppConfig,
    cache: Cache,
    *,
    prompt: str,
    raw_path: Path,
    material: dict[str, Any],
    refresh_cache: bool,
    image_size: str | None,
    image_quality: str | None,
    image_model: str | None,
) -> str:
    cached = None if refresh_cache else cache.lookup("sprite_sequence_imagegen", material, "png")
    if cached is not None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(cached.read_bytes())
        return "cache"
    generate_image(
        cfg,
        prompt,
        raw_path,
        size=image_size or cfg.image_gen.size,
        quality=image_quality or cfg.sprite.image_quality,
        model=image_model,
    )
    cache.store_copy("sprite_sequence_imagegen", material, "png", raw_path)
    return "generated"


def _generate_or_load_next_frame(
    cfg: AppConfig,
    cache: Cache,
    *,
    previous_reference_path: Path,
    prompt: str,
    raw_path: Path,
    material: dict[str, Any],
    refresh_cache: bool,
    image_size: str | None,
    image_quality: str | None,
    image_model: str | None,
) -> str:
    cached = None if refresh_cache else cache.lookup("sprite_sequence_imageedit", material, "png")
    if cached is not None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(cached.read_bytes())
        return "cache"
    edit_image(
        cfg,
        previous_reference_path,
        prompt,
        raw_path,
        size=image_size or cfg.image_gen.size,
        quality=image_quality or cfg.sprite.image_quality,
        model=image_model,
        input_fidelity=cfg.image_gen.edit_input_fidelity,
    )
    cache.store_copy("sprite_sequence_imageedit", material, "png", raw_path)
    return "edited"


def _generate_frame_with_retries(
    cfg: AppConfig,
    cache: Cache,
    inputs: SpritePipelineInput,
    settings: _SequenceSettings,
    *,
    index: int,
    description: str,
    timeline: list[str],
    raw_dir: Path,
    reference_dir: Path,
    previous_reference_path: Path | None,
    notify: ProgressCb,
) -> _FrameDraft:
    raw_path = raw_dir / f"frame_{index:03d}.png"
    reference_path = reference_dir / f"frame_{index:03d}.png"
    action_phase = timeline[index - 1]
    previous_phase = timeline[index - 2] if index > 1 else ""
    last_error = ""
    for attempt in range(settings.max_frame_retries + 1):
        prompt = (
            build_sequence_first_frame_prompt(
                cfg,
                description,
                target_size=settings.target_size,
                frame_count=settings.frame_count,
                action_phase=action_phase,
                key_color=settings.key_color,
                key_tolerance=settings.key_tolerance,
                max_colors=settings.max_colors,
                anchor=settings.anchor,
            )
            if index == 1
            else build_sequence_next_frame_prompt(
                cfg,
                description,
                target_size=settings.target_size,
                frame_index=index,
                frame_count=settings.frame_count,
                action_phase=action_phase,
                previous_action_phase=previous_phase,
                key_color=settings.key_color,
                key_tolerance=settings.key_tolerance,
                max_colors=settings.max_colors,
                anchor=settings.anchor,
                retry_hint=_retry_hint(attempt),
            )
        )
        try:
            material = {
                "prompt": prompt,
                "user_prompt": inputs.prompt,
                "frame_index": index,
                "frame_count": settings.frame_count,
                "attempt": attempt,
                "target_size": list(settings.target_size),
                "size": inputs.image_size or cfg.image_gen.size,
                "quality": inputs.image_quality or cfg.sprite.image_quality,
                "model": inputs.image_model or cfg.image_gen.model,
                "output_format": cfg.image_gen.output_format,
            }
            if index == 1:
                mode = _generate_or_load_first_frame(
                    cfg,
                    cache,
                    prompt=prompt,
                    raw_path=raw_path,
                    material=material,
                    refresh_cache=inputs.refresh_cache,
                    image_size=inputs.image_size,
                    image_quality=inputs.image_quality,
                    image_model=inputs.image_model,
                )
            else:
                if previous_reference_path is None:
                    raise ValueError("缺少上一帧参考图")
                material["reference_sha256"] = sha256_of_file(previous_reference_path)
                mode = _generate_or_load_next_frame(
                    cfg,
                    cache,
                    previous_reference_path=previous_reference_path,
                    prompt=prompt,
                    raw_path=raw_path,
                    material=material,
                    refresh_cache=inputs.refresh_cache,
                    image_size=inputs.image_size,
                    image_quality=inputs.image_quality,
                    image_model=inputs.image_model,
                )
            preprocess_meta = _prepare_reference(
                raw_path,
                reference_path,
                target_size=settings.target_size,
                generated_preprocess_method=inputs.pixelize_params.generated_preprocess_method,
            )
            content, bbox, postprocess_meta = _extract_frame_content(
                cfg,
                reference_path,
                key_tolerance=settings.key_tolerance,
            )
            if bbox is None:
                raise ValueError("未检测到可见主体像素")
            if _is_oversized(content, settings.target_size, settings.oversize_regenerate_threshold):
                raise ValueError(
                    f"帧内容尺寸 {content.width}x{content.height} 超过目标尺寸 {settings.target_size[0]}x{settings.target_size[1]} 的 "
                    f"{settings.oversize_regenerate_threshold:.0%} 阈值"
                )
            return _FrameDraft(
                index=index,
                raw_path=raw_path,
                reference_path=reference_path,
                content=content,
                bbox=bbox,
                action_phase=action_phase,
                effective_prompt=prompt,
                generation_mode=mode,
                attempts=attempt + 1,
                preprocess_meta=preprocess_meta,
                postprocess_meta=postprocess_meta,
            )
        except Exception as exc:  # noqa: BLE001 - 单帧重试需要记录原始错误
            last_error = str(exc)
            notify(
                "sprite_frame_retry",
                {
                    "frame_index": index,
                    "attempt": attempt + 1,
                    "max_attempts": settings.max_frame_retries + 1,
                    "error": last_error,
                },
            )
            if attempt >= settings.max_frame_retries:
                break
    raise ValueError(f"第 {index} 帧生成失败：{last_error}")


def _paste_content_to_canvas(content: Image.Image, *, size: tuple[int, int], anchor: str) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    frame = content.convert("RGBA")
    x = max(0, (size[0] - frame.width) // 2)
    anchor_key = (anchor or "bottom_center").strip().lower()
    if anchor_key in {"center", "middle", "center_center"}:
        y = max(0, (size[1] - frame.height) // 2)
    else:
        y = max(0, size[1] - frame.height)
    canvas.alpha_composite(frame, (x, y))
    return canvas


def _finalize_frames(
    drafts: list[_FrameDraft],
    final_dir: Path,
    *,
    settings: _SequenceSettings,
    shared_palette: bool,
    dither: str,
) -> tuple[list[SpriteFrame], dict[str, Any], tuple[int, int], list[Path]]:
    if not drafts:
        raise ValueError("没有可用于合成的序列帧")
    max_content_width = max(draft.content.width for draft in drafts)
    max_content_height = max(draft.content.height for draft in drafts)
    effective_size = (
        _ceil_to_multiple(max(settings.target_size[0], max_content_width), settings.frame_size_step),
        _ceil_to_multiple(max(settings.target_size[1], max_content_height), settings.frame_size_step),
    )
    canvases = [
        _paste_content_to_canvas(draft.content, size=effective_size, anchor=settings.anchor)
        for draft in drafts
    ]
    shared_palette_hex: list[str] = []
    if shared_palette:
        canvases, shared_palette_hex = _apply_shared_palette(
            canvases,
            colors=settings.max_colors,
            dither=dither,
        )
    final_dir.mkdir(parents=True, exist_ok=True)
    frames: list[SpriteFrame] = []
    frame_paths: list[Path] = []
    for draft, image in zip(drafts, canvases, strict=True):
        path = final_dir / f"frame_{draft.index:03d}.png"
        image.save(path)
        frame_paths.append(path)
        rect = {
            "x": (draft.index - 1) * effective_size[0],
            "y": 0,
            "w": effective_size[0],
            "h": effective_size[1],
        }
        frames.append(
            SpriteFrame(
                index=draft.index,
                raw_path=draft.raw_path,
                reference_path=draft.reference_path,
                path=path,
                sheet_rect=rect,
                action_phase=draft.action_phase,
                bbox=draft.bbox,
            )
        )
    meta = {
        "mode": "sequence_frame_asset_postprocess",
        "target_frame_size": list(settings.target_size),
        "effective_frame_size": list(effective_size),
        "max_content_size": [max_content_width, max_content_height],
        "frame_size_step": settings.frame_size_step,
        "overflow_policy": "expand_sheet_to_fit",
        "anchor": settings.anchor,
        "shared_palette": bool(shared_palette),
        "shared_palette_colors": shared_palette_hex,
        "frame_meta": [
            {
                "index": draft.index,
                "input_size": list(draft.content.size),
                "output_size": list(effective_size),
                "bbox": list(draft.bbox) if draft.bbox else None,
                "generation_mode": draft.generation_mode,
                "attempts": draft.attempts,
                "preprocess": draft.preprocess_meta,
                "postprocess": draft.postprocess_meta,
            }
            for draft in drafts
        ],
    }
    return frames, meta, effective_size, frame_paths


def _write_sequence_json(
    path: Path,
    *,
    run_dir: Path,
    frames: list[SpriteFrame],
    settings: _SequenceSettings,
    effective_size: tuple[int, int],
    sheet_path: Path,
    timeline: list[str],
    billing: dict[str, Any] | None,
) -> dict[str, Any]:
    sheet_size = (effective_size[0] * len(frames), effective_size[1])
    sequence = {
        "type": "sequence_frames",
        "frame_count": len(frames),
        "max_frame_count": int(settings.frame_count if settings.frame_count > 12 else 12),
        "fps": settings.fps,
        "duration_ms": settings.duration_ms,
        "loop": settings.loop == 0,
        "target_frame_size": {"width": settings.target_size[0], "height": settings.target_size[1]},
        "effective_frame_size": {"width": effective_size[0], "height": effective_size[1]},
        "sheet_size": {"width": sheet_size[0], "height": sheet_size[1]},
        "anchor": settings.anchor,
        "overflow_policy": "expand_sheet_to_fit",
        "frame_size_step": settings.frame_size_step,
        "oversize_regenerate_threshold": settings.oversize_regenerate_threshold,
        "final_postprocess": "reuse_asset_pipeline",
        "reference_policy_requested": settings.reference_policy_requested,
        "reference_policy_effective": settings.reference_policy_effective,
        "reference_policy_fallback_reason": settings.reference_policy_fallback_reason,
        "playback_source": _rel(sheet_path, run_dir),
        "billing": billing or None,
        "action_timeline": timeline,
        "frames": [
            {
                "index": frame.index,
                "name": f"frame_{frame.index:03d}",
                "file": _rel(frame.path, run_dir),
                "raw_file": _rel(frame.raw_path, run_dir),
                "reference_file": _rel(frame.reference_path, run_dir),
                "sheet_rect": dict(frame.sheet_rect),
                "action_phase": frame.action_phase,
                "bbox": list(frame.bbox) if frame.bbox else None,
            }
            for frame in frames
        ],
    }
    path.write_text(json.dumps(sequence, ensure_ascii=False, indent=2), encoding="utf-8")
    return sequence


def _write_sprite_input_debug(
    path: Path,
    *,
    raw_prompt: str,
    normalized_description: str,
    settings: _SequenceSettings,
    effective_size: tuple[int, int] | None,
    timeline: list[str],
    prompts: dict[int, str],
    billing: dict[str, Any] | None,
) -> None:
    target_bounds = _target_frame_bounds(settings.frame_count, settings.target_size[0], settings.target_size[1])
    effective = effective_size or settings.target_size
    effective_bounds = _target_frame_bounds(settings.frame_count, effective[0], effective[1])
    sheet_size = (effective[0] * settings.frame_count, effective[1])
    parts = [
        "[raw_prompt]",
        raw_prompt,
        "",
        "[normalized_description]",
        normalized_description,
        "",
        "[sequence_settings]",
        f"frame_count = {settings.frame_count}",
        "max_frame_count = 12",
        f"fps = {settings.fps}",
        f"duration_ms = {settings.duration_ms}",
        f"loop = {settings.loop}",
        f"target_frame_width = {settings.target_size[0]}",
        f"target_frame_height = {settings.target_size[1]}",
        f"effective_frame_width = {effective[0]}",
        f"effective_frame_height = {effective[1]}",
        f"anchor = {settings.anchor}",
        f"background_policy = key_color_to_transparent({settings.key_color})",
        "overflow_policy = expand_sheet_to_fit",
        f"frame_size_step = {settings.frame_size_step}",
        f"oversize_regenerate_threshold = {settings.oversize_regenerate_threshold:.0%}",
        "final_postprocess = reuse_asset_pipeline",
        f"gif_export = {'true' if settings.gif_export else 'false'}",
        "playback_source = sprite_sheet_with_sequence_json",
        f"reference_policy_requested = {settings.reference_policy_requested}",
        f"reference_policy_effective = {settings.reference_policy_effective}",
        f"reference_policy_fallback_reason = {settings.reference_policy_fallback_reason}",
        "",
        "[billing]",
    ]
    if billing:
        parts.extend(f"{key} = {value}" for key, value in billing.items())
    else:
        parts.append("billing = not_provided")
    parts.extend([
        "",
        "[target_sheet_contract]",
        f"target_sprite_sheet_width = {settings.target_size[0] * settings.frame_count}",
        f"target_sprite_sheet_height = {settings.target_size[1]}",
        "read_order = left_to_right",
        _format_frame_bounds(target_bounds),
        "",
        "[effective_sheet_contract]",
        f"sprite_sheet_width = {sheet_size[0]}",
        f"sprite_sheet_height = {sheet_size[1]}",
        "read_order = left_to_right",
        _format_frame_bounds(effective_bounds),
        "",
        "[action_timeline]",
    ])
    parts.extend(f"frame_{index:03d} = {phase}" for index, phase in enumerate(timeline, start=1))
    for index in sorted(prompts):
        parts.extend(["", f"[effective_prompt_frame_{index:03d}]", prompts[index]])
    parts.extend([
        "",
        "[processing_pipeline]",
        "frame_generation = first_frame_asset_generation_then_iterative_img2img",
        f"reference_policy = {settings.reference_policy_effective}",
        "reference_preprocess = perfectPixel",
        "final_postprocess = reuse current asset pipeline -> calculate content bounds -> transparent pad to effective frame size",
        "packing = horizontal_sprite_sheet",
        "preview = sprite_sheet_sequence_player",
    ])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def run_sprite_pipeline(
    cfg: AppConfig,
    inputs: SpritePipelineInput,
    progress: ProgressCb | None = None,
) -> SpritePipelineResult:
    """执行：首帧生图 -> 逐帧图生图 -> 横向精灵表 + sequence.json。"""

    notify = progress or _noop
    if not (inputs.prompt or "").strip():
        raise ValueError("序列帧任务需要 prompt")

    out_root = Path(inputs.out_root or cfg.output.root)
    run_dir = new_run_dir(out_root, seed=f"sequence\n{inputs.prompt}")
    notify("sprite_run_start", {"run_dir": str(run_dir)})

    try:
        guard = validate_user_prompt(cfg, inputs.prompt, allow_template_break=True)
    except PromptPolicyError as exc:
        notify("prompt_guard_rejected", exc.result.to_metadata())
        raise ValueError(str(exc)) from exc
    prompt_guard_meta = guard.to_metadata()
    description = guard.normalized_description or inputs.prompt
    notify("prompt_guard_ready", prompt_guard_meta)

    settings = _resolve_settings(cfg, inputs, description)
    timeline = build_action_timeline(description, settings.frame_count)
    _write_sprite_input_debug(
        run_dir / "00_input.txt",
        raw_prompt=inputs.prompt,
        normalized_description=description,
        settings=settings,
        effective_size=None,
        timeline=timeline,
        prompts={},
        billing=inputs.billing,
    )

    raw_dir = run_dir / "frames" / "raw"
    reference_dir = run_dir / "frames" / "reference"
    final_dir = run_dir / "frames" / "final"
    sheet_path = run_dir / "sprite_sheet.png"
    sequence_path = run_dir / "sequence.json"
    gif_path = run_dir / "sprite.gif"
    cache = Cache(cfg.cache.dir, enabled=cfg.cache.enabled and inputs.use_cache)

    drafts: list[_FrameDraft] = []
    effective_prompts: dict[int, str] = {}
    previous_reference_path: Path | None = None
    with _local_stage(inputs.local_stage_context):
        for index in range(1, settings.frame_count + 1):
            notify("sprite_frame_start", {"frame_index": index, "frame_count": settings.frame_count})
            reference_path_for_frame = (
                drafts[0].reference_path
                if index == settings.frame_count and settings.frame_count > 2 and drafts
                else previous_reference_path
            )
            draft = _generate_frame_with_retries(
                cfg,
                cache,
                inputs,
                settings,
                index=index,
                description=description,
                timeline=timeline,
                raw_dir=raw_dir,
                reference_dir=reference_dir,
                previous_reference_path=reference_path_for_frame,
                notify=notify,
            )
            drafts.append(draft)
            effective_prompts[index] = draft.effective_prompt
            previous_reference_path = draft.reference_path
            notify(
                "sprite_frame_ready",
                {
                    "frame_index": index,
                    "raw": str(draft.raw_path),
                    "reference": str(draft.reference_path),
                    "content_size": list(draft.content.size),
                    "attempts": draft.attempts,
                },
            )

        frames, frame_meta, effective_size, frame_paths = _finalize_frames(
            drafts,
            final_dir,
            settings=settings,
            shared_palette=cfg.sprite.shared_palette,
            dither=inputs.pixelize_params.dither,
        )
        notify("sprite_frames_finalized", {"count": len(frame_paths), "dir": str(final_dir), "effective_size": list(effective_size)})

        compose_horizontal_sprite_sheet(frame_paths, sheet_path)
        preview_path: Path | None = None
        if settings.gif_export:
            compose_gif(frame_paths, gif_path, duration_ms=settings.duration_ms, loop=settings.loop)
            preview_path = gif_path
        notify("sprite_outputs_ready", {"sheet": str(sheet_path), "sequence": str(sequence_path), "gif": str(preview_path) if preview_path else None})

    _write_sprite_input_debug(
        run_dir / "00_input.txt",
        raw_prompt=inputs.prompt,
        normalized_description=description,
        settings=settings,
        effective_size=effective_size,
        timeline=timeline,
        prompts=effective_prompts,
        billing=inputs.billing,
    )
    sequence = _write_sequence_json(
        sequence_path,
        run_dir=run_dir,
        frames=frames,
        settings=settings,
        effective_size=effective_size,
        sheet_path=sheet_path,
        timeline=timeline,
        billing=inputs.billing,
    )
    source_path = drafts[0].raw_path
    meta = {
        "version": __version__,
        "input": {
            "prompt": inputs.prompt,
            "effective_prompt": effective_prompts.get(1, ""),
            "effective_prompts": {str(key): value for key, value in effective_prompts.items()},
        },
        "prompt_guard": prompt_guard_meta,
        "image_gen": {
            "model": inputs.image_model or cfg.image_gen.model,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.sprite.image_quality,
            "output_format": cfg.image_gen.output_format,
            "input_fidelity": cfg.image_gen.edit_input_fidelity,
            "used": True,
            "mode": "sequence_frames",
        },
        "sprite": {
            "type": "sequence_frames",
            "frame_count": len(frames),
            "max_frame_count": int(getattr(cfg.sprite, "max_frame_count", 12)),
            "fps": settings.fps,
            "duration_ms": settings.duration_ms,
            "loop": settings.loop,
            "target_frame_size": list(settings.target_size),
            "effective_frame_size": list(effective_size),
            "sheet_size": [effective_size[0] * len(frames), effective_size[1]],
            "colors": settings.max_colors,
            "anchor": settings.anchor,
            "green_screen_color": settings.key_color,
            "green_screen_tolerance": settings.key_tolerance,
            "frame_background_flow": "per_frame_perfect_pixel_to_asset_color_to_alpha_to_effective_canvas",
            "reference_policy_requested": settings.reference_policy_requested,
            "reference_policy_effective": settings.reference_policy_effective,
            "reference_policy_fallback_reason": settings.reference_policy_fallback_reason,
            "overflow_policy": "expand_sheet_to_fit",
            "frame_size_step": settings.frame_size_step,
            "oversize_regenerate_threshold": settings.oversize_regenerate_threshold,
            "max_frame_retries": settings.max_frame_retries,
            "source_frame": _rel(source_path, run_dir),
            "raw_frames_dir": _rel(raw_dir, run_dir),
            "reference_frames_dir": _rel(reference_dir, run_dir),
            "frames_dir": _rel(final_dir, run_dir),
            "horizontal_sheet": sheet_path.name,
            "sequence_json": sequence_path.name,
            "gif": gif_path.name if settings.gif_export else None,
            "frames": [frame.to_metadata(run_dir) for frame in frames],
            "pixelize": frame_meta,
            "sequence": sequence,
            "billing": inputs.billing or None,
        },
        "cache": {"enabled": cache.enabled, "refresh": inputs.refresh_cache},
        "outputs": {
            "source": _rel(source_path, run_dir),
            "sprite_frames": _rel(final_dir, run_dir),
            "sprite_sheet": sheet_path.name,
            "sequence_json": sequence_path.name,
            "sprite_gif": gif_path.name if settings.gif_export else None,
            "pixelized": sheet_path.name,
            "preview": gif_path.name if settings.gif_export else None,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return SpritePipelineResult(
        run_dir=run_dir,
        source_path=source_path,
        frame_paths=frame_paths,
        pixel_path=sheet_path,
        preview_path=gif_path if settings.gif_export else None,
        meta_path=meta_path,
        meta=meta,
    )
