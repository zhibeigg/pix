"""Web Job 与 pix pipeline 的适配。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pix.config import AppConfig, load_config
from pix.pipeline import GridDesignInput, PipelineInput, PipelineResult, run_pipeline
from pix.pixelize.core import PixelizeParams
from pix_web.config import WebSettings
from pix_web.models import GenerationJob


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
    )


def grid_design_from_json(data: dict[str, Any]) -> GridDesignInput:
    grid = data.get("grid") or {}
    return GridDesignInput(
        mode=str(grid.get("mode", "off")),  # type: ignore[arg-type]
        review=bool(grid.get("review", False)),
        retries=int(grid.get("retries", 1)),
        instruction=str(grid.get("instruction", "")),
        fallback=str(grid.get("fallback", "extract")),  # type: ignore[arg-type]
    )


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
        out_root=out_root,
        use_cache=True,
        refresh_cache=False,
    )


def run_job_pipeline(job: GenerationJob, settings: WebSettings, *, cfg: AppConfig | None = None) -> PipelineResult:
    resolved_cfg = cfg or load_config(config_file=settings.pix_config_file)
    inputs = pipeline_input_from_job(job, settings)
    return run_pipeline(resolved_cfg, inputs)
