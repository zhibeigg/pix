"""Web Job 与 pix pipeline 的适配。"""

from __future__ import annotations

from copy import deepcopy
import json
import time
from pathlib import Path
from typing import Any

from PIL import Image

from pix import __version__
from pix.api.image_dispatcher import clear_image_provider_history, image_provider_history
from pix.api.image_gen import generate_image
from pix.api.prompt_guard import PromptPolicyError, RAW_IMAGE_PROMPT_MAX_CHARS, validate_user_prompt
from pix.asset import build_asset_prompt
from pix.config import AppConfig, load_config
from pix.contact_sheet import resolve_key_color
from pix.io_utils import file_lock, new_run_dir
from pix.pipeline import GridDesignInput, PipelineInput, PipelineResult, run_pipeline
from pix.pixelize.core import PixelizeParams
from pix.pixelize.perfect_pixel import preprocess_generated_image
from pix.sprite import SpritePipelineResult
from pix.sprite_mosaic import SpriteMosaicInput, run_sprite_mosaic_pipeline
from pix_web.config import WebSettings
from pix_web.models import GenerationJob


_LOCAL_STAGE_LOCK_TIMEOUT_SECONDS = 1800.0
_LOCAL_STAGE_LOCK_POLL_SECONDS = 0.1


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
    preview_scale = 0 if no_preview else int(_value_from_json(data, "preview_scale", cfg.asset.preview_scale))
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
        auto_crop=bool(_value_from_json(data, "auto_crop", cfg.asset.auto_crop)),
        crop_padding=float(_value_from_json(data, "crop_padding", cfg.asset.crop_padding)),
        crop_square=bool(_value_from_json(data, "crop_square", cfg.asset.crop_square)),
        palette_mode=str(_value_from_json(data, "palette_mode", cfg.asset.palette_mode)),  # type: ignore[arg-type]
        generated_preprocess_method=str(_value_from_json(data, "generated_preprocess_method", cfg.pixelize.generated_preprocess_method)),  # type: ignore[arg-type]
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


def _asset_data(job: GenerationJob) -> dict[str, Any]:
    data = job.params_json or {}
    asset = data.get("asset") or {}
    return asset if isinstance(asset, dict) else {}


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
    if asset_kind == "game_logo":
        return (
            "Use the provided reference image as logo inspiration: preserve its emblem silhouette, "
            "shape language, main color mood, stroke rhythm, and lettering attitude where useful, "
            "but redesign it as a clean pixel-art game logo. The final readable text must only use "
            "the exact title, acronym, or brand text from the Subject; do not copy or invent any extra words from the reference."
        )
    return ""


def pipeline_input_from_job(job: GenerationJob, settings: WebSettings) -> PipelineInput:
    data = job.params_json or {}
    image_path = Path(job.input_image_path) if job.input_image_path else None
    out_root = settings.storage_root / "runs" / f"job-{job.id}"

    return PipelineInput(
        prompt=job.prompt,
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
        use_cache=True,
        refresh_cache=False,
        local_stage_context=_local_stage_context(settings),
    )


def asset_pipeline_input_from_job(job: GenerationJob, settings: WebSettings, cfg: AppConfig) -> PipelineInput:
    data = job.params_json or {}
    asset = _asset_data(job)
    name = _asset_name(job)
    params = asset_pixelize_params_from_json(data, cfg)
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, name)
    asset_kind = str(asset.get("asset_kind") or "item_icon")
    image_path = Path(job.input_image_path) if job.input_image_path else None
    prompt = build_asset_prompt(
        cfg.asset.prompt_template,
        name,
        size=params.output_size,
        extra_prompt=str(asset.get("extra_prompt") or ""),
        asset_kind=asset_kind,
        subject_kind=str(asset.get("subject_kind") or "single_prop"),
        key_color=key_hex,
        key_tolerance=cfg.image_gen.green_screen_tolerance,
        max_colors=params.colors,
    )
    reference_appendix = _asset_reference_prompt_appendix(asset_kind, image_path is not None)
    if reference_appendix:
        prompt = f"{prompt} {reference_appendix}"
    image_quality = data.get("image_quality") if _request_includes(data, "image_quality") else cfg.asset.image_quality
    user_prompt_parts = [name, str(asset.get("extra_prompt") or "").strip()]
    prompt_guard_text = "\n".join(part for part in user_prompt_parts if part)
    return PipelineInput(
        prompt=prompt,
        prompt_guard_text=prompt_guard_text,
        image_path=image_path,
        image_size=data.get("image_size") or cfg.image_gen.size,
        image_quality=image_quality,
        image_model=data.get("image_model"),
        vl_model=data.get("vl_model"),
        skip_vl=_asset_skip_vl(data, cfg),
        pixelize_params=params,
        grid=asset_grid_design_from_json(data, cfg),
        out_root=settings.storage_root / "runs" / f"job-{job.id}",
        use_cache=True,
        refresh_cache=False,
        local_stage_context=_local_stage_context(settings),
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
        use_cache=True,
        refresh_cache=False,
        fps=int(sprite.get("fps", 8)),
        duration_ms=int(sprite.get("duration_ms", 0)) or None,
        loop=int(sprite.get("loop", 0)),
        gif_export=bool(sprite.get("gif_export", False)),
        key_tolerance=sprite.get("key_tolerance"),
        billing=data.get("billing") if isinstance(data.get("billing"), dict) else None,
        local_stage_context=_local_stage_context(settings),
    )


def _write_asset_meta(result: PipelineResult, job: GenerationJob, inputs: PipelineInput) -> None:
    data = job.params_json or {}
    asset = _asset_data(job)
    result.meta["asset"] = {
        "name": _asset_name(job),
        "extra_prompt": str(asset.get("extra_prompt") or ""),
        "asset_kind": str(asset.get("asset_kind") or "item_icon"),
        "subject_kind": str(asset.get("subject_kind") or "single_prop"),
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
        "request_fields": data.get("request_fields") or [],
        "pixelize_fields": data.get("pixelize_fields") or [],
    }
    result.meta_path.write_text(json.dumps(result.meta, indent=2, ensure_ascii=False), encoding="utf-8")


def run_asset_job_pipeline(job: GenerationJob, settings: WebSettings, cfg: AppConfig) -> PipelineResult:
    asset_cfg = deepcopy(cfg)
    asset_cfg.image_gen.contact_sheet_enabled = False
    asset_cfg.image_gen.prompt_guard_remote = False
    inputs = asset_pipeline_input_from_job(job, settings, asset_cfg)
    result = run_pipeline(asset_cfg, inputs)
    _write_asset_meta(result, job, inputs)
    return result


def run_tile_asset_job_pipeline(job: GenerationJob, settings: WebSettings, cfg: AppConfig) -> PipelineResult:
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
    prompt = build_asset_prompt(
        asset_cfg.asset.prompt_template,
        name,
        size=(width, height),
        extra_prompt=extra_prompt,
        asset_kind="tile_texture",
        subject_kind="tileable_pattern",
        max_colors=params.colors,
    )

    # 1. Prompt guard（只走本地规则；与 asset 一致）
    user_prompt = "\n".join(part for part in [name, extra_prompt] if part) or name
    try:
        guard = validate_user_prompt(
            asset_cfg,
            user_prompt,
            allow_template_break=False,
            max_chars=RAW_IMAGE_PROMPT_MAX_CHARS,
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
    clear_image_provider_history()
    with _local_stage_context(settings)():
        generate_image(
            asset_cfg,
            prompt,
            raw_path,
            size=image_size,
            quality=image_quality,
            model=image_model,
        )

        # 2. 完美像素：让 perfectPixel 自动检测网格作为主导，target_size 仅作为提示。
        # 用户面板上选择的"目标尺寸"被理解为"输出 ≤ 目标尺寸的最小整数倍"，避免在
        # perfect_pixel 已经精确网格对齐的结果上再做一次破坏性的 NEAREST 缩放。
        with Image.open(raw_path) as opened:
            source_image = opened.convert("RGBA")
        preprocessed = preprocess_generated_image(
            source_image,
            method=params.generated_preprocess_method or "perfect_pixel",
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
            final_image = refined.resize((width, height), Image.NEAREST) if refined.size != (width, height) else refined
        else:
            final_image = refined

        pixel_path = run_dir / "03_pixelized.png"
        final_image.save(pixel_path)

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
    meta: dict[str, Any] = {
        "version": __version__,
        "duration_seconds": duration,
        "input": {
            "prompt": prompt,
            "effective_prompt": prompt,
            "image_path": None,
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
        },
        "asset": {
            "name": name,
            "extra_prompt": extra_prompt,
            "asset_kind": "tile_texture",
            "subject_kind": "tileable_pattern",
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
            "request_fields": data.get("request_fields") or [],
            "pixelize_fields": data.get("pixelize_fields") or [],
            "tile_pipeline": True,
        },
        "pixelize": {
            "perfect_pixel_only": True,
            "preprocess": preprocessed.meta,
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


def run_job_pipeline(job: GenerationJob, settings: WebSettings, *, cfg: AppConfig | None = None) -> PipelineResult | SpritePipelineResult:
    resolved_cfg = cfg or load_config(config_file=settings.pix_config_file)
    if job.job_type == "asset":
        asset = _asset_data(job)
        if str(asset.get("asset_kind") or "item_icon") == "tile_texture":
            return run_tile_asset_job_pipeline(job, settings, resolved_cfg)
        return run_asset_job_pipeline(job, settings, resolved_cfg)
    if job.job_type == "sprite_sheet":
        return run_sprite_mosaic_pipeline(resolved_cfg, sprite_mosaic_input_from_job(job, settings))
    inputs = pipeline_input_from_job(job, settings)
    return run_pipeline(resolved_cfg, inputs)
