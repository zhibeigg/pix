"""Web Job 与 pix pipeline 的适配。"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from pix.asset import build_asset_prompt
from pix.config import AppConfig, load_config
from pix.io_utils import file_lock
from pix.pipeline import GridDesignInput, PipelineInput, PipelineResult, run_pipeline
from pix.pixelize.core import PixelizeParams
from pix.sprite import SpritePipelineInput, SpritePipelineResult, run_sprite_pipeline
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
    prompt = build_asset_prompt(
        cfg.asset.prompt_template,
        name,
        size=params.output_size,
        extra_prompt=str(asset.get("extra_prompt") or ""),
        asset_kind=str(asset.get("asset_kind") or "item_icon"),
        subject_kind=str(asset.get("subject_kind") or "single_prop"),
    )
    image_quality = data.get("image_quality") if _request_includes(data, "image_quality") else cfg.asset.image_quality
    return PipelineInput(
        prompt=prompt,
        image_path=None,
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


def sprite_input_from_job(job: GenerationJob, settings: WebSettings) -> SpritePipelineInput:
    data = job.params_json or {}
    sprite = data.get("sprite") or {}
    out_root = settings.storage_root / "runs" / f"job-{job.id}"
    return SpritePipelineInput(
        prompt=job.prompt or "",
        image_size=data.get("image_size"),
        image_quality=data.get("image_quality"),
        image_model=data.get("image_model"),
        pixelize_params=pixelize_params_from_json(data),
        out_root=out_root,
        use_cache=True,
        refresh_cache=False,
        duration_ms=int(sprite.get("duration_ms", 120)),
        loop=int(sprite.get("loop", 0)),
        rows=int(sprite.get("rows", 3)),
        cols=int(sprite.get("cols", 3)),
        key_mode=sprite.get("key_mode"),
        key_tolerance=sprite.get("key_tolerance"),
        key_softness=sprite.get("key_softness"),
        key_alpha_floor=sprite.get("key_alpha_floor"),
        key_despill=sprite.get("key_despill"),
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
        "preview_scale": inputs.pixelize_params.preview_scale,
        "skip_vl": inputs.skip_vl,
        "no_preview": bool(asset.get("no_preview", False)),
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


def run_job_pipeline(job: GenerationJob, settings: WebSettings, *, cfg: AppConfig | None = None) -> PipelineResult | SpritePipelineResult:
    resolved_cfg = cfg or load_config(config_file=settings.pix_config_file)
    if job.job_type == "asset":
        return run_asset_job_pipeline(job, settings, resolved_cfg)
    if job.job_type == "sprite_sheet":
        return run_sprite_pipeline(resolved_cfg, sprite_input_from_job(job, settings))
    inputs = pipeline_input_from_job(job, settings)
    return run_pipeline(resolved_cfg, inputs)
