"""Web Job 与 pix pipeline 的适配。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pix import __version__, dual_grid
from pix.api.image_dispatcher import clear_image_provider_history, image_provider_history
from pix.api.image_gen import (
    SizeRetryConfig,
    generate_image,
    last_size_retry_outcome,
    parse_size,
)
from pix.api.prompt_guard import PromptPolicyError, RAW_IMAGE_PROMPT_MAX_CHARS, validate_user_prompt
from pix.asset import build_asset_prompt, resolve_tile_texture_kind
from pix.config import AppConfig, load_config
from pix.contact_sheet import resolve_key_color
from pix.io_utils import file_lock, new_run_dir
from pix.pipeline import GridDesignInput, PipelineInput, PipelineResult, run_pipeline
from pix.pixelize.bg_removal import remove_background
from pix.pixelize.core import PixelizeParams
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.prompt_style import STYLE_PROFILE_POLICY_MAX_CHARS, compile_style_profile, style_profile_policy_text
from pix.sprite import SpritePipelineResult
from pix.sprite_mosaic import SpriteMosaicInput, run_sprite_mosaic_pipeline
from pix_web.config import WebSettings
from pix_web.models import GenerationJob


_LOCAL_STAGE_LOCK_TIMEOUT_SECONDS = 1800.0
_LOCAL_STAGE_LOCK_POLL_SECONDS = 0.1
_UI_COMPONENT_IMAGE_SIZE = "auto"


def _positive_limit(value: object, fallback: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def _raw_prompt_guard_max_chars(cfg: AppConfig | None) -> int | None:
    if cfg is None:
        return None
    return _positive_limit(cfg.image_gen.prompt_guard_max_chars, RAW_IMAGE_PROMPT_MAX_CHARS)


def _asset_prompt_guard_max_chars(cfg: AppConfig) -> int:
    return (
        _positive_limit(cfg.asset.subject_max_chars, 160)
        + _positive_limit(cfg.asset.extra_prompt_max_chars, RAW_IMAGE_PROMPT_MAX_CHARS)
        + STYLE_PROFILE_POLICY_MAX_CHARS
    )


def _dual_grid_prompt_guard_max_chars(cfg: AppConfig) -> int:
    return (_positive_limit(cfg.asset.subject_max_chars, 160) * 3) + STYLE_PROFILE_POLICY_MAX_CHARS


def _local_stage_context(settings: WebSettings):
    lock_path = settings.storage_root / ".locks" / "local-pipeline.lock"
    return lambda: file_lock(
        lock_path,
        timeout=_LOCAL_STAGE_LOCK_TIMEOUT_SECONDS,
        poll_interval=_LOCAL_STAGE_LOCK_POLL_SECONDS,
    )


def _as_fields(value: Any) -> set[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return None


def _value_from_json(
    data: dict[str, Any],
    key: str,
    fallback: Any,
    *,
    fields_key: str = "pixelize_fields",
    object_key: str = "pixelize",
) -> Any:
    values = data.get(object_key) or {}
    if not isinstance(values, dict):
        return fallback
    fields = _as_fields(data.get(fields_key))
    if fields is not None:
        return values.get(key, fallback) if key in fields else fallback
    return values.get(key, fallback)


def _request_includes(data: dict[str, Any], key: str) -> bool:
    fields = _as_fields(data.get("request_fields"))
    if fields is None:
        return key in data and data.get(key) is not None
    return key in fields


def _asset_image_size(data: dict[str, Any], cfg: AppConfig) -> str:
    image_size = data.get("image_size")
    if image_size:
        return str(image_size)
    asset = data.get("asset") or {}
    if isinstance(asset, dict) and str(asset.get("asset_kind") or "") == "ui_component":
        return _UI_COMPONENT_IMAGE_SIZE
    return cfg.image_gen.size


def _size_retry_enabled_from_job(data: dict[str, Any]) -> bool:
    asset = data.get("asset") or {}
    asset_kind = str(asset.get("asset_kind") or "") if isinstance(asset, dict) else ""
    if asset_kind in {"tile_texture", "dual_grid"}:
        # 平铺纹理/双瓦片依赖无缝边界，不能透明补边；避免外部 API 误触旧的 AI 画布尺寸重试。
        return False
    retry = data.get("size_retry")
    return bool(retry.get("enabled")) if isinstance(retry, dict) else False


def _size_retry_max_attempts_from_job(data: dict[str, Any]) -> int:
    retry = data.get("size_retry")
    if not isinstance(retry, dict):
        return 1
    try:
        return max(1, int(retry.get("max_attempts") or 1))
    except (TypeError, ValueError):
        return 1


def _merge_size_retry(*metas: dict[str, Any] | None) -> dict[str, Any] | None:
    """合并多次材质生成（如 dual_grid 的 A/B）的尺寸重试结果。

    actual_attempts / max_attempts 累加；matched 取「全部命中」；任一命中宽高比类协议则标注。
    用于 worker 按总尝试次数结算计费。
    """
    present = [m for m in metas if isinstance(m, dict) and m.get("enabled")]
    if not present:
        return None
    return {
        "enabled": True,
        "max_attempts": sum(int(m.get("max_attempts") or 1) for m in present),
        "actual_attempts": sum(int(m.get("actual_attempts") or 1) for m in present),
        "matched": all(bool(m.get("matched")) for m in present),
        "expected_size": present[0].get("expected_size"),
        "actual_size": present[-1].get("actual_size"),
        "aspect_ratio_protocol": any(bool(m.get("aspect_ratio_protocol")) for m in present),
        "materials": present,
    }


def pixelize_params_from_json(data: dict[str, Any]) -> PixelizeParams:
    pix = data.get("pixelize") or {}
    output_size = pix.get("output_size") or (128, 128)
    return PixelizeParams(
        output_size=(int(output_size[0]), int(output_size[1])),
        colors=int(pix.get("colors", 16)),
        dither=str(pix.get("dither", "floyd_steinberg")),  # type: ignore[arg-type]
        preset=str(pix.get("preset", "auto")),
        preview_scale=int(pix.get("preview_scale", 4)),
        edge_enhance=float(pix.get("edge_enhance", 0.1)),
        saturation=float(pix.get("saturation", 1.0)),
        resample=str(pix.get("resample", "smart")),  # type: ignore[arg-type]
        snap_to_grid=bool(pix.get("snap_to_grid", True)),
        remove_bg=bool(pix.get("remove_bg", False)),
        bg_tolerance=int(pix.get("bg_tolerance", 12)),
        bg_feather=int(pix.get("bg_feather", 0)),
        edge_style=str(pix.get("edge_style", "hard")),  # type: ignore[arg-type]
        bg_removal_algorithm=str(pix.get("bg_removal_algorithm", "pixel_bg")),
        auto_crop=bool(pix.get("auto_crop", False)),
        crop_padding=float(pix.get("crop_padding", 0.12)),
        crop_square=bool(pix.get("crop_square", True)),
        palette_mode=str(pix.get("palette_mode", "auto")),  # type: ignore[arg-type]
        generated_preprocess_method=str(pix.get("generated_preprocess_method", "perfect_pixel")),  # type: ignore[arg-type]
    )


def asset_pixelize_params_from_json(data: dict[str, Any], cfg: AppConfig) -> PixelizeParams:
    output_size = _value_from_json(data, "output_size", cfg.asset.pixel_size)
    asset = data.get("asset") or {}
    no_preview = bool(asset.get("no_preview", False)) if isinstance(asset, dict) else False
    preview_scale = (
        0 if no_preview else int(_value_from_json(data, "preview_scale", cfg.asset.preview_scale))
    )
    return PixelizeParams(
        output_size=(int(output_size[0]), int(output_size[1])),
        colors=int(_value_from_json(data, "colors", cfg.asset.colors)),
        dither=str(_value_from_json(data, "dither", cfg.asset.dither)),  # type: ignore[arg-type]
        preset=str(_value_from_json(data, "preset", "auto")),
        preview_scale=preview_scale,
        edge_enhance=float(_value_from_json(data, "edge_enhance", cfg.pixelize.edge_enhance)),
        saturation=float(_value_from_json(data, "saturation", cfg.pixelize.saturation)),
        resample=str(_value_from_json(data, "resample", cfg.pixelize.resample)),  # type: ignore[arg-type]
        snap_to_grid=bool(_value_from_json(data, "snap_to_grid", cfg.pixelize.snap_to_grid)),
        remove_bg=bool(_value_from_json(data, "remove_bg", cfg.asset.remove_bg)),
        bg_tolerance=int(_value_from_json(data, "bg_tolerance", cfg.asset.bg_tolerance)),
        bg_feather=int(_value_from_json(data, "bg_feather", cfg.asset.bg_feather)),
        edge_style=str(_value_from_json(data, "edge_style", cfg.asset.edge_style)),  # type: ignore[arg-type]
        bg_removal_algorithm=str(
            _value_from_json(data, "bg_removal_algorithm", cfg.asset.bg_removal_algorithm)
        ),
        auto_crop=bool(_value_from_json(data, "auto_crop", cfg.asset.auto_crop)),
        crop_padding=float(_value_from_json(data, "crop_padding", cfg.asset.crop_padding)),
        crop_square=bool(_value_from_json(data, "crop_square", cfg.asset.crop_square)),
        palette_mode=str(_value_from_json(data, "palette_mode", cfg.asset.palette_mode)),  # type: ignore[arg-type]
        generated_preprocess_method=str(
            _value_from_json(
                data, "generated_preprocess_method", cfg.pixelize.generated_preprocess_method
            )
        ),  # type: ignore[arg-type]
    )


def grid_design_from_json(data: dict[str, Any]) -> GridDesignInput:
    grid = data.get("grid") or {}
    return GridDesignInput(
        mode=str(grid.get("mode", "off")),  # type: ignore[arg-type]
    )


def asset_grid_design_from_json(data: dict[str, Any], cfg: AppConfig) -> GridDesignInput:
    if _request_includes(data, "grid"):
        return grid_design_from_json(data)
    return GridDesignInput(mode="extract" if cfg.asset.grid_mode else "off")


def bg_removal_options_from_params(cfg: AppConfig, params: PixelizeParams) -> dict[str, Any]:
    asset = getattr(cfg, "asset", None)
    options: dict[str, Any] = {
        "bg_removal_algorithm": "pixel_bg",
        "color_to_alpha_shape": "sphere",
        "color_to_alpha_transparency": 48,
        "color_to_alpha_opacity": 255,
        "color_to_alpha_interpolation": "linear",
    }
    if asset is not None:
        options.update(
            {
                "bg_removal_algorithm": getattr(asset, "bg_removal_algorithm", "pixel_bg"),
                "color_to_alpha_shape": getattr(asset, "color_to_alpha_shape", "sphere"),
                "color_to_alpha_transparency": getattr(asset, "color_to_alpha_transparency", 48),
                "color_to_alpha_opacity": getattr(asset, "color_to_alpha_opacity", 255),
                "color_to_alpha_interpolation": getattr(asset, "color_to_alpha_interpolation", "linear"),
            }
        )
    if params.bg_removal_algorithm:
        options["bg_removal_algorithm"] = params.bg_removal_algorithm
    return options


def _asset_data(job: GenerationJob) -> dict[str, Any]:
    data = job.params_json or {}
    asset = data.get("asset") or {}
    return asset if isinstance(asset, dict) else {}


def _style_profile_data(job: GenerationJob) -> dict[str, Any]:
    data = job.params_json or {}
    style_profile = data.get("style_profile") or {}
    return style_profile if isinstance(style_profile, dict) else {}


def _asset_name(job: GenerationJob) -> str:
    asset = _asset_data(job)
    return str(asset.get("name") or job.prompt or "").strip()


def _asset_skip_vl(data: dict[str, Any], cfg: AppConfig) -> bool:
    asset = data.get("asset") or {}
    use_vl = asset.get("use_vl") if isinstance(asset, dict) else None
    if use_vl is not None:
        return not bool(use_vl)
    if _request_includes(data, "skip_vl"):
        return bool(data.get("skip_vl", False))
    return bool(cfg.asset.skip_vl)


def _asset_reference_prompt_appendix(asset_kind: str, has_reference: bool) -> str:
    if not has_reference:
        return ""
    if asset_kind == "tile_texture":
        return (
            "Use the provided reference image only as material and style inspiration for a seamless tile texture. "
            "Do not trace, crop, upscale, or preserve a centered subject from the reference. The final image must remain "
            "an edge-to-edge TRUE pixel-art tileable pattern: no transparent background, no padding, no border, and all "
            "four edges must connect seamlessly when repeated."
        )
    if asset_kind == "game_logo":
        return (
            "Use the provided reference image as logo inspiration: first reinterpret it in the same TRUE pixel-art vocabulary "
            "(large square pixels, hard edges, limited palette), then preserve its emblem silhouette, "
            "shape language, main color mood, stroke rhythm, and lettering attitude where useful, "
            "but redesign it as a clean pixel-art game logo. The final readable text must only use "
            "the exact title, acronym, or brand text from the Subject; do not copy or invent any extra words from the reference."
        )
    return (
        "Use the provided reference image only as visual input for an asset redraw. First convert the reference mentally into "
        "a clean TRUE pixel-art interpretation with large square pixels, hard edges, a limited palette, and a simple silhouette; "
        "then apply the asset brief above as the authority for subject, size, palette limit, background, and forbidden elements. "
        "Do not simply trace, upscale, posterize, or pixelize the uploaded image. Redesign it as a fresh centered game asset; "
        "keep only useful composition, silhouette, material cues, and color mood from the reference. For ordinary item icons "
        "and UI components, do not copy readable text, labels, paragraphs, or tiny details from the reference."
    )


def pipeline_input_from_job(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig | None = None
) -> PipelineInput:
    data = job.params_json or {}
    image_path = Path(job.input_image_path) if job.input_image_path else None
    out_root = settings.storage_root / "runs" / f"job-{job.id}"
    # local_pixelize 的输入通常来自作品库候选、上传后的本地重处理或前端复用源图；
    # 语义上应按“已生成源图”走 perfect pixel / 去背景 / 裁切等后处理，而不是普通上传 legacy 路径。
    input_is_generated_source = job.job_type == "local_pixelize"

    return PipelineInput(
        prompt=job.prompt,
        prompt_guard_max_chars=_raw_prompt_guard_max_chars(cfg),
        image_path=image_path,
        image_size=data.get("image_size"),
        image_quality=data.get("image_quality"),
        image_model=data.get("image_model"),
        vl_model=data.get("vl_model"),
        skip_vl=bool(data.get("skip_vl", False)),
        pixelize_params=pixelize_params_from_json(data),
        grid=grid_design_from_json(data),
        source_only=bool(data.get("source_only", False)),
        out_root=out_root,
        use_cache=False,
        refresh_cache=False,
        local_stage_context=_local_stage_context(settings),
        input_is_generated_source=input_is_generated_source,
        size_retry_enabled=_size_retry_enabled_from_job(data),
        size_retry_max_attempts=_size_retry_max_attempts_from_job(data),
    )


# 参考图微调注入：声明上传的参考图即“图1”，让用户在 prompt 里写“图1 / 参考图”有明确指代。
RAW_REFERENCE_IMAGE_ALIAS = (
    'The uploaded reference image is also called 图1 ("image 1"); whenever the brief mentions '
    "图1, 图一, or 参考图, it refers to this uploaded reference image."
)


def image_to_image_pipeline_input_from_job(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig
) -> PipelineInput:
    """参考图微调（image_to_image）：复用素材直出的像素风 prompt，把上传图当参考图重绘成像素风。

    与素材直出共用 build_asset_prompt + 参考图 appendix，用户原始 prompt 作为 Subject；
    可由 cfg.image_gen.image_to_image_pixel_prompt 关闭，关闭后回退原始 prompt 直传。
    """
    base = pipeline_input_from_job(job, settings, cfg)
    user_prompt = (job.prompt or "").strip()
    # source_only 的 image_to_image 是“原生出图”（RawImagePage 参考图→大图，跳过像素化），
    # 不应套用像素风模板；仅对会进入像素化的参考图微调注入。
    if not cfg.image_gen.image_to_image_pixel_prompt or not user_prompt or base.source_only:
        return base

    params = base.pixelize_params
    # 复用原作品的素材类型：参考图微调本质是“按原素材规则重绘”，写死 item_icon 会让
    # UI 组件 / Logo / 平铺纹理 都被当成物品图标。build_asset_prompt 内部会校验并纠正
    # 非法 asset_kind / 不匹配的 subject_kind，缺省时回退物品图标。
    asset = _asset_data(job)
    asset_kind = str(asset.get("asset_kind") or "item_icon")
    subject_kind = str(asset.get("subject_kind") or "single_prop")
    texture_kind = str(asset.get("texture_kind") or "auto")
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, user_prompt)
    prompt = build_asset_prompt(
        cfg.asset.prompt_template,
        user_prompt,
        size=params.output_size,
        asset_kind=asset_kind,
        subject_kind=subject_kind,
        texture_kind=texture_kind,
        key_color=key_hex,
        key_tolerance=cfg.image_gen.green_screen_tolerance,
        max_colors=params.colors,
        style_profile=_style_profile_data(job),
    )
    reference_appendix = _asset_reference_prompt_appendix(asset_kind, base.image_path is not None)
    if reference_appendix:
        prompt = f"{prompt} {reference_appendix}"
    prompt = f"{prompt} {RAW_REFERENCE_IMAGE_ALIAS}"
    # prompt_guard_text 仍只审核用户原文与用户可控风格档案，而不是我们注入的模板。
    style_text = style_profile_policy_text(_style_profile_data(job))
    guard_text = "\n".join(part for part in [user_prompt, style_text] if part)
    return replace(base, prompt=prompt.strip(), prompt_guard_text=guard_text)


def asset_pipeline_input_from_job(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig
) -> PipelineInput:
    data = job.params_json or {}
    asset = _asset_data(job)
    name = _asset_name(job)
    params = asset_pixelize_params_from_json(data, cfg)
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, name)
    asset_kind = str(asset.get("asset_kind") or "item_icon")
    texture_kind = str(asset.get("texture_kind") or "auto")
    image_path = Path(job.input_image_path) if job.input_image_path else None
    prompt = build_asset_prompt(
        cfg.asset.prompt_template,
        name,
        size=params.output_size,
        extra_prompt=str(asset.get("extra_prompt") or ""),
        asset_kind=asset_kind,
        subject_kind=str(asset.get("subject_kind") or "single_prop"),
        texture_kind=texture_kind,
        key_color=key_hex,
        key_tolerance=cfg.image_gen.green_screen_tolerance,
        max_colors=params.colors,
        style_profile=_style_profile_data(job),
    )
    reference_appendix = _asset_reference_prompt_appendix(asset_kind, image_path is not None)
    if reference_appendix:
        prompt = f"{prompt} {reference_appendix}"
    image_quality = (
        data.get("image_quality")
        if _request_includes(data, "image_quality")
        else cfg.asset.image_quality
    )
    user_prompt_parts = [
        name,
        str(asset.get("extra_prompt") or "").strip(),
        style_profile_policy_text(_style_profile_data(job)),
    ]
    prompt_guard_text = "\n".join(part for part in user_prompt_parts if part)
    return PipelineInput(
        prompt=prompt,
        prompt_guard_text=prompt_guard_text,
        prompt_guard_max_chars=_asset_prompt_guard_max_chars(cfg),
        image_path=image_path,
        image_size=_asset_image_size(data, cfg),
        image_quality=image_quality,
        image_model=data.get("image_model"),
        vl_model=data.get("vl_model"),
        skip_vl=_asset_skip_vl(data, cfg),
        pixelize_params=params,
        grid=asset_grid_design_from_json(data, cfg),
        out_root=settings.storage_root / "runs" / f"job-{job.id}",
        use_cache=False,
        refresh_cache=False,
        local_stage_context=_local_stage_context(settings),
        # 素材直出尊重 perfectPixel 检测出的真实像素网格（不强制缩放回 output_size），
        # 再由 pipeline 填充到 2 的幂标准尺寸，避免把 AI 细节缩糊。
        input_is_generated_source=True,
        size_retry_enabled=_size_retry_enabled_from_job(data),
        size_retry_max_attempts=_size_retry_max_attempts_from_job(data),
    )


def sprite_mosaic_input_from_job(job: GenerationJob, settings: WebSettings) -> SpriteMosaicInput:
    data = job.params_json or {}
    sprite = data.get("sprite") or {}
    out_root = settings.storage_root / "runs" / f"job-{job.id}"
    raw_row_prompts = sprite.get("row_prompts") or []
    if not isinstance(raw_row_prompts, list):
        raw_row_prompts = []
    row_prompts = [str(item) for item in raw_row_prompts]
    reference_path_value = sprite.get("reference_image_path")
    reference_path = Path(reference_path_value) if reference_path_value else None
    return SpriteMosaicInput(
        prompt=job.prompt or "",
        rows=int(sprite.get("rows", 1)),
        cols=int(sprite.get("cols", 1)),
        row_prompts=row_prompts,
        reference_image_path=reference_path,
        image_size=data.get("image_size"),
        image_quality=data.get("image_quality"),
        image_model=data.get("image_model"),
        pixelize_params=pixelize_params_from_json(data),
        out_root=out_root,
        use_cache=False,
        refresh_cache=False,
        fps=int(sprite.get("fps", 8)),
        duration_ms=int(sprite.get("duration_ms", 0)) or None,
        loop=int(sprite.get("loop", 0)),
        gif_export=bool(sprite.get("gif_export", False)),
        key_tolerance=sprite.get("key_tolerance"),
        billing=data.get("billing") if isinstance(data.get("billing"), dict) else None,
        style_profile=_style_profile_data(job),
        local_stage_context=_local_stage_context(settings),
    )


def _write_asset_meta(result: PipelineResult, job: GenerationJob, inputs: PipelineInput) -> None:
    data = job.params_json or {}
    asset = _asset_data(job)
    name = _asset_name(job)
    extra_prompt = str(asset.get("extra_prompt") or "")
    asset_kind = str(asset.get("asset_kind") or "item_icon")
    requested_texture_kind = str(asset.get("texture_kind") or "auto")
    resolved_texture_kind = (
        resolve_tile_texture_kind(requested_texture_kind, name=name, extra_prompt=extra_prompt)
        if asset_kind == "tile_texture"
        else None
    )
    compiled_style = compile_style_profile(_style_profile_data(job))
    result.meta["asset"] = {
        "name": name,
        "extra_prompt": extra_prompt,
        "asset_kind": asset_kind,
        "subject_kind": str(asset.get("subject_kind") or "single_prop"),
        "texture_kind": requested_texture_kind if asset_kind == "tile_texture" else None,
        "requested_texture_kind": requested_texture_kind if asset_kind == "tile_texture" else None,
        "resolved_texture_kind": resolved_texture_kind,
        "prompt": inputs.prompt,
        "grid_mode": inputs.grid.mode,
        "pixel_size": list(inputs.pixelize_params.output_size),
        "colors": inputs.pixelize_params.colors,
        "palette_mode": inputs.pixelize_params.palette_mode,
        "generated_preprocess_method": inputs.pixelize_params.generated_preprocess_method,
        "preview_scale": inputs.pixelize_params.preview_scale,
        "skip_vl": inputs.skip_vl,
        "no_preview": bool(asset.get("no_preview", False)),
        "reference_image_path": str(inputs.image_path) if inputs.image_path else None,
        "reference_mode": "image_edit" if inputs.image_path else None,
        "style_profile": compiled_style.data,
        "applied_style_profile": compiled_style.applied_rules,
        "request_fields": data.get("request_fields") or [],
        "pixelize_fields": data.get("pixelize_fields") or [],
    }
    result.meta_path.write_text(
        json.dumps(result.meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _final_pixel_size_from_result(result: PipelineResult) -> tuple[int, int] | None:
    """从 pipeline 结果 meta 读填充后的成品像素尺寸。"""
    pm = (result.meta or {}).get("pixelize") or {}
    pad = pm.get("pad_to_power_of_two") or {}
    fs = pad.get("final_size")
    if isinstance(fs, (list, tuple)) and len(fs) == 2:
        return (int(fs[0]), int(fs[1]))
    eff = pm.get("effective_params") or {}
    os_ = eff.get("output_size")
    if isinstance(os_, (list, tuple)) and len(os_) == 2:
        return (int(os_[0]), int(os_[1]))
    try:
        with Image.open(result.pixel_path) as opened:
            return (int(opened.width), int(opened.height))
    except Exception:  # noqa: BLE001 - meta 兜底失败时不影响任务成功
        return None


def _size_retry_attempt_record(
    *,
    attempt: int,
    result: PipelineResult,
    target: tuple[int, int],
) -> dict[str, Any]:
    """记录一次尺寸重试尝试，供最终 meta/API 展示为可选候选。"""
    final_size = _final_pixel_size_from_result(result)
    matched = final_size == target
    return {
        "index": attempt,
        "attempt": attempt,
        "path": str(result.pixel_path),
        "source_path": str(result.source_path),
        "pixelized_path": str(result.pixel_path),
        "preview_path": str(result.preview_path) if result.preview_path else None,
        "meta_json_path": str(result.meta_path),
        "final_size": list(final_size) if final_size else None,
        "target_size": list(target),
        "matched": matched,
        "selected": False,
    }


def run_asset_job_pipeline(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig
) -> PipelineResult:
    asset_cfg = deepcopy(cfg)
    asset_cfg.image_gen.contact_sheet_enabled = False
    asset_cfg.image_gen.prompt_guard_remote = False
    inputs = asset_pipeline_input_from_job(job, settings, asset_cfg)

    target = tuple(inputs.pixelize_params.output_size)
    # 尺寸重试：填充后的成品标准尺寸 ≠ 用户目标时，刷新缓存重走生图，直到命中或耗尽次数。
    # 每次尝试的 run_dir 都保留，并在最终 meta 里暴露为候选，供用户自行选择。
    max_attempts = max(1, inputs.size_retry_max_attempts) if inputs.size_retry_enabled else 1
    result: PipelineResult | None = None
    attempt_records: list[dict[str, Any]] = []
    matched = False
    for attempt in range(1, max_attempts + 1):
        attempt_inputs = replace(inputs, refresh_cache=(attempt > 1)) if attempt > 1 else inputs
        result = run_pipeline(asset_cfg, attempt_inputs)
        record = _size_retry_attempt_record(attempt=attempt, result=result, target=target)
        attempt_records.append(record)
        if max_attempts == 1 or record["matched"]:
            matched = bool(record["matched"])
            break
    assert result is not None
    if inputs.size_retry_enabled:
        selected_index = len(attempt_records)
        for record in attempt_records:
            record["selected"] = int(record["attempt"] or 0) == selected_index
        final_size = _final_pixel_size_from_result(result)
        result.meta.setdefault("image_gen", {})["size_retry"] = {
            "enabled": True,
            "max_attempts": max_attempts,
            "actual_attempts": len(attempt_records),
            "matched": matched,
            "expected_size": list(target),
            "actual_size": list(final_size) if final_size else None,
            "target_size": list(target),
            "final_size": list(final_size) if final_size else None,
            "attempts": attempt_records,
        }
    _write_asset_meta(result, job, inputs)
    return result


@dataclass(frozen=True)
class _TileMaterial:
    """`_generate_tile_material` 的产物：完美像素化后的纹理 + 复用所需的元信息。

    `pixel_path` 即落盘的纹理图（tile_texture 用作最终产物，dual_grid 用作材质源）。
    其余字段让调用方原样复现各自的 meta，无需重新推断或再开图。
    """

    pixel_path: Path
    raw_path: Path
    prompt: str
    preprocess_meta: dict[str, Any]
    width: int
    height: int
    size_retry: dict[str, Any] | None = None


def _generate_tile_material(
    asset_cfg: AppConfig,
    *,
    name: str,
    extra_prompt: str,
    texture_kind: str,
    size: tuple[int, int],
    max_colors: int,
    generated_preprocess_method: str,
    image_size: str,
    image_quality: str | None,
    image_model: str | None,
    raw_path: Path,
    pixel_path: Path,
    size_retry_enabled: bool = False,
    size_retry_max_attempts: int = 1,
    style_profile: dict[str, Any] | None = None,
) -> _TileMaterial:
    """单张无缝纹理生成：prompt 构造 → generate_image → perfect_pixel → 落到 (w,h)。

    由 `run_tile_asset_job_pipeline`（单材质）与 `run_dual_grid_asset_job_pipeline`
    （材质 A/B 各一次）复用。**行为与原 tile pipeline 内联实现逐字一致**：同样的
    prompt 规则、同样的 perfect_pixel 调用、同样的兜底缩放判定（`max_colors` /
    `generated_preprocess_method` 由调用方传入已解析的请求值，而非从 cfg 再推断）。
    调用方负责生图前的 `clear_image_provider_history()` 与 `_local_stage_context` 上锁。
    """
    width, height = int(size[0]), int(size[1])
    prompt = build_asset_prompt(
        asset_cfg.asset.prompt_template,
        name,
        size=(width, height),
        extra_prompt=extra_prompt,
        asset_kind="tile_texture",
        subject_kind="tileable_pattern",
        texture_kind=texture_kind,
        max_colors=max_colors,
        style_profile=style_profile,
    )
    expected = parse_size(image_size)
    size_retry = (
        SizeRetryConfig(
            enabled=True,
            max_attempts=max(1, size_retry_max_attempts),
            expected_size=expected,
        )
        if size_retry_enabled and expected is not None
        else None
    )
    generate_image(
        asset_cfg,
        prompt,
        raw_path,
        size=image_size,
        quality=image_quality,
        model=image_model,
        size_retry=size_retry,
    )
    outcome = last_size_retry_outcome()
    size_retry_meta = outcome.to_metadata() if outcome is not None and outcome.enabled else None

    # 完美像素：让 perfectPixel 自动检测网格作为主导，target_size 仅作为提示。
    # 用户面板上选择的"目标尺寸"被理解为"输出 ≤ 目标尺寸的最小整数倍"，避免在
    # perfect_pixel 已经精确网格对齐的结果上再做一次破坏性的 NEAREST 缩放。
    with Image.open(raw_path) as opened:
        source_image = opened.convert("RGBA")
    preprocessed = preprocess_generated_image(
        source_image,
        method=generated_preprocess_method or "perfect_pixel",
        target_size=(width, height),
    )
    refined = preprocessed.image.convert("RGB")
    # 仅当 perfect_pixel 完全没生效（fallback 到原图 1024+）时才需要做兜底缩放。
    # 正常情况下 perfectPixel 输出会落在 32~256 的网格尺寸，直接采用即可——
    # 这与 theamusing/perfectPixel webdemo 的体验一致。
    applied = bool(preprocessed.meta.get("applied"))
    max_safe_side = max(512, max(width, height) * 8)
    if not applied or max(refined.size) > max_safe_side:
        # perfect_pixel 没生效（或输出仍接近原图），退化到目标尺寸
        final_image = (
            refined.resize((width, height), Image.NEAREST)
            if refined.size != (width, height)
            else refined
        )
    else:
        final_image = refined

    final_image.save(pixel_path)
    return _TileMaterial(
        pixel_path=pixel_path,
        raw_path=raw_path,
        prompt=prompt,
        preprocess_meta=preprocessed.meta,
        width=final_image.width,
        height=final_image.height,
        size_retry=size_retry_meta,
    )


def run_tile_asset_job_pipeline(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig
) -> PipelineResult:
    """平铺纹理专用最小 pipeline：1 次生图 → perfect_pixel → 落盘。

    跳过候选生成、VL 评分、grid extract、chroma-key 抠色、auto_crop 与共享调色板等
    所有针对"主体居中 + 透明背景"的素材后处理；输出物即"完美像素化后的源图"。
    """
    start = time.time()
    asset_cfg = deepcopy(cfg)
    asset_cfg.image_gen.contact_sheet_enabled = False
    asset_cfg.image_gen.prompt_guard_remote = False

    data = job.params_json or {}
    asset = _asset_data(job)
    name = _asset_name(job)
    params = asset_pixelize_params_from_json(data, asset_cfg)
    width, height = int(params.output_size[0]), int(params.output_size[1])
    extra_prompt = str(asset.get("extra_prompt") or "").strip()
    requested_texture_kind = str(asset.get("texture_kind") or "auto")
    resolved_texture_kind = resolve_tile_texture_kind(
        requested_texture_kind,
        name=name,
        extra_prompt=extra_prompt,
    )

    # 1. Prompt guard（只走本地规则；与 asset 一致）
    style_text = style_profile_policy_text(_style_profile_data(job))
    user_prompt = "\n".join(part for part in [name, extra_prompt, style_text] if part) or name
    try:
        guard = validate_user_prompt(
            asset_cfg,
            user_prompt,
            allow_template_break=False,
            max_chars=_asset_prompt_guard_max_chars(asset_cfg),
        )
    except PromptPolicyError as exc:
        raise ValueError(str(exc)) from exc

    out_root = settings.storage_root / "runs" / f"job-{job.id}"
    run_dir = new_run_dir(out_root, seed=f"tile_texture\n{name}\n{extra_prompt}")
    image_size = data.get("image_size") or asset_cfg.image_gen.size
    image_quality = (
        data.get("image_quality")
        if _request_includes(data, "image_quality")
        else asset_cfg.asset.image_quality
    )
    image_model = data.get("image_model") or asset_cfg.image_gen.model

    raw_path = run_dir / "01_source.png"
    pixel_path = run_dir / "03_pixelized.png"
    clear_image_provider_history()
    with _local_stage_context(settings)():
        material = _generate_tile_material(
            asset_cfg,
            name=name,
            extra_prompt=extra_prompt,
            texture_kind=requested_texture_kind,
            size=(width, height),
            max_colors=params.colors,
            generated_preprocess_method=params.generated_preprocess_method,
            image_size=image_size,
            image_quality=image_quality,
            image_model=image_model,
            raw_path=raw_path,
            pixel_path=pixel_path,
            size_retry_enabled=_size_retry_enabled_from_job(data),
            size_retry_max_attempts=_size_retry_max_attempts_from_job(data),
            style_profile=_style_profile_data(job),
        )
        prompt = material.prompt
        preprocessed_meta = material.preprocess_meta
        with Image.open(material.pixel_path) as opened:
            final_image = opened.convert("RGB")

        # 可选放大预览：preview_scale 是相对"用户预期目标尺寸"的倍数，
        # 当 perfect_pixel 自动检测到更高分辨率时，按用户预期目标尺寸预览像素总宽度反推预览倍数，
        # 避免 126×126 × 12 = 1512 这种过大预览。
        preview_path: Path | None = None
        preview_scale = max(0, int(params.preview_scale or 0))
        if preview_scale > 0:
            target_preview_side = max(width, height) * preview_scale
            actual_max = max(final_image.width, final_image.height)
            effective_scale = max(1, round(target_preview_side / actual_max))
            preview_path = run_dir / "04_preview.png"
            preview = final_image.resize(
                (final_image.width * effective_scale, final_image.height * effective_scale),
                Image.NEAREST,
            )
            preview.save(preview_path)

    duration = round(time.time() - start, 3)
    compiled_style = compile_style_profile(_style_profile_data(job))
    meta: dict[str, Any] = {
        "version": __version__,
        "duration_seconds": duration,
        "input": {
            "prompt": prompt,
            "effective_prompt": prompt,
            "image_path": None,
            "style_profile": compiled_style.data,
            "applied_style_profile": compiled_style.applied_rules,
        },
        "prompt_guard": guard.to_metadata(),
        "image_gen": {
            "model": image_model,
            "size": image_size,
            "quality": image_quality,
            "output_format": asset_cfg.image_gen.output_format,
            "input_fidelity": asset_cfg.image_gen.edit_input_fidelity,
            "used": True,
            "mode": "tile_texture",
            "source_only": True,
            "provider_history": image_provider_history(),
            "contact_sheet": None,
            **({"size_retry": material.size_retry} if material.size_retry else {}),
        },
        "asset": {
            "name": name,
            "extra_prompt": extra_prompt,
            "asset_kind": "tile_texture",
            "subject_kind": "tileable_pattern",
            "texture_kind": requested_texture_kind,
            "requested_texture_kind": requested_texture_kind,
            "resolved_texture_kind": resolved_texture_kind,
            "prompt": prompt,
            "grid_mode": "off",
            "pixel_size": [final_image.width, final_image.height],
            "requested_pixel_size": [width, height],
            "colors": int(params.colors),
            "palette_mode": "auto",
            "generated_preprocess_method": params.generated_preprocess_method,
            "preview_scale": preview_scale,
            "skip_vl": True,
            "no_preview": preview_scale == 0,
            "style_profile": compiled_style.data,
            "applied_style_profile": compiled_style.applied_rules,
            "request_fields": data.get("request_fields") or [],
            "pixelize_fields": data.get("pixelize_fields") or [],
            "tile_pipeline": True,
        },
        "pixelize": {
            "perfect_pixel_only": True,
            "preprocess": preprocessed_meta,
            "output_size": [final_image.width, final_image.height],
            "requested_output_size": [width, height],
        },
        "outputs": {
            "source": "01_source.png",
            "pixelized": "03_pixelized.png",
            "preview": preview_path.name if preview_path else None,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return PipelineResult(
        run_dir=run_dir,
        source_path=raw_path,
        analysis_path=None,
        analysis=None,
        pixel_path=pixel_path,
        preview_path=preview_path,
        meta_path=meta_path,
        meta=meta,
        grid_path=None,
    )


# material_b 这两个值表示「透明模式」（实心 A ↔ 透明）：不生成、不采样 B。
_DUAL_GRID_TRANSPARENT_TOKENS = {"", "transparent"}


def _material_to_rgba_array(path: Path, size: tuple[int, int]) -> np.ndarray:
    """把落盘材质读成 (h, w, 4) uint8，并以 NEAREST 落到单瓦片尺寸 (w, h)。"""
    width, height = int(size[0]), int(size[1])
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA").resize((width, height), Image.NEAREST)
    return np.asarray(rgba, dtype=np.uint8)


def _darkest_visible_rgb(mat: np.ndarray, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """取材质里 alpha>0 像素中亮度最低者的 RGB（描边缺省色）；全透明则回退 fallback。"""
    visible = mat[mat[:, :, 3] > 0]
    if visible.size == 0:
        return fallback
    rgb = visible[:, :3].astype(np.float64)
    # Rec.601 亮度近似，取最暗一像素
    luma = rgb @ np.array([0.299, 0.587, 0.114])
    darkest = visible[int(np.argmin(luma)), :3]
    return (int(darkest[0]), int(darkest[1]), int(darkest[2]))


def run_dual_grid_asset_job_pipeline(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig
) -> PipelineResult:
    """dual-grid 双瓦片直出：AI 生成无缝材质 A/B → 代码确定性合成 4×4 图集 + 应用预览。

    复用 `_generate_tile_material` 生成材质 A（必）与 B（透明模式跳过），再交给纯算法
    `pix.dual_grid` 合成。无缝性由角掩码的「边不变量」构造保证（见 `pix.dual_grid`）。
    """
    start = time.time()
    asset_cfg = deepcopy(cfg)
    asset_cfg.image_gen.contact_sheet_enabled = False
    asset_cfg.image_gen.prompt_guard_remote = False

    data = job.params_json or {}
    asset = _asset_data(job)
    name = _asset_name(job)
    params = asset_pixelize_params_from_json(data, asset_cfg)
    width, height = int(params.output_size[0]), int(params.output_size[1])

    material_a = str(asset.get("material_a") or "").strip()
    material_b_raw = str(asset.get("material_b") or "").strip()
    transparent_mode = material_b_raw.casefold() in _DUAL_GRID_TRANSPARENT_TOKENS
    style = str(asset.get("transition_style") or "rounded")
    requested_kind_a = str(asset.get("material_a_texture_kind") or "auto")
    requested_kind_b = str(asset.get("material_b_texture_kind") or "auto")
    resolved_kind_a = resolve_tile_texture_kind(requested_kind_a, name=material_a)
    resolved_kind_b = (
        None if transparent_mode else resolve_tile_texture_kind(requested_kind_b, name=material_b_raw)
    )

    # Prompt guard：审核整体用户文本（素材名 + 两种材质描述），与 tile pipeline 同走本地规则。
    style_text = style_profile_policy_text(_style_profile_data(job))
    guard_parts = [name, material_a, "" if transparent_mode else material_b_raw, style_text]
    user_prompt = "\n".join(part for part in guard_parts if part) or name
    try:
        guard = validate_user_prompt(
            asset_cfg,
            user_prompt,
            allow_template_break=False,
            max_chars=_dual_grid_prompt_guard_max_chars(asset_cfg),
        )
    except PromptPolicyError as exc:
        raise ValueError(str(exc)) from exc

    out_root = settings.storage_root / "runs" / f"job-{job.id}"
    run_dir = new_run_dir(out_root, seed=f"dual_grid\n{name}\n{material_a}\n{material_b_raw}")
    materials_dir = run_dir / "materials"
    materials_dir.mkdir(parents=True, exist_ok=True)
    image_size = data.get("image_size") or asset_cfg.image_gen.size
    image_quality = (
        data.get("image_quality")
        if _request_includes(data, "image_quality")
        else asset_cfg.asset.image_quality
    )
    image_model = data.get("image_model") or asset_cfg.image_gen.model

    clear_image_provider_history()
    with _local_stage_context(settings)():
        material_a_result = _generate_tile_material(
            asset_cfg,
            name=material_a,
            extra_prompt="",
            texture_kind=requested_kind_a,
            size=(width, height),
            max_colors=params.colors,
            generated_preprocess_method=params.generated_preprocess_method,
            image_size=image_size,
            image_quality=image_quality,
            image_model=image_model,
            raw_path=run_dir / "01_material_a_source.png",
            pixel_path=materials_dir / "material_a.png",
            size_retry_enabled=_size_retry_enabled_from_job(data),
            size_retry_max_attempts=_size_retry_max_attempts_from_job(data),
            style_profile=_style_profile_data(job),
        )
        material_b_result: _TileMaterial | None = None
        if not transparent_mode:
            material_b_result = _generate_tile_material(
                asset_cfg,
                name=material_b_raw,
                extra_prompt="",
                texture_kind=requested_kind_b,
                size=(width, height),
                max_colors=params.colors,
                generated_preprocess_method=params.generated_preprocess_method,
                image_size=image_size,
                image_quality=image_quality,
                image_model=image_model,
                raw_path=run_dir / "01_material_b_source.png",
                pixel_path=materials_dir / "material_b.png",
                size_retry_enabled=_size_retry_enabled_from_job(data),
                size_retry_max_attempts=_size_retry_max_attempts_from_job(data),
                style_profile=_style_profile_data(job),
            )

    # 合并 A/B 两次材质生成的尺寸重试结果，供 meta 与 worker 计费结算使用。
    dual_grid_size_retry = _merge_size_retry(
        material_a_result.size_retry,
        material_b_result.size_retry if material_b_result else None,
    )

    # `_material_to_rgba_array` 以 NEAREST 强制把每张材质落到 (width, height)，
    # 这正是 spec §8「A、B 理论上都 = output_size」的执行点：两数组形状由此对齐。
    mat_a = _material_to_rgba_array(material_a_result.pixel_path, (width, height))
    mat_b = (
        _material_to_rgba_array(material_b_result.pixel_path, (width, height))
        if material_b_result is not None
        else None
    )
    # 透明模式描边缺省色 = 材质 A 最暗可见色（让描边与主体融合）；A 全透明则回退深灰。
    outline_rgb = _darkest_visible_rgb(mat_a, (32, 32, 32))

    # 防御性契约（spec §8）：两材质形状必须一致，否则 compose_atlas 内的布尔掩码
    # 索引会抛晦涩的 numpy IndexError。当前因上面强制 resize 不可达，留作护栏。
    assert mat_b is None or mat_b.shape == mat_a.shape, (
        f"material A/B shape mismatch: {mat_a.shape} vs {mat_b.shape}"
    )

    atlas, tiles, mapping = dual_grid.compose_atlas(mat_a, mat_b, style, outline_rgb)
    seed = dual_grid.preview_seed(name, material_a, material_b_raw, style)
    preview_cells = 8
    preview = dual_grid.render_preview(tiles, width, height, seed, cells=preview_cells)

    atlas_path = run_dir / "dual_grid_atlas.png"
    preview_path = run_dir / "dual_grid_preview.png"
    Image.fromarray(atlas, mode="RGBA").save(atlas_path)
    Image.fromarray(preview, mode="RGBA").save(preview_path)

    atlas_height, atlas_width = atlas.shape[:2]
    duration = round(time.time() - start, 3)
    compiled_style = compile_style_profile(_style_profile_data(job))
    material_outputs: dict[str, str] = {"material_a": "materials/material_a.png"}
    if material_b_result is not None:
        material_outputs["material_b"] = "materials/material_b.png"
    meta: dict[str, Any] = {
        "version": __version__,
        "duration_seconds": duration,
        "input": {
            "prompt": material_a_result.prompt,
            "material_a_prompt": material_a_result.prompt,
            "material_b_prompt": material_b_result.prompt if material_b_result else None,
            "image_path": None,
            "style_profile": compiled_style.data,
            "applied_style_profile": compiled_style.applied_rules,
        },
        "prompt_guard": guard.to_metadata(),
        "image_gen": {
            "model": image_model,
            "size": image_size,
            "quality": image_quality,
            "output_format": asset_cfg.image_gen.output_format,
            "input_fidelity": asset_cfg.image_gen.edit_input_fidelity,
            "used": True,
            "mode": "dual_grid",
            "source_only": True,
            "provider_history": image_provider_history(),
            "contact_sheet": None,
            **({"size_retry": dual_grid_size_retry} if dual_grid_size_retry else {}),
        },
        "asset": {
            "name": name,
            "asset_kind": "dual_grid",
            "subject_kind": "tileable_pattern",
            "material_a": material_a,
            "material_b": "" if transparent_mode else material_b_raw,
            "material_a_texture_kind": requested_kind_a,
            "material_b_texture_kind": requested_kind_b,
            "resolved_texture_kind_a": resolved_kind_a,
            "resolved_texture_kind_b": resolved_kind_b,
            "transition_style": style,
            "transparent_mode": transparent_mode,
            "tile_size": [width, height],
            "atlas_size": [atlas_width, atlas_height],
            "convention": dual_grid.CONVENTION,
            "mapping": mapping,
            "preview_seed": seed,
            "preview_cells": preview_cells,
            "shared_palette": False,
            "colors": int(params.colors),
            "skip_vl": True,
            "style_profile": compiled_style.data,
            "applied_style_profile": compiled_style.applied_rules,
            "request_fields": data.get("request_fields") or [],
            "pixelize_fields": data.get("pixelize_fields") or [],
            "dual_grid_pipeline": True,
        },
        "pixelize": {
            "perfect_pixel_only": True,
            "material_a_preprocess": material_a_result.preprocess_meta,
            "material_b_preprocess": (
                material_b_result.preprocess_meta if material_b_result else None
            ),
            "output_size": [width, height],
            "requested_output_size": [width, height],
        },
        "outputs": {
            "dual_grid_atlas": "dual_grid_atlas.png",
            "dual_grid_preview": "dual_grid_preview.png",
            "materials": material_outputs,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return PipelineResult(
        run_dir=run_dir,
        source_path=material_a_result.raw_path,
        analysis_path=None,
        analysis=None,
        pixel_path=atlas_path,
        preview_path=preview_path,
        meta_path=meta_path,
        meta=meta,
        grid_path=None,
    )


def run_local_bg_remove_job_pipeline(
    job: GenerationJob, settings: WebSettings, cfg: AppConfig
) -> PipelineResult:
    """本地去背景：不调用 AI、不像素化，按选择算法直接输出透明 PNG。"""
    start = time.time()
    data = job.params_json or {}
    params = pixelize_params_from_json(data)
    if not job.input_image_path:
        raise ValueError("本地去背景需要输入图片")
    input_path = Path(job.input_image_path)
    if not input_path.exists():
        raise ValueError("输入图片不存在")

    out_root = settings.storage_root / "runs" / f"job-{job.id}"
    run_dir = new_run_dir(out_root, seed=str(input_path))
    source_path = run_dir / "01_source.png"
    output_path = run_dir / "02_background_removed.png"
    meta_path = run_dir / "meta.json"

    with _local_stage_context(settings)():
        with Image.open(input_path) as opened:
            source = opened.convert("RGBA")
        original_size = [int(source.width), int(source.height)]
        source.save(source_path)
        output = remove_background(
            source,
            tolerance=max(0, int(params.bg_tolerance)),
            feather=max(0, int(params.bg_feather)),
            edge_style=params.edge_style,
            keep_border_bleed=True,
            **bg_removal_options_from_params(cfg, params),
        )
        output.save(output_path)
        output_size = [int(output.width), int(output.height)]

    duration = round(time.time() - start, 3)
    meta: dict[str, Any] = {
        "version": __version__,
        "duration_seconds": duration,
        "input": {"prompt": None, "image_path": str(input_path)},
        "image_gen": {"used": False, "mode": "local_bg_remove", "source_only": True},
        "pixelize": {
            "mode": "local_bg_remove",
            "effective_params": {
                "output_size": output_size,
                "requested_output_size": list(params.output_size),
                "colors": params.colors,
                "remove_bg": True,
                "bg_tolerance": params.bg_tolerance,
                "bg_feather": params.bg_feather,
                "edge_style": params.edge_style,
                "bg_removal_algorithm": params.bg_removal_algorithm,
            },
            "bg_removal_algorithm": params.bg_removal_algorithm,
            "original_size": original_size,
            "output_size": output_size,
        },
        "outputs": {
            "source": source_path.name,
            "background_removed": output_path.name,
            "pixelized": output_path.name,
        },
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return PipelineResult(
        run_dir=run_dir,
        source_path=source_path,
        analysis_path=None,
        analysis=None,
        pixel_path=output_path,
        preview_path=None,
        meta_path=meta_path,
        meta=meta,
        grid_path=None,
    )



def run_job_pipeline(
    job: GenerationJob, settings: WebSettings, *, cfg: AppConfig | None = None
) -> PipelineResult | SpritePipelineResult:
    resolved_cfg = cfg or load_config(config_file=settings.pix_config_file)
    if job.job_type == "asset":
        asset = _asset_data(job)
        kind = str(asset.get("asset_kind") or "item_icon")
        if kind == "dual_grid":
            return run_dual_grid_asset_job_pipeline(job, settings, resolved_cfg)
        if kind == "tile_texture":
            return run_tile_asset_job_pipeline(job, settings, resolved_cfg)
        return run_asset_job_pipeline(job, settings, resolved_cfg)
    if job.job_type == "sprite_sheet":
        return run_sprite_mosaic_pipeline(resolved_cfg, sprite_mosaic_input_from_job(job, settings))
    if job.job_type == "local_bg_remove":
        return run_local_bg_remove_job_pipeline(job, settings, resolved_cfg)
    if job.job_type == "image_to_image":
        return run_pipeline(
            resolved_cfg, image_to_image_pipeline_input_from_job(job, settings, resolved_cfg)
        )
    inputs = pipeline_input_from_job(job, settings, resolved_cfg)
    return run_pipeline(resolved_cfg, inputs)
