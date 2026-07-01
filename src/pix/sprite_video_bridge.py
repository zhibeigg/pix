"""首尾帧视频补间序列帧 pipeline。"""

from __future__ import annotations

import base64
from collections import Counter, deque
import json
import re
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager, Mapping

import numpy as np
from PIL import Image

from pix import __version__
from pix.api.ark_video import ArkVideoClient
from pix.api.image_dispatcher import clear_image_provider_history, image_provider_history
from pix.api.image_gen import edit_image, generate_image
from pix.api.packy_client import make_packy_client
from pix.api.prompt_guard import PromptPolicyError, RAW_IMAGE_PROMPT_MAX_CHARS, validate_user_prompt
from pix.config import AppConfig, require_vl_api_key
from pix.contact_sheet import parse_hex_color
from pix.io_utils import image_to_base64_data_url, new_run_dir
from pix.pixelize.bg_removal import apply_pixel_bg_alpha
from pix.pixelize.core import PixelizeParams, next_power_of_two
from pix.pixelize.palette import kmeans_palette, rgb_to_hex
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.prompt_style import STYLE_PROFILE_POLICY_MAX_CHARS, compile_style_profile, style_profile_policy_text
from pix.sprite import (
    SpriteFrame,
    SpritePipelineResult,
    _apply_shared_palette,
    _ceil_to_multiple,
    _quantize_with_palette,
    _rel,
    _visible_bbox,
    compose_gif,
    compose_grid_sprite_sheet,
    compose_horizontal_sprite_sheet,
)
from pix.sprite_mosaic import (
    SpriteMosaicInput,
    _apply_frame_edges,
    _axis_transition_splits,
    _build_sequence_json,
    _ensure_row_prompts,
    _frame_metadata,
    _frame_size_report,
    _resolve_settings,
)


LocalStageContext = Callable[[], ContextManager[None]]
ProgressCb = Any
_WAITING_STATUSES = {"queued", "running"}
_FAILED_STATUSES = {"failed", "expired", "cancelled"}
_FRAME_BACKGROUND_FLOW = "video_frames_to_perfect_pixel_detect_all_to_mode_grid_to_fixed_grid_perfect_pixel_to_key_color_alpha_to_denoise_to_union_bbox_to_power2_square_canvas_to_palette_limit"


@dataclass
class SpriteVideoBridgeInput:
    prompt: str
    rows: int
    cols: int
    row_prompts: list[str] = field(default_factory=list)
    video_action_prompt: str = ""
    video_return_to_first_frame: bool = False
    reference_image_path: Path | None = None
    image_size: str | None = None
    image_quality: str | None = None
    image_model: str | None = None
    pixelize_params: PixelizeParams = field(default_factory=PixelizeParams)
    out_root: str | Path | None = None
    fps: int = 8
    duration_ms: int | None = None
    loop: int | None = None
    gif_export: bool | None = None
    billing: dict[str, Any] | None = None
    style_profile: Mapping[str, object] | None = None
    local_stage_context: LocalStageContext | None = None
    state: dict[str, Any] | None = None


class VideoBridgeWaiting(RuntimeError):
    """Ark 视频任务仍在异步执行，worker 应把 job 置为 waiting。"""

    def __init__(self, message: str, *, state: dict[str, Any], run_dir: Path):
        super().__init__(message)
        self.state = state
        self.run_dir = run_dir


def _noop(_step: str, _payload: dict[str, Any]) -> None:
    pass


def _local_stage(factory: LocalStageContext | None) -> ContextManager[None]:
    return factory() if factory is not None else nullcontext()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def next_poll_at(cfg: AppConfig) -> str:
    interval = max(1, int(getattr(cfg.video_bridge, "poll_interval_seconds", 30) or 30))
    return _iso(_utcnow() + timedelta(seconds=interval))


def derive_video_bridge_duration_seconds(frame_count: int, duration_ms: int) -> int:
    """按序列帧播放节奏推导 Ark 视频秒数。

    video_bridge 的抽帧时间轴必须跟最终序列帧一致：N 帧 × 每帧间隔。
    Ark 当前 duration 使用秒级整数，非整秒时向上取整，避免生成视频短于目标动画。
    """
    safe_frame_count = max(1, int(frame_count))
    safe_duration_ms = max(1, int(duration_ms))
    return max(1, (safe_frame_count * safe_duration_ms + 999) // 1000)


def video_bridge_timing_meta(frame_count: int, duration_ms: int) -> dict[str, Any]:
    safe_frame_count = max(1, int(frame_count))
    safe_duration_ms = max(1, int(duration_ms))
    total_ms = safe_frame_count * safe_duration_ms
    return {
        "source": "sprite_timing",
        "frame_count": safe_frame_count,
        "frame_duration_ms": safe_duration_ms,
        "total_duration_ms": total_ms,
        "ark_duration_seconds": derive_video_bridge_duration_seconds(safe_frame_count, safe_duration_ms),
    }


def parse_state_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_waiting_state_due(state: Mapping[str, Any], now: datetime | None = None) -> bool:
    due = parse_state_time(state.get("next_poll_at"))
    return due is None or due <= (now or _utcnow())


def is_waiting_state_expired(state: Mapping[str, Any], cfg: AppConfig, now: datetime | None = None) -> bool:
    started = parse_state_time(state.get("created_at") or state.get("started_at"))
    if started is None:
        return False
    timeout = max(1, int(getattr(cfg.video_bridge, "task_timeout_seconds", 1800) or 1800))
    return started + timedelta(seconds=timeout) <= (now or _utcnow())


def _write_state(run_dir: Path, state: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "video_bridge_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_file_state(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "video_bridge_state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _video_input_size(cfg: AppConfig) -> tuple[int, int]:
    raw = getattr(cfg.video_bridge, "video_input_size", (640, 640))
    if isinstance(raw, str) and "x" in raw.lower():
        left, right = raw.lower().split("x", 1)
        return max(300, int(left)), max(300, int(right))
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return max(300, int(raw[0])), max(300, int(raw[1]))
        except (TypeError, ValueError):
            pass
    return (640, 640)


def _prompt_guard_max_chars(cfg: AppConfig) -> int:
    return (
        max(1, int(getattr(cfg.sprite, "subject_max_chars", RAW_IMAGE_PROMPT_MAX_CHARS) or RAW_IMAGE_PROMPT_MAX_CHARS))
        + max(1, int(getattr(cfg.sprite, "row_prompt_max_chars", 600) or 600))
        + STYLE_PROFILE_POLICY_MAX_CHARS
    )


def _action_prompt(inputs: SpriteVideoBridgeInput) -> str:
    explicit = (inputs.video_action_prompt or "").strip()
    if explicit:
        return explicit
    for item in inputs.row_prompts:
        if (item or "").strip():
            return item.strip()
    return inputs.prompt.strip()


def _mosaic_inputs_for_video_bridge(
    inputs: SpriteVideoBridgeInput,
    *,
    action_prompt: str,
) -> SpriteMosaicInput:
    """把 video_bridge 输入映射到 mosaic 的通用设置解析结构。

    video_bridge 不是 mosaic 出图，但它应复用同一套 `pixelize` 参数语义：
    output_size / colors / edge_style / bg_feather / dither / generated_preprocess_method。
    """
    return SpriteMosaicInput(
        prompt=inputs.prompt,
        rows=inputs.rows,
        cols=inputs.cols,
        row_prompts=inputs.row_prompts or [action_prompt],
        reference_image_path=inputs.reference_image_path,
        image_size=inputs.image_size,
        image_quality=inputs.image_quality,
        image_model=inputs.image_model,
        pixelize_params=inputs.pixelize_params,
        out_root=inputs.out_root,
        fps=inputs.fps,
        duration_ms=inputs.duration_ms,
        loop=inputs.loop,
        gif_export=inputs.gif_export,
        billing=inputs.billing,
        style_profile=inputs.style_profile,
        local_stage_context=inputs.local_stage_context,
    )


def _resolve_video_bridge_settings(
    cfg: AppConfig,
    inputs: SpriteVideoBridgeInput,
    *,
    description: str,
    action_prompt: str,
):
    return _resolve_settings(
        cfg,
        _mosaic_inputs_for_video_bridge(inputs, action_prompt=action_prompt),
        description,
    )


def _frame_parameter_clause(
    *,
    frame_size: tuple[int, int] | None,
    max_colors: int | None,
    key_color: str | None,
    key_tolerance: int | None,
    denoise: bool,
) -> str:
    parts: list[str] = []
    if frame_size is not None:
        parts.append(
            f"Target extracted sprite frame size is {int(frame_size[0])}x{int(frame_size[1])} pixel-art pixels; "
            "keep the subject readable at exactly this small game-sprite size and do not rely on subpixel detail."
        )
    if max_colors is not None:
        parts.append(
            f"Use no more than {max(2, int(max_colors))} visible foreground/subject colors across the animation; "
            "the flat key-color background does not count, and the palette must stay stable with no per-frame color flicker."
        )
    if key_color:
        tolerance_text = (
            f" with removal tolerance {max(0, int(key_tolerance))} RGB Euclidean distance"
            if key_tolerance is not None
            else ""
        )
        parts.append(
            f"Use the single flat key-color {key_color} only for background/empty pixels{tolerance_text}; "
            "foreground colors must stay clearly separated from it."
        )
    if denoise:
        parts.append(
            "Denoise discipline: do not create isolated random color speckles, compression-like noise, stray dots, "
            "one-pixel debris, or off-body color flecks; all visible non-background pixels should belong to the main subject, controlled effects, weapon trails, smoke, or particles attached to the action."
        )
    return " ".join(parts)


def build_video_bridge_keyframe_prompt(
    cfg: AppConfig,
    description: str,
    action_prompt: str,
    *,
    key_color: str,
    key_tolerance: int | None = None,
    frame_size: tuple[int, int] | None = None,
    max_colors: int | None = None,
    denoise: bool = True,
    style_profile: Mapping[str, object] | None = None,
) -> str:
    style_prompt = compile_style_profile(style_profile).prompt
    parameter_clause = _frame_parameter_clause(
        frame_size=frame_size,
        max_colors=max_colors,
        key_color=key_color,
        key_tolerance=key_tolerance,
        denoise=denoise,
    )
    prompt = (
        "Create ONE image containing exactly two side-by-side panels for a pixel-art animation bridge. "
        f"Subject identity: {description}. Action to interpolate: {action_prompt}. "
        "Left panel: the exact START pose of the action. Right panel: the exact END pose of the same action. "
        "The same character or object must keep identical identity, costume, palette, outline thickness, scale, proportions, and ground footprint in both panels. "
        "Each pose must stay completely inside its own half of the image: the left pose cannot cross the vertical midpoint, the right pose cannot cross into the left half, and there must be a wide empty key-color gutter between the two poses. "
        "Use a flat orthographic game-sprite view with no camera perspective change. "
        f"Fill every empty/background pixel in both panels with one perfectly uniform key color {key_color}; no gradients, no shadows on the background, no texture in the background. "
        "Leave clear empty key-color margin around the subject in both panels. "
        f"{parameter_clause} "
        "Do not add text, labels, arrows, watermark, UI, frame numbers, borders, panel dividers, or extra poses. "
        "Crisp pixel art, hard edges, limited palette, no painterly blending, no anti-aliased soft brush."
    )
    if style_prompt:
        prompt = f"{prompt} {style_prompt}"
    return prompt.strip()


def build_video_bridge_motion_prompt(
    description: str,
    action_prompt: str,
    *,
    frame_count: int | None = None,
    frame_duration_ms: int | None = None,
    video_duration_seconds: int | None = None,
    return_to_first_frame: bool = False,
    frame_size: tuple[int, int] | None = None,
    max_colors: int | None = None,
    key_color: str | None = None,
    key_tolerance: int | None = None,
    denoise: bool = True,
) -> str:
    safe_frame_count = max(2, int(frame_count)) if frame_count else None
    frame_clause = (
        f"The motion will be sampled into {safe_frame_count} sprite frames, so every sampled frame must read as a clean incremental pose. "
        if safe_frame_count
        else "Every sampled frame must read as a clean incremental sprite pose. "
    )
    timing_clause = ""
    if safe_frame_count and frame_duration_ms and video_duration_seconds:
        safe_frame_duration_ms = max(1, int(frame_duration_ms))
        total_ms = safe_frame_count * safe_frame_duration_ms
        timing_clause = (
            f"Timing target: the source video duration is locked to {max(1, int(video_duration_seconds))} second(s), "
            f"derived from {safe_frame_count} sprite frames × {safe_frame_duration_ms} ms per frame "
            f"({total_ms} ms total animation time, rounded up to whole seconds for the video API). "
            "Distribute the motion evenly across this full duration so the extracted sprite frames preserve the requested playback cadence. "
        )
    parameter_clause = _frame_parameter_clause(
        frame_size=frame_size,
        max_colors=max_colors,
        key_color=key_color,
        key_tolerance=key_tolerance,
        denoise=denoise,
    )
    return_clause = (
        "Loop-return requirement: after the animation reaches the provided last_frame pose, it must continue with a smooth return motion back to the provided first_frame pose; the final sampled frame must match first_frame again, making the sequence loop-ready. Allocate enough intermediate frames for both the outbound action and the return-to-start motion, with no teleporting, no hard cut, and no sudden snap back to the initial pose. "
        if return_to_first_frame
        else ""
    )
    endpoint_clause = (
        "The first and final video frames must both match the provided first_frame image. The provided last_frame image is the peak/action target pose that should be reached during the middle or later part of the animation before returning to first_frame. "
        if return_to_first_frame
        else "The first frame must match the provided first_frame image and the final frame must match the provided last_frame image. "
    )
    return (
        f"Create a short continuous pixel-art motion interpolation for this subject: {description}. "
        f"Motion: {action_prompt}. {endpoint_clause}"
        f"{frame_clause}{timing_clause}{return_clause}Use smooth evenly spaced in-between poses with small consistent changes between adjacent frames; no sudden jumps, no duplicated frozen frames, no skipped action phases. "
        f"{parameter_clause} "
        "Every frame must be TRUE pixel art: visible pixels are crisp square pixel blocks aligned to a stable pixel grid, with hard edges, limited palette, no anti-aliasing, no motion blur, no painterly smoothing, no subpixel smearing, and no soft interpolated gradients. "
        "Pixel-block orientation rule: all visible pixel blocks must remain axis-aligned horizontal/vertical square tiles on one upright pixel grid; never rotate, tilt, shear, skew, diamond-turn, or slant the pixel blocks to simulate motion. Express motion only by changing whole square-pixel positions, silhouettes, and poses on the upright grid, not by rotating chunks of pixels. "
        "Keep a fixed orthographic game-sprite camera, identical character identity, proportions, palette, outline thickness, and scale for the entire video. "
        "The entire subject silhouette must remain fully inside the frame for every frame: hood, cloak, limbs, weapon, smoke, magic particles, trails, and all effects must stay visible with clear key-color padding on all four edges. "
        "Pixel-boundary rule: only the flat key-color background may touch the canvas edges; every non-background / non-key-color pixel is foreground and must stay completely inside the interior safe area, with at least 10% key-color margin from every canvas edge, including stray particles, smoke wisps, weapon tips, shadows, highlights, trails, and effects. "
        "Never crop, clip, truncate, or let any foreground pixel touch or cross the frame boundary; if the motion would extend outward, keep the subject centered and scale the motion down instead of moving outside the canvas. "
        "No cuts, no zoom, no camera pan, no background changes. No text, no logo, no watermark, no UI. Keep the flat key-color background consistent."
    )


def _data_url_from_png(path: Path, max_bytes: int) -> str:
    raw = path.read_bytes()
    if len(raw) > max(1, int(max_bytes)):
        raise ValueError(f"视频补间输入帧过大：{len(raw)} bytes，超过配置上限")
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _fit_to_canvas(image: Image.Image, size: tuple[int, int], key_rgb: tuple[int, int, int]) -> Image.Image:
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    src = image.convert("RGBA")
    scale = min(width / max(1, src.width), height / max(1, src.height))
    new_size = (max(1, int(round(src.width * scale))), max(1, int(round(src.height * scale))))
    resized = src.resize(new_size, Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (width, height), (*key_rgb, 255))
    canvas.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return canvas


def _paste_keyframe_content_to_canvas(content: Image.Image, *, size: tuple[int, int], anchor: str) -> Image.Image:
    """按几何 bbox 安全贴首尾关键帧。

    最终 sprite 帧使用质心对齐来降低身体抖动；但 Ark 首尾输入不能用质心对齐，
    否则长匕首/法杖等横向轮廓会被夹到归一化画布边缘。
    """
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


def _paste_final_frame_content_to_canvas(
    content: Image.Image,
    *,
    size: tuple[int, int],
    anchor: str,
    padding: int,
) -> Image.Image:
    """最终序列帧贴图时强制给所有非透明像素保留安全边。

    视频模型可能仍把烟雾/粒子生成到画面边缘；抽帧后必须保证成品中任何
    非背景/非透明像素都不触碰输出帧边界。
    """
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    frame = content.convert("RGBA")
    safe_padding = max(0, int(padding))
    min_x = safe_padding if frame.width + safe_padding * 2 <= size[0] else 0
    max_x = max(min_x, size[0] - frame.width - min_x)
    x = max(min_x, min(max_x, (size[0] - frame.width) // 2))
    alpha = np.asarray(frame)[..., 3]
    xs = np.where(alpha > 8)[1]
    if xs.size:
        centroid_x = float(xs.mean())
        x = int(round(size[0] / 2.0 - centroid_x))
        x = max(min_x, min(max_x, x))
    min_y = safe_padding if frame.height + safe_padding * 2 <= size[1] else 0
    max_y = max(min_y, size[1] - frame.height - min_y)
    anchor_key = (anchor or "bottom_center").strip().lower()
    if anchor_key in {"center", "middle", "center_center"}:
        y = max(min_y, min(max_y, (size[1] - frame.height) // 2))
    else:
        y = max(min_y, min(max_y, size[1] - frame.height - min_y))
    canvas.alpha_composite(frame, (x, y))
    return canvas


def _key_color_foreground_mask(image: Image.Image, key_rgb: tuple[int, int, int], tolerance: int) -> np.ndarray:
    arr = np.asarray(image.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.int32)
    key = np.asarray(key_rgb, dtype=np.int32)
    diff = rgb - key
    dist_sq = np.sum(diff * diff, axis=2)
    safe_tolerance = max(0, int(tolerance))
    return (arr[:, :, 3] > 8) & (dist_sq > safe_tolerance * safe_tolerance)


def _adaptive_keyframe_split_x(pair: Image.Image, key_rgb: tuple[int, int, int], key_tolerance: int) -> int:
    """在双栏关键帧之间用整轴扫掠寻找真实空隙，避免几何中线硬切。"""
    width = pair.width
    if width <= 2:
        return max(1, width // 2)
    mid = width // 2
    lo = max(1, int(round(width * 0.30)))
    hi = min(width - 1, int(round(width * 0.70)))
    if hi <= lo:
        return max(1, min(width - 1, mid))

    mask = _key_color_foreground_mask(pair, key_rgb, key_tolerance)
    counts = mask.sum(axis=0).astype(np.int64)
    scanned = _axis_transition_splits(counts, width, 2)
    if scanned is not None and len(scanned) == 3:
        split = int(scanned[1])
        # 双栏关键帧仍约束在中间区域，避免把左/右外边距当成首尾分隔。
        if lo <= split <= hi:
            return max(1, min(width - 1, split))

    # 回退：中间窗口内按平滑后的前景密度找最低点。
    window = max(5, min(31, ((hi - lo) // 12) | 1))
    kernel = np.ones(window, dtype=np.float32) / float(window)
    smoothed = np.convolve(counts.astype(np.float32), kernel, mode="same")
    split = lo + int(np.argmin(smoothed[lo:hi]))
    return max(1, min(width - 1, int(split)))


def _split_keyframes(
    pair_path: Path,
    first_path: Path,
    last_path: Path,
    *,
    key_rgb: tuple[int, int, int] | None = None,
    key_tolerance: int = 48,
) -> dict[str, Any]:
    with Image.open(pair_path) as opened:
        pair = opened.convert("RGBA")
    if key_rgb is None:
        split_x = max(1, pair.width // 2)
        method = "midpoint"
    else:
        split_x = _adaptive_keyframe_split_x(pair, key_rgb, key_tolerance)
        method = "axis_transition_gutter"
    pair.crop((0, 0, split_x, pair.height)).save(first_path)
    pair.crop((split_x, 0, pair.width, pair.height)).save(last_path)
    return {"method": method, "split_x": split_x, "source_size": [pair.width, pair.height]}


def _mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _expand_bbox(
    bbox: tuple[int, int, int, int],
    *,
    padding: int,
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = size
    safe_padding = max(0, int(padding))
    return (
        max(0, bbox[0] - safe_padding),
        max(0, bbox[1] - safe_padding),
        min(int(width), bbox[2] + safe_padding),
        min(int(height), bbox[3] + safe_padding),
    )


def _bbox_distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    dx = max(0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0, max(a[1], b[1]) - min(a[3], b[3]))
    return max(dx, dy)


def _foreground_components(
    linked_mask: np.ndarray,
    source_mask: np.ndarray,
) -> list[dict[str, Any]]:
    height, width = linked_mask.shape
    seen = np.zeros((height, width), dtype=bool)
    components: list[dict[str, Any]] = []
    for y in range(height):
        x_candidates = np.where(linked_mask[y] & ~seen[y])[0]
        for start_x_raw in x_candidates:
            start_x = int(start_x_raw)
            if seen[y, start_x] or not linked_mask[y, start_x]:
                continue
            queue: deque[tuple[int, int]] = deque([(start_x, y)])
            seen[y, start_x] = True
            xs: list[int] = []
            ys: list[int] = []
            source_xs: list[int] = []
            source_ys: list[int] = []
            dilated_area = 0
            while queue:
                x, current_y = queue.popleft()
                xs.append(x)
                ys.append(current_y)
                dilated_area += 1
                if source_mask[current_y, x]:
                    source_xs.append(x)
                    source_ys.append(current_y)
                for next_y in range(current_y - 1, current_y + 2):
                    if next_y < 0 or next_y >= height:
                        continue
                    for next_x in range(x - 1, x + 2):
                        if next_x < 0 or next_x >= width:
                            continue
                        if seen[next_y, next_x] or not linked_mask[next_y, next_x]:
                            continue
                        seen[next_y, next_x] = True
                        queue.append((next_x, next_y))
            if not source_xs or not source_ys:
                continue
            components.append(
                {
                    "area": len(source_xs),
                    "dilated_area": dilated_area,
                    "bbox": (min(source_xs), min(source_ys), max(source_xs) + 1, max(source_ys) + 1),
                    "linked_bbox": (min(xs), min(ys), max(xs) + 1, max(ys) + 1),
                    "_points": list(zip(source_xs, source_ys, strict=False)),
                }
            )
    components.sort(key=lambda item: (int(item["area"]), int(item["dilated_area"])), reverse=True)
    return components


def _bbox_union(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not bboxes:
        return None
    return (
        min(item[0] for item in bboxes),
        min(item[1] for item in bboxes),
        max(item[2] for item in bboxes),
        max(item[3] for item in bboxes),
    )


def _paint_components(mask: np.ndarray, components: list[dict[str, Any]]) -> None:
    for component in components:
        for x, y in component.get("_points", []):
            mask[int(y), int(x)] = True


def _select_subject_mask(
    foreground_mask: np.ndarray,
    *,
    target_size: tuple[int, int],
) -> tuple[np.ndarray, tuple[int, int, int, int] | None, dict[str, Any]]:
    raw_bbox = _mask_bbox(foreground_mask)
    if raw_bbox is None:
        return foreground_mask.copy(), None, {
            "raw_bbox": None,
            "bbox": None,
            "component_count": 0,
            "kept_component_count": 0,
            "dropped_component_count": 0,
        }

    height, width = foreground_mask.shape
    scale = max(
        width / max(1, int(target_size[0])),
        height / max(1, int(target_size[1])),
        1.0,
    )
    crop_padding = max(2, min(12, int(round(2 * scale))))
    # 组件必须先按原始非背景色块识别，不能让小噪点在膨胀后成为“桥”，
    # 否则远处孤立紫点会被并入主体并撑大 bbox。
    components = _foreground_components(foreground_mask, foreground_mask)
    if not components:
        bbox = _expand_bbox(raw_bbox, padding=crop_padding, size=(width, height))
        return foreground_mask.copy(), bbox, {
            "raw_bbox": list(raw_bbox),
            "bbox": list(bbox),
            "crop_padding": crop_padding,
            "component_count": 0,
            "kept_component_count": 0,
            "dropped_component_count": 0,
        }

    main = components[0]
    main_area = max(1, int(main["area"]))
    significant_area = max(8, int(round(main_area * 0.025)))
    significant_gap = max(3, min(18, int(round(3 * scale))))
    small_gap = max(2, min(10, int(round(2 * scale))))
    min_small_area = 1

    significant = [component for component in components if int(component["area"]) >= significant_area]
    kept_significant: list[dict[str, Any]] = [main]
    frontier_bbox = main["bbox"]
    changed = True
    while changed:
        changed = False
        for component in significant:
            if component in kept_significant:
                continue
            if _bbox_distance(component["bbox"], frontier_bbox) <= significant_gap:
                kept_significant.append(component)
                union = _bbox_union([item["bbox"] for item in kept_significant])
                if union is not None:
                    frontier_bbox = union
                changed = True

    significant_bbox = _bbox_union([item["bbox"] for item in kept_significant]) or main["bbox"]
    kept: list[dict[str, Any]] = list(kept_significant)
    for component in components:
        if component in kept:
            continue
        area = int(component["area"])
        if area >= min_small_area and _bbox_distance(component["bbox"], significant_bbox) <= small_gap:
            # 小色块可以被主体轮廓吸附，但不会继续扩展 significant_bbox，避免噪点链条桥接。
            kept.append(component)

    selected = np.zeros_like(foreground_mask, dtype=bool)
    _paint_components(selected, kept)
    subject_bbox = _mask_bbox(selected) or significant_bbox
    bbox = _expand_bbox(subject_bbox, padding=crop_padding, size=(width, height))
    return selected, bbox, {
        "raw_bbox": list(raw_bbox),
        "subject_bbox": list(subject_bbox),
        "bbox": list(bbox),
        "crop_padding": crop_padding,
        "significant_area": significant_area,
        "significant_gap": significant_gap,
        "small_gap": small_gap,
        "component_count": len(components),
        "kept_component_count": len(kept),
        "dropped_component_count": max(0, len(components) - len(kept)),
        "top_components": [
            {"area": int(item["area"]), "bbox": list(item["bbox"])} for item in components[:8]
        ],
    }


def _keyframe_content(
    src_path: Path,
    *,
    target_size: tuple[int, int],
    key_rgb: tuple[int, int, int],
    key_tolerance: int,
    generated_preprocess_method: str | None,
) -> tuple[Image.Image, dict[str, Any]]:
    """把 AI 关键帧半图整理为透明主体内容。

    注意：这里是送入视频模型前的关键一步。不能直接把左右半图等比塞进视频画布，
    否则双栏图里的留白/分隔线/主体偏移会被 Ark 当作首尾帧内容。流程必须与
    mosaic cell 类似：perfectPixel 对齐 → key-color alpha → 基于主体轮廓裁剪。
    """
    with Image.open(src_path) as opened:
        source = opened.convert("RGBA")
    preprocessed = preprocess_generated_image(
        source,
        method=generated_preprocess_method,
        target_size=target_size,
    )
    alpha_image = apply_pixel_bg_alpha(
        preprocessed.image.convert("RGBA"),
        key_rgb=key_rgb,
        tolerance=max(0, int(key_tolerance)),
    )
    alpha = np.asarray(alpha_image.getchannel("A"), dtype=np.uint8)
    foreground_mask = alpha > 8
    subject_mask, bbox, selection_meta = _select_subject_mask(foreground_mask, target_size=target_size)
    if bbox is None:
        content = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    else:
        clean = alpha_image.copy()
        clean_alpha = np.asarray(clean.getchannel("A"), dtype=np.uint8).copy()
        clean_alpha[~subject_mask] = 0
        clean.putalpha(Image.fromarray(clean_alpha, mode="L"))
        content = clean.crop(bbox).convert("RGBA")
    return content, {
        "source": str(src_path.name),
        "source_size": list(source.size),
        "preprocess": preprocessed.meta,
        "bbox": list(bbox) if bbox else None,
        "selection": selection_meta,
        "content_size": list(content.size),
    }


def _prepare_video_keyframes(
    first_path: Path,
    last_path: Path,
    first_dest_path: Path,
    last_dest_path: Path,
    size: tuple[int, int],
    *,
    target_size: tuple[int, int],
    frame_size_step: int,
    anchor: str,
    key_rgb: tuple[int, int, int],
    key_tolerance: int,
    generated_preprocess_method: str | None,
) -> dict[str, Any]:
    first_content, first_meta = _keyframe_content(
        first_path,
        target_size=target_size,
        key_rgb=key_rgb,
        key_tolerance=key_tolerance,
        generated_preprocess_method=generated_preprocess_method,
    )
    last_content, last_meta = _keyframe_content(
        last_path,
        target_size=target_size,
        key_rgb=key_rgb,
        key_tolerance=key_tolerance,
        generated_preprocess_method=generated_preprocess_method,
    )
    content_padding = max(8, min(32, int(round(min(target_size) * 0.25))))
    normalized_size = (
        _ceil_to_multiple(
            max(target_size[0], first_content.width + content_padding * 2, last_content.width + content_padding * 2),
            frame_size_step,
        ),
        _ceil_to_multiple(
            max(target_size[1], first_content.height + content_padding * 2, last_content.height + content_padding * 2),
            frame_size_step,
        ),
    )
    first_normalized = _paste_keyframe_content_to_canvas(first_content, size=normalized_size, anchor=anchor)
    last_normalized = _paste_keyframe_content_to_canvas(last_content, size=normalized_size, anchor=anchor)
    first_fitted = _fit_to_canvas(first_normalized, size, key_rgb)
    last_fitted = _fit_to_canvas(last_normalized, size, key_rgb)
    first_dest_path.parent.mkdir(parents=True, exist_ok=True)
    first_fitted.save(first_dest_path)
    last_fitted.save(last_dest_path)
    return {
        "target_size": list(target_size),
        "normalized_size": list(normalized_size),
        "content_padding": content_padding,
        "video_input_size": list(size),
        "anchor": anchor,
        "key_tolerance": int(key_tolerance),
        "generated_preprocess_method": generated_preprocess_method,
        "first": first_meta,
        "last": last_meta,
    }


_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_LOOSE_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_text_parts(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


def _extract_chat_content(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        raise ValueError(f"VL 响应缺少 choices: {str(resp)[:500]}")
    message = choices[0].get("message") or {}
    content = _extract_text_parts(message.get("content"))
    if content:
        return content
    raise ValueError(f"无法解析 VL 响应 content: {str(resp)[:500]}")


def _extract_anthropic_content(resp: dict[str, Any]) -> str:
    content = _extract_text_parts(resp.get("content"))
    if content:
        return content
    raise ValueError(f"无法解析 Anthropic VL 响应 content: {str(resp)[:500]}")


def _anthropic_image_content(path: Path) -> dict[str, Any]:
    data_url = image_to_base64_data_url(path)
    header, _, data = data_url.partition(",")
    media_type = "image/png"
    if header.startswith("data:") and ";" in header:
        media_type = header[5:].split(";", 1)[0] or media_type
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _extract_motion_plan(raw: str) -> str:
    text = (raw or "").strip()
    json_block = _JSON_BLOCK_RE.search(text)
    if json_block:
        text = json_block.group(1).strip()
    else:
        loose = _LOOSE_JSON_RE.search(text)
        if loose:
            text = loose.group(0).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("VL motion prompt 响应不是 JSON 对象")
    plan = str(data.get("optimized_motion_plan") or data.get("motion_plan") or data.get("prompt") or "").strip()
    if not plan:
        raise ValueError("VL motion prompt 响应缺少 optimized_motion_plan")
    return " ".join(plan.split())[:1600]


def _motion_prompt_optimizer_instruction(
    *,
    description: str,
    action_prompt: str,
    base_prompt: str,
    frame_count: int,
    return_to_first_frame: bool = False,
) -> str:
    loop_instruction = (
        "The user enabled return_to_first_frame: the motion plan must explicitly reach the last_frame pose, then continue back to the first_frame pose so the final sampled frame matches first_frame for a loop-ready animation. "
        if return_to_first_frame
        else ""
    )
    return (
        "You are optimizing a video-generation prompt for a pixel-art sprite animation. "
        "Inspect the provided first_frame and last_frame images, then write a concise motion plan that helps the video model create fluid, coherent in-betweens. "
        "Do not override safety or product constraints. Preserve the subject identity and the exact start/end poses. "
        f"{loop_instruction}"
        "The plan must emphasize: continuous readable motion, evenly spaced intermediate poses, every sampled frame as crisp grid-aligned TRUE pixel art, no anti-aliasing, no blur, no painterly smoothing, fixed orthographic camera, no zoom/pan/cuts, and all subject parts/effects staying fully inside the frame with key-color padding. "
        "Pixel-block orientation rule: every visible pixel block must stay axis-aligned as horizontal/vertical square tiles on one upright pixel grid; never rotate, tilt, shear, skew, diamond-turn, or slant pixel blocks to fake motion. The motion plan should describe changes in whole square-pixel positions, silhouettes, and poses, not rotated pixel chunks. "
        "Pixel-boundary rule: only the flat key-color background is allowed to touch canvas edges; every non-background / non-key-color pixel is foreground and must remain inside the interior safe area with at least 10% key-color margin from every canvas edge, including stray particles, smoke wisps, weapon tips, shadows, highlights, trails, and effects. "
        "Mention weapons, cloak, smoke, particles, trails, and other moving parts only as controlled in-frame foreground elements that never touch or cross the boundary. "
        "Return JSON only, no Markdown, in this schema: {\"optimized_motion_plan\": \"one English paragraph under 1200 characters\"}.\n\n"
        f"Subject: {description}\n"
        f"User motion request: {action_prompt}\n"
        f"Target sampled sprite frames: {max(2, int(frame_count))}\n"
        f"Non-negotiable base prompt constraints to preserve:\n{base_prompt}"
    )


def _optimize_video_bridge_motion_prompt(
    cfg: AppConfig,
    *,
    description: str,
    action_prompt: str,
    base_prompt: str,
    first_frame_path: Path,
    last_frame_path: Path,
    frame_count: int,
    return_to_first_frame: bool = False,
) -> tuple[str, dict[str, Any]]:
    model = str(getattr(cfg.vision, "model", "") or "").strip()
    meta: dict[str, Any] = {
        "enabled": True,
        "used": False,
        "mode": "fallback",
        "model": model,
        "return_to_first_frame": bool(return_to_first_frame),
    }
    try:
        api_key = require_vl_api_key(cfg)
    except RuntimeError as exc:
        return base_prompt, {**meta, "mode": "unavailable", "error": str(exc)}

    client = make_packy_client(cfg, api_key)
    instruction = _motion_prompt_optimizer_instruction(
        description=description,
        action_prompt=action_prompt,
        base_prompt=base_prompt,
        frame_count=frame_count,
        return_to_first_frame=return_to_first_frame,
    )
    model_name = model or cfg.vision.model
    temperature = min(float(getattr(cfg.vision, "temperature", 0.2)), 0.2)
    max_tokens = max(600, min(int(getattr(cfg.vision, "max_tokens", 2048)), 1600))
    use_anthropic_protocol = "claude" in model_name.lower() or "anthropic" in model_name.lower()
    endpoint = "/v1/messages" if use_anthropic_protocol else "/v1/chat/completions"
    try:
        if use_anthropic_protocol:
            anthropic_payload: dict[str, Any] = {
                "model": model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            _anthropic_image_content(first_frame_path),
                            _anthropic_image_content(last_frame_path),
                        ],
                    }
                ],
            }
            raw = _extract_anthropic_content(client.post_json(endpoint, anthropic_payload))
        else:
            payload: dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {"type": "image_url", "image_url": {"url": image_to_base64_data_url(first_frame_path)}},
                            {"type": "image_url", "image_url": {"url": image_to_base64_data_url(last_frame_path)}},
                        ],
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            raw = _extract_chat_content(client.post_json(endpoint, payload))
        motion_plan = _extract_motion_plan(raw)
    except Exception as exc:  # noqa: BLE001 - 优化失败不能阻断视频任务
        return base_prompt, {**meta, "mode": "failed", "endpoint": endpoint, "error": str(exc)[:500]}

    optimized_prompt = f"{base_prompt} Optimized motion plan: {motion_plan}".strip()
    return optimized_prompt, {
        **meta,
        "used": True,
        "mode": "model",
        "endpoint": endpoint,
        "optimized_motion_plan": motion_plan,
    }


def _start_video_task(
    cfg: AppConfig,
    inputs: SpriteVideoBridgeInput,
    *,
    run_dir: Path,
    description: str,
    action_prompt: str,
    key_color: str,
    notify: ProgressCb,
) -> None:
    keyframe_pair_path = run_dir / "keyframe_pair.png"
    first_path = run_dir / "keyframes" / "first_frame.png"
    last_path = run_dir / "keyframes" / "last_frame.png"
    first_video_path = run_dir / "keyframes" / "first_frame_video.png"
    last_video_path = run_dir / "keyframes" / "last_frame_video.png"
    first_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _resolve_video_bridge_settings(
        cfg,
        inputs,
        description=description,
        action_prompt=action_prompt,
    )

    keyframe_prompt = build_video_bridge_keyframe_prompt(
        cfg,
        description,
        action_prompt,
        key_color=key_color,
        key_tolerance=settings.key_tolerance,
        frame_size=settings.target_size,
        max_colors=settings.max_colors,
        style_profile=inputs.style_profile,
    )
    clear_image_provider_history()
    with _local_stage(inputs.local_stage_context):
        notify("video_bridge_keyframes_start", {"run_dir": str(run_dir)})
        if inputs.reference_image_path is not None:
            edit_image(
                cfg,
                inputs.reference_image_path,
                keyframe_prompt,
                keyframe_pair_path,
                size=inputs.image_size or cfg.image_gen.size,
                quality=inputs.image_quality or cfg.sprite.image_quality,
                model=inputs.image_model,
                input_fidelity=cfg.image_gen.edit_input_fidelity,
            )
        else:
            generate_image(
                cfg,
                keyframe_prompt,
                keyframe_pair_path,
                size=inputs.image_size or cfg.image_gen.size,
                quality=inputs.image_quality or cfg.sprite.image_quality,
                model=inputs.image_model,
            )
        key_rgb = parse_hex_color(key_color)
        keyframe_split = _split_keyframes(
            keyframe_pair_path,
            first_path,
            last_path,
            key_rgb=key_rgb,
            key_tolerance=settings.key_tolerance,
        )
        video_size = _video_input_size(cfg)
        keyframe_preprocess = _prepare_video_keyframes(
            first_path,
            last_path,
            first_video_path,
            last_video_path,
            video_size,
            target_size=settings.target_size,
            frame_size_step=settings.frame_size_step,
            anchor=settings.anchor,
            key_rgb=key_rgb,
            key_tolerance=settings.key_tolerance,
            generated_preprocess_method=inputs.pixelize_params.generated_preprocess_method,
        )

    max_bytes = max(1, int(getattr(cfg.video_bridge, "max_base64_image_bytes", 30 * 1024 * 1024)))
    first_data_url = _data_url_from_png(first_video_path, max_bytes)
    last_data_url = _data_url_from_png(last_video_path, max_bytes)
    frame_count = max(2, int(settings.frame_count))
    timing_meta = video_bridge_timing_meta(frame_count, settings.duration_ms)
    ark_duration_seconds = int(timing_meta["ark_duration_seconds"])
    return_to_first_frame = bool(inputs.video_return_to_first_frame)
    ark_last_frame_data_url = first_data_url if return_to_first_frame else last_data_url
    ark_last_frame_source = "first_frame_video_path" if return_to_first_frame else "last_frame_video_path"
    base_motion_prompt = build_video_bridge_motion_prompt(
        description,
        action_prompt,
        frame_count=frame_count,
        frame_duration_ms=settings.duration_ms,
        video_duration_seconds=ark_duration_seconds,
        return_to_first_frame=return_to_first_frame,
        frame_size=settings.target_size,
        max_colors=settings.max_colors,
        key_color=key_color,
        key_tolerance=settings.key_tolerance,
    )
    motion_prompt, motion_prompt_optimizer = _optimize_video_bridge_motion_prompt(
        cfg,
        description=description,
        action_prompt=action_prompt,
        base_prompt=base_motion_prompt,
        first_frame_path=first_video_path,
        last_frame_path=last_video_path,
        frame_count=frame_count,
        return_to_first_frame=return_to_first_frame,
    )
    notify(
        "video_bridge_motion_prompt_ready",
        {"optimized": bool(motion_prompt_optimizer.get("used")), "timing": timing_meta},
    )
    client = ArkVideoClient(cfg)
    created = client.create_task(
        prompt=motion_prompt,
        first_frame_data_url=first_data_url,
        last_frame_data_url=ark_last_frame_data_url,
        model=cfg.video_bridge.model,
        resolution=cfg.video_bridge.resolution,
        ratio=cfg.video_bridge.ratio,
        duration=ark_duration_seconds,
        generate_audio=bool(cfg.video_bridge.generate_audio),
        watermark=bool(cfg.video_bridge.watermark),
    )
    state = {
        "kind": "video_bridge",
        "stage": "ark_waiting",
        "run_dir": str(run_dir),
        "created_at": _iso(_utcnow()),
        "next_poll_at": next_poll_at(cfg),
        "ark_task_id": created.id,
        "last_status": "created",
        "keyframe_prompt": keyframe_prompt,
        "motion_prompt": motion_prompt,
        "motion_prompt_base": base_motion_prompt,
        "motion_prompt_optimizer": motion_prompt_optimizer,
        "video_return_to_first_frame": return_to_first_frame,
        "ark_last_frame_source": ark_last_frame_source,
        "timing": timing_meta,
        "duration": ark_duration_seconds,
        "configured_duration": int(getattr(cfg.video_bridge, "duration", ark_duration_seconds) or ark_duration_seconds),
        "duration_source": "sprite_timing",
        "prompt_parameters": {
            "target_frame_size": list(settings.target_size),
            "colors": int(settings.max_colors),
            "green_screen_color": key_color,
            "green_screen_tolerance": int(settings.key_tolerance),
            "edge_style": settings.edge_style,
            "bg_feather": int(settings.bg_feather),
            "generated_preprocess_method": inputs.pixelize_params.generated_preprocess_method,
            "denoise": True,
        },
        "keyframe_pair_path": _rel(keyframe_pair_path, run_dir),
        "first_frame_path": _rel(first_path, run_dir),
        "last_frame_path": _rel(last_path, run_dir),
        "first_frame_video_path": _rel(first_video_path, run_dir),
        "last_frame_video_path": _rel(last_video_path, run_dir),
        "keyframe_split": keyframe_split,
        "keyframe_preprocess": keyframe_preprocess,
        "ark_create": created.raw,
        "provider_history": image_provider_history(),
    }
    _write_state(run_dir, state)
    raise VideoBridgeWaiting("Ark 视频补间任务已创建，等待生成完成", state=state, run_dir=run_dir)


def _poll_video_task(cfg: AppConfig, state: dict[str, Any], run_dir: Path) -> Path:
    if is_waiting_state_expired(state, cfg):
        raise TimeoutError("Ark 视频补间任务等待超时")
    task_id = str(state.get("ark_task_id") or "").strip()
    if not task_id:
        raise ValueError("video_bridge_state 缺少 ark_task_id")
    task = ArkVideoClient(cfg).get_task(task_id)
    state = {**state, "last_status": task.status, "ark_last": task.raw}
    if task.status in _WAITING_STATUSES:
        state["next_poll_at"] = next_poll_at(cfg)
        _write_state(run_dir, state)
        raise VideoBridgeWaiting(f"Ark 视频任务仍在 {task.status}", state=state, run_dir=run_dir)
    if task.status in _FAILED_STATUSES:
        message = task.error.get("message") if task.error else ""
        code = task.error.get("code") if task.error else ""
        raise RuntimeError(f"Ark 视频任务失败：{task.status} {code} {message}".strip())
    if task.status != "succeeded":
        state["next_poll_at"] = next_poll_at(cfg)
        _write_state(run_dir, state)
        raise VideoBridgeWaiting(f"Ark 视频任务状态 {task.status}，等待下一次查询", state=state, run_dir=run_dir)
    video_url = task.video_url
    if not video_url:
        raise RuntimeError("Ark 视频任务成功但未返回 video_url")
    video_path = run_dir / "ark_video.mp4"
    ArkVideoClient(cfg).download_video(video_url, video_path)
    state.update(
        {
            "stage": "video_downloaded",
            "video_path": _rel(video_path, run_dir),
            "video_url_cached_at": _iso(_utcnow()),
            "ark_succeeded": task.raw,
        }
    )
    _write_state(run_dir, state)
    return video_path


def _reader_frame_count(reader: Any) -> int | None:
    for name in ("count_frames", "get_length"):
        try:
            value = getattr(reader, name)()
        except Exception:  # noqa: BLE001 - reader 后端差异
            continue
        try:
            count = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if count > 0 and count < 10_000_000:
            return count
    return None


def _sample_indices(total: int, count: int) -> list[int]:
    safe_total = max(1, int(total))
    safe_count = max(1, int(count))
    if safe_count == 1:
        return [0]
    return [min(safe_total - 1, max(0, round(i * (safe_total - 1) / (safe_count - 1)))) for i in range(safe_count)]


def _extract_video_frames(video_path: Path, raw_dir: Path, frame_count: int) -> tuple[list[Path], dict[str, Any]]:
    import imageio.v2 as imageio

    raw_dir.mkdir(parents=True, exist_ok=True)
    reader = imageio.get_reader(str(video_path), "ffmpeg")
    meta: dict[str, Any] = {}
    try:
        meta = dict(reader.get_meta_data() or {})
    except Exception:  # noqa: BLE001
        meta = {}
    total = _reader_frame_count(reader)
    frame_paths: list[Path] = []
    samples: list[dict[str, Any]] = []
    try:
        if total is not None:
            indices = _sample_indices(total, frame_count)
            for out_index, frame_index in enumerate(indices, start=1):
                frame = reader.get_data(frame_index)
                path = raw_dir / f"frame_{out_index:03d}.png"
                Image.fromarray(np.asarray(frame)).convert("RGBA").save(path)
                frame_paths.append(path)
                samples.append({"index": out_index, "frame_index": int(frame_index)})
        else:
            frames = [np.asarray(frame) for frame in reader]
            if not frames:
                raise ValueError("视频中没有可抽取的帧")
            indices = _sample_indices(len(frames), frame_count)
            for out_index, frame_index in enumerate(indices, start=1):
                path = raw_dir / f"frame_{out_index:03d}.png"
                Image.fromarray(frames[frame_index]).convert("RGBA").save(path)
                frame_paths.append(path)
                samples.append({"index": out_index, "frame_index": int(frame_index)})
            total = len(frames)
    finally:
        reader.close()
    return frame_paths, {"meta": meta, "total_frames": total, "samples": samples}


def _union_bbox(bboxes: list[tuple[int, int, int, int] | None], fallback_size: tuple[int, int]) -> tuple[int, int, int, int]:
    present = [bbox for bbox in bboxes if bbox is not None]
    if not present:
        return (0, 0, int(fallback_size[0]), int(fallback_size[1]))
    return (
        min(b[0] for b in present),
        min(b[1] for b in present),
        max(b[2] for b in present),
        max(b[3] for b in present),
    )


def _preprocess_grid_from_meta(meta: Mapping[str, Any]) -> tuple[int, int] | None:
    for key in ("refined_size", "output_size", "grid_size"):
        value = meta.get(key)
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            continue
        try:
            grid = int(value[0]), int(value[1])
        except (TypeError, ValueError):
            continue
        if grid[0] > 0 and grid[1] > 0:
            return grid
    return None


def _mode_grid_size(grids: list[tuple[int, int]], target_size: tuple[int, int]) -> tuple[int, int] | None:
    if not grids:
        return None
    target = int(target_size[0]), int(target_size[1])
    counts = Counter(grids)
    return min(
        counts,
        key=lambda grid: (
            -counts[grid],
            abs(grid[0] - target[0]) + abs(grid[1] - target[1]),
            abs((grid[0] * grid[1]) - (target[0] * target[1])),
            grid,
        ),
    )


def _power_of_two_square_frame_size(
    required_size: tuple[int, int],
    *,
    target_size: tuple[int, int],
) -> tuple[int, int]:
    """把最终帧画布向上取整为 2 的幂方形尺寸，不缩放内容，只透明填充。"""
    side = next_power_of_two(
        max(
            1,
            int(required_size[0]),
            int(required_size[1]),
            int(target_size[0]),
            int(target_size[1]),
        )
    )
    return side, side


def _detect_sequence_perfect_pixel_grid(
    raw_frame_paths: list[Path],
    *,
    method: str | None,
    target_size: tuple[int, int],
) -> tuple[tuple[int, int] | None, list[dict[str, Any]]]:
    detections: list[dict[str, Any]] = []
    if (method or "").strip().lower().replace("-", "_") not in {"perfect", "perfectpixel", "perfect_pixel"}:
        return None, detections
    detected_grids: list[tuple[int, int]] = []
    for index, path in enumerate(raw_frame_paths, start=1):
        with Image.open(path) as opened:
            source = opened.convert("RGBA")
        result = preprocess_generated_image(source, method=method, target_size=target_size)
        grid = _preprocess_grid_from_meta(result.meta)
        if grid is not None:
            detected_grids.append(grid)
        detections.append(
            {
                "index": index,
                "source": path.name,
                "detected_grid_size": list(grid) if grid else None,
                "preprocess": result.meta,
            }
        )
    return _mode_grid_size(detected_grids, target_size), detections


def _apply_individual_palettes(
    images: list[Image.Image],
    *,
    colors: int,
    dither: str,
) -> tuple[list[Image.Image], list[list[str]]]:
    """共享调色板关闭时也强制每帧遵守颜色上限。"""
    quantized: list[Image.Image] = []
    palettes: list[list[str]] = []
    safe_colors = max(2, min(256, int(colors)))
    for image in images:
        palette_rgb = kmeans_palette(image, safe_colors)
        quantized.append(_quantize_with_palette(image, palette_rgb, dither=dither))
        palettes.append([rgb_to_hex(rgb) for rgb in palette_rgb])
    return quantized, palettes


def _process_frames(
    cfg: AppConfig,
    raw_frame_paths: list[Path],
    final_dir: Path,
    *,
    target_size: tuple[int, int],
    frame_size_step: int,
    anchor: str,
    key_rgb: tuple[int, int, int],
    key_tolerance: int,
    max_colors: int,
    dither: str,
    edge_style: str,
    bg_feather: int,
    generated_preprocess_method: str | None = "perfect_pixel",
) -> tuple[list[Path], list[tuple[int, int, int, int] | None], tuple[int, int], list[str], dict[str, Any]]:
    sequence_grid_size, grid_detections = _detect_sequence_perfect_pixel_grid(
        raw_frame_paths,
        method=generated_preprocess_method,
        target_size=target_size,
    )
    prepared: list[Image.Image] = []
    prepared_sizes: list[tuple[int, int]] = []
    bboxes: list[tuple[int, int, int, int] | None] = []
    frame_meta: list[dict[str, Any]] = []
    dropped_components = 0
    for index, path in enumerate(raw_frame_paths, start=1):
        with Image.open(path) as opened:
            source = opened.convert("RGBA")
        preprocessed = preprocess_generated_image(
            source,
            method=generated_preprocess_method,
            target_size=target_size,
            grid_size=sequence_grid_size,
        )
        # 与素材直出保持一致：perfectPixel 的输出尺寸应以检测/固定网格为准，
        # 不能再强行缩放回用户请求的 target_size，否则会把检测到的像素格重新压糊。
        normalized = preprocessed.image.convert("RGBA")
        frame_size = normalized.size
        transparent = apply_pixel_bg_alpha(normalized, key_rgb=key_rgb, tolerance=key_tolerance)
        alpha = np.asarray(transparent.getchannel("A"), dtype=np.uint8)
        foreground_mask = alpha > 8
        subject_mask, selection_bbox, selection_meta = _select_subject_mask(
            foreground_mask,
            target_size=frame_size,
        )
        clean = transparent.copy()
        clean_alpha = alpha.copy()
        clean_alpha[~subject_mask] = 0
        clean.putalpha(Image.fromarray(clean_alpha, mode="L"))
        bbox = selection_bbox if selection_bbox is not None else _visible_bbox(clean)
        prepared.append(clean)
        prepared_sizes.append(frame_size)
        bboxes.append(bbox)
        dropped_components += int(selection_meta.get("dropped_component_count") or 0)
        frame_meta.append(
            {
                "index": index,
                "source": path.name,
                "source_size": list(source.size),
                "preprocess": preprocessed.meta,
                "normalized_size": list(normalized.size),
                "denoise": {
                    "enabled": True,
                    "method": "connected_components_keep_main_subject",
                    "selection": selection_meta,
                },
                "bbox": list(bbox) if bbox else None,
            }
        )
    common_size = (
        max([int(target_size[0]), *(size[0] for size in prepared_sizes)]),
        max([int(target_size[1]), *(size[1] for size in prepared_sizes)]),
    )
    common_prepared: list[Image.Image] = []
    for image in prepared:
        if image.size == common_size:
            common_prepared.append(image)
            continue
        canvas = Image.new("RGBA", common_size, (0, 0, 0, 0))
        canvas.alpha_composite(image.convert("RGBA"), (0, 0))
        common_prepared.append(canvas)
    union = _union_bbox(bboxes, common_size)
    contents = [image.crop(union).convert("RGBA") for image in common_prepared]
    contents = _apply_frame_edges(contents, edge_style=edge_style, feather=bg_feather)
    frame_padding = max(2, min(8, int(round(min(common_size) * 0.08))))
    max_w = max([common_size[0], *(content.width + frame_padding * 2 for content in contents)])
    max_h = max([common_size[1], *(content.height + frame_padding * 2 for content in contents)])
    required_frame_size = (max_w, max_h)
    effective_size = _power_of_two_square_frame_size(required_frame_size, target_size=target_size)
    canvases = [
        _paste_final_frame_content_to_canvas(content, size=effective_size, anchor=anchor, padding=frame_padding)
        for content in contents
    ]
    palette: list[str] = []
    frame_palettes: list[list[str]] = []
    palette_mode = "none"
    if cfg.sprite.shared_palette:
        canvases, palette = _apply_shared_palette(canvases, colors=max_colors, dither=dither)
        palette_mode = "shared"
    else:
        canvases, frame_palettes = _apply_individual_palettes(canvases, colors=max_colors, dither=dither)
        palette_mode = "per_frame"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_paths: list[Path] = []
    for index, canvas in enumerate(canvases, start=1):
        path = final_dir / f"frame_{index:03d}.png"
        canvas.save(path)
        final_paths.append(path)
    return final_paths, bboxes, effective_size, palette, {
        "union_bbox": list(union),
        "frame_padding": frame_padding,
        "target_size": list(target_size),
        "common_preprocess_size": list(common_size),
        "required_frame_size": list(required_frame_size),
        "final_canvas_rule": "next_power_of_two_square_transparent_padding",
        "legacy_frame_size_step": int(frame_size_step),
        "preserve_perfect_pixel_detected_size": True,
        "generated_preprocess_method": generated_preprocess_method,
        "perfect_pixel_sequence_grid": {
            "enabled": bool(grid_detections),
            "strategy": "detect_all_frames_take_mode_then_reprocess_with_fixed_grid",
            "mode_grid_size": list(sequence_grid_size) if sequence_grid_size else None,
            "detections": grid_detections,
        },
        "denoise": {
            "enabled": True,
            "method": "connected_components_keep_main_subject",
            "dropped_component_count": dropped_components,
        },
        "palette_mode": palette_mode,
        "max_colors": int(max_colors),
        "shared_palette": bool(cfg.sprite.shared_palette),
        "frame_palettes": frame_palettes,
        "frames": frame_meta,
    }


def _finalize_outputs(
    cfg: AppConfig,
    inputs: SpriteVideoBridgeInput,
    *,
    run_dir: Path,
    video_path: Path,
    description: str,
    action_prompt: str,
    key_color: str,
    prompt_guard_meta: dict[str, Any],
    effective_prompt: str,
    notify: ProgressCb,
) -> SpritePipelineResult:
    mosaic_inputs = _mosaic_inputs_for_video_bridge(inputs, action_prompt=action_prompt)
    settings = _resolve_settings(cfg, mosaic_inputs, description)
    safe_row_prompts = _ensure_row_prompts(mosaic_inputs.row_prompts, settings.rows, action_prompt)
    raw_dir = run_dir / "frames" / "raw"
    final_dir = run_dir / "frames" / "final"
    sheet_path = run_dir / "sprite_sheet.png"
    sheet_grid_path = run_dir / "sprite_sheet_grid.png"
    sequence_path = run_dir / "sequence.json"
    gif_path = run_dir / "sprite.gif"
    keyframe_pair_path = run_dir / "keyframe_pair.png"

    notify("video_bridge_extract_start", {"video": str(video_path), "frame_count": settings.frame_count})
    raw_frame_paths, sampling_meta = _extract_video_frames(video_path, raw_dir, settings.frame_count)
    key_rgb = parse_hex_color(key_color)
    frame_paths, bboxes, effective_size, shared_palette_hex, process_meta = _process_frames(
        cfg,
        raw_frame_paths,
        final_dir,
        target_size=settings.target_size,
        frame_size_step=settings.frame_size_step,
        anchor=settings.anchor,
        key_rgb=key_rgb,
        key_tolerance=settings.key_tolerance,
        max_colors=settings.max_colors,
        dither=inputs.pixelize_params.dither,
        edge_style=settings.edge_style,
        bg_feather=settings.bg_feather,
        generated_preprocess_method=inputs.pixelize_params.generated_preprocess_method,
    )

    frames: list[SpriteFrame] = []
    for index, path in enumerate(frame_paths, start=1):
        row_index = (index - 1) // settings.cols
        frames.append(
            SpriteFrame(
                index=index,
                raw_path=raw_frame_paths[index - 1],
                reference_path=raw_frame_paths[index - 1],
                path=path,
                sheet_rect={
                    "x": (index - 1) * effective_size[0],
                    "y": 0,
                    "w": effective_size[0],
                    "h": effective_size[1],
                },
                action_phase=safe_row_prompts[row_index] if row_index < len(safe_row_prompts) else action_prompt,
                bbox=bboxes[index - 1],
            )
        )
    compose_horizontal_sprite_sheet(frame_paths, sheet_path)
    compose_grid_sprite_sheet(frame_paths, sheet_grid_path, rows=settings.rows, cols=settings.cols, frame_size=effective_size)
    preview_path: Path | None = None
    if settings.gif_export:
        compose_gif(frame_paths, gif_path, duration_ms=settings.duration_ms, loop=settings.loop)
        preview_path = gif_path

    rows_outputs = [
        {
            "row_index": row_index,
            "frame_indices": list(range(row_index * settings.cols + 1, row_index * settings.cols + settings.cols + 1)),
            "action_phase": safe_row_prompts[row_index] if row_index < len(safe_row_prompts) else action_prompt,
            "sheet": None,
            "gif": None,
        }
        for row_index in range(settings.rows)
    ]
    sequence = _build_sequence_json(
        sequence_path,
        run_dir=run_dir,
        frames=frames,
        settings=settings,
        effective_size=effective_size,
        sheet_path=sheet_path,
        mosaic_sheet_path=keyframe_pair_path,
        sheet_grid_path=sheet_grid_path,
        row_prompts=safe_row_prompts,
        rows_outputs=rows_outputs,
        billing=inputs.billing,
    )
    sequence["mode"] = "video_bridge"
    sequence["generation_mode"] = "video_bridge"
    sequence["source_video"] = _rel(video_path, run_dir)
    sequence_path.write_text(json.dumps(sequence, ensure_ascii=False, indent=2), encoding="utf-8")

    compiled_style = compile_style_profile(inputs.style_profile)
    frame_report = _frame_size_report(settings.target_size, effective_size)
    timing_meta = video_bridge_timing_meta(settings.frame_count, settings.duration_ms)
    state = _load_file_state(run_dir)
    meta = {
        "version": __version__,
        "input": {
            "prompt": inputs.prompt,
            "row_prompts": safe_row_prompts,
            "video_action_prompt": action_prompt,
            "video_return_to_first_frame": bool(inputs.video_return_to_first_frame),
            "style_profile": compiled_style.data,
            "applied_style_profile": compiled_style.applied_rules,
            "effective_prompt": effective_prompt,
        },
        "prompt_guard": prompt_guard_meta,
        "image_gen": {
            "model": inputs.image_model or cfg.image_gen.model,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.sprite.image_quality,
            "output_format": cfg.image_gen.output_format,
            "input_fidelity": cfg.image_gen.edit_input_fidelity,
            "used": True,
            "mode": "sprite_video_bridge_keyframes",
            "use_reference": inputs.reference_image_path is not None,
        },
        "video_bridge": {
            "provider": cfg.video_bridge.provider,
            "model": cfg.video_bridge.model,
            "resolution": cfg.video_bridge.resolution,
            "ratio": cfg.video_bridge.ratio,
            "duration": timing_meta["ark_duration_seconds"],
            "configured_duration": cfg.video_bridge.duration,
            "duration_source": "sprite_timing",
            "timing": timing_meta,
            "generate_audio": cfg.video_bridge.generate_audio,
            "watermark": cfg.video_bridge.watermark,
            "return_to_first_frame": bool(inputs.video_return_to_first_frame),
            "state": state,
            "video_path": _rel(video_path, run_dir),
            "keyframe_pair": _rel(keyframe_pair_path, run_dir),
            "sampling": sampling_meta,
            "processing": process_meta,
        },
        "sprite": {
            "type": "sequence_frames",
            "mode": "video_bridge",
            "generation_mode": "video_bridge",
            "rows": settings.rows,
            "cols": settings.cols,
            "frame_count": settings.frame_count,
            "max_frame_count": int(getattr(cfg.sprite, "max_frame_count", 64)),
            "fps": settings.fps,
            "duration_ms": settings.duration_ms,
            "loop": settings.loop,
            "target_frame_size": list(settings.target_size),
            "effective_frame_size": list(effective_size),
            "delivered_frame_size": frame_report["delivered_frame_size"],
            "frame_size_adapted": frame_report["frame_size_adapted"],
            "sheet_size": [effective_size[0] * len(frames), effective_size[1]],
            "colors": settings.max_colors,
            "anchor": settings.anchor,
            "green_screen_color": settings.key_color,
            "green_screen_tolerance": settings.key_tolerance,
            "frame_background_flow": _FRAME_BACKGROUND_FLOW,
            "postprocess_denoise": process_meta.get("denoise"),
            "generated_preprocess_method": inputs.pixelize_params.generated_preprocess_method,
            "palette_mode": process_meta.get("palette_mode"),
            "shared_palette": bool(cfg.sprite.shared_palette),
            "shared_palette_colors": shared_palette_hex,
            "row_prompts": safe_row_prompts,
            "video_action_prompt": action_prompt,
            "video_return_to_first_frame": bool(inputs.video_return_to_first_frame),
            "raw_frames_dir": _rel(raw_dir, run_dir),
            "frames_dir": _rel(final_dir, run_dir),
            "horizontal_sheet": sheet_path.name,
            "grid_sheet": sheet_grid_path.name,
            "sequence_json": sequence_path.name,
            "gif": gif_path.name if settings.gif_export else None,
            "frames": [_frame_metadata(frame, run_dir, cols=settings.cols, cell_meta=[]) for frame in frames],
            "rows_outputs": rows_outputs,
            "sequence": sequence,
            "billing": inputs.billing or None,
            "style_profile": compiled_style.data,
            "applied_style_profile": compiled_style.applied_rules,
            "use_reference": inputs.reference_image_path is not None,
        },
        "outputs": {
            "source": _rel(keyframe_pair_path, run_dir),
            "sprite_frames": _rel(final_dir, run_dir),
            "sprite_sheet": sheet_path.name,
            "sprite_sheet_grid": sheet_grid_path.name,
            "sprite_mosaic": keyframe_pair_path.name,
            "sequence_json": sequence_path.name,
            "sprite_gif": gif_path.name if settings.gif_export else None,
            "pixelized": sheet_path.name,
            "preview": _rel(preview_path, run_dir) if preview_path is not None else None,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return SpritePipelineResult(
        run_dir=run_dir,
        source_path=keyframe_pair_path,
        frame_paths=frame_paths,
        pixel_path=sheet_path,
        preview_path=preview_path,
        meta_path=meta_path,
        meta=meta,
    )


def run_sprite_video_bridge_pipeline(
    cfg: AppConfig,
    inputs: SpriteVideoBridgeInput,
    progress: ProgressCb | None = None,
) -> SpritePipelineResult:
    notify = progress or _noop
    prompt = (inputs.prompt or "").strip()
    if not prompt:
        raise ValueError("视频补间序列帧任务需要 prompt")
    if not getattr(cfg.video_bridge, "enabled", False):
        raise ValueError("首尾帧视频补间未启用，请先配置 pix.video_bridge.enabled")
    if not (getattr(cfg.video_bridge, "api_key", None) or "").strip():
        raise ValueError("首尾帧视频补间需要配置 Ark API Key")

    action_prompt = _action_prompt(inputs)
    style_text = style_profile_policy_text(inputs.style_profile)
    guard_text = "\n".join(part for part in [prompt, action_prompt, style_text] if part).strip()
    try:
        guard = validate_user_prompt(
            cfg,
            guard_text,
            allow_template_break=True,
            max_chars=_prompt_guard_max_chars(cfg),
        )
    except PromptPolicyError as exc:
        notify("prompt_guard_rejected", exc.result.to_metadata())
        raise ValueError(str(exc)) from exc
    prompt_guard_meta = guard.to_metadata()
    description = guard.normalized_description or prompt
    settings = _resolve_video_bridge_settings(
        cfg,
        inputs,
        description=description,
        action_prompt=action_prompt,
    )
    key_color = settings.key_color
    effective_prompt = build_video_bridge_keyframe_prompt(
        cfg,
        description,
        action_prompt,
        key_color=key_color,
        key_tolerance=settings.key_tolerance,
        frame_size=settings.target_size,
        max_colors=settings.max_colors,
        style_profile=inputs.style_profile,
    )

    state = dict(inputs.state or {})
    run_dir = Path(state.get("run_dir") or "") if state.get("run_dir") else None
    if run_dir is None:
        out_root = Path(inputs.out_root or cfg.output.root)
        run_dir = new_run_dir(out_root, seed=f"video_bridge\n{prompt}\n{action_prompt}")
        notify("video_bridge_run_start", {"run_dir": str(run_dir)})
        _start_video_task(
            cfg,
            inputs,
            run_dir=run_dir,
            description=description,
            action_prompt=action_prompt,
            key_color=key_color,
            notify=notify,
        )
    state = {**_load_file_state(run_dir), **state}
    video_path = run_dir / str(state.get("video_path") or "") if state.get("video_path") else None
    if video_path is None or not video_path.exists():
        video_path = _poll_video_task(cfg, state, run_dir)
    return _finalize_outputs(
        cfg,
        inputs,
        run_dir=run_dir,
        video_path=video_path,
        description=description,
        action_prompt=action_prompt,
        key_color=key_color,
        prompt_guard_meta=prompt_guard_meta,
        effective_prompt=effective_prompt,
        notify=notify,
    )
