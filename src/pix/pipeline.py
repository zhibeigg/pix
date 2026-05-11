"""主编排：prompt/图片 → 生图 → 分析 → 像素化。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from PIL import Image

from pix import __version__
from pix.analysis.schema import PixAnalysis
from pix.api.image_gen import edit_image, generate_image
from pix.api.vision import VisionParseError, analyze_image
from pix.cache import Cache
from pix.config import AppConfig
from pix.grid.design import design_pixel_grid
from pix.grid.extract import extract_pixel_grid, infer_grid_aligned_output_size
from pix.grid.postprocess import fit_pixel_grid_to_canvas, polish_pixel_grid
from pix.grid.readability import evaluate_grid_readability
from pix.grid.render import render_pixel_grid
from pix.grid.review import review_pixel_grid
from pix.grid.schema import PixelGrid, save_grid
from pix.io_utils import new_run_dir, sha256_of_file
from pix.pixelize.core import PixelizeParams, pixelize


ProgressCb = Callable[[str, dict], None]


@dataclass
class GridDesignInput:
    mode: Literal["off", "extract", "ai"] = "off"
    review: bool = False
    retries: int = 1
    instruction: str = ""
    fallback: Literal["extract", "pixelize", "fail"] = "extract"


@dataclass
class PipelineInput:
    prompt: str | None = None
    image_path: Path | None = None
    # 生图参数
    image_size: str | None = None
    image_quality: str | None = None
    image_model: str | None = None
    # VL
    vl_model: str | None = None
    skip_vl: bool = False
    # 像素化
    pixelize_params: PixelizeParams = field(default_factory=PixelizeParams)
    # 输出
    out_root: str | Path | None = None
    # 缓存
    use_cache: bool = True
    refresh_cache: bool = False
    # Pixel Grid 低像素直绘/提取
    grid: GridDesignInput = field(default_factory=GridDesignInput)


@dataclass
class PipelineResult:
    run_dir: Path
    source_path: Path
    analysis_path: Path | None
    analysis: PixAnalysis | None
    pixel_path: Path
    preview_path: Path | None
    meta_path: Path
    meta: dict
    grid_path: Path | None = None


def _noop(_step: str, _payload: dict) -> None:
    pass


def _extract_grid_from_source(cfg: AppConfig, inputs: PipelineInput, source_path: Path, *, fallback: bool = False) -> PixelGrid:
    params = inputs.pixelize_params
    return extract_pixel_grid(
        source_path,
        output_size=params.output_size,
        max_colors=params.colors,
        auto_crop=params.auto_crop or cfg.asset.auto_crop,
        crop_padding=params.crop_padding,
        crop_square=params.crop_square,
        remove_bg=params.remove_bg,
        bg_tolerance=params.bg_tolerance,
        metadata={"generator": "extract_grid_fallback" if fallback else "extract_grid"},
    )


def _draft_grid_from_source(cfg: AppConfig, inputs: PipelineInput, source_path: Path) -> PixelGrid | None:
    if not cfg.asset.ai_grid_draft:
        return None
    params = inputs.pixelize_params
    aligned = infer_grid_aligned_output_size(
        source_path,
        auto_crop=params.auto_crop or cfg.asset.auto_crop,
        crop_padding=params.crop_padding,
        crop_square=params.crop_square,
        remove_bg=params.remove_bg,
        bg_tolerance=params.bg_tolerance,
        max_axis=cfg.asset.ai_grid_draft_max_axis,
    )
    return extract_pixel_grid(
        source_path,
        output_size=aligned.output_size,
        max_colors=params.colors,
        auto_crop=params.auto_crop or cfg.asset.auto_crop,
        crop_padding=params.crop_padding,
        crop_square=params.crop_square,
        remove_bg=params.remove_bg,
        bg_tolerance=params.bg_tolerance,
        metadata={
            "generator": "ai_grid_draft",
            "draft_size_source": aligned.to_metadata(),
            "target_output_size": list(params.output_size),
        },
    )


def _run_grid_pixelize(
    cfg: AppConfig,
    inputs: PipelineInput,
    source_path: Path,
    run_dir: Path,
    notify: ProgressCb,
) -> tuple[Image.Image, Image.Image | None, dict, Path]:
    params = inputs.pixelize_params
    grid_meta: dict = {
        "mode": inputs.grid.mode,
        "review": inputs.grid.review,
        "fallback": inputs.grid.fallback,
        "used_fallback": False,
    }
    try:
        if inputs.grid.mode == "ai":
            draft_grid = _draft_grid_from_source(cfg, inputs, source_path)
            draft_report = evaluate_grid_readability(draft_grid, max_colors=params.colors) if draft_grid is not None else None
            notify(
                "grid_design_start",
                {
                    "size": list(params.output_size),
                    "colors": params.colors,
                    "draft_size": [draft_grid.canvas.width, draft_grid.canvas.height] if draft_grid is not None else None,
                },
            )
            grid = design_pixel_grid(
                cfg,
                source_path,
                output_size=params.output_size,
                max_colors=params.colors,
                model=inputs.vl_model,
                instruction=inputs.grid.instruction,
                source_prompt=inputs.prompt or "",
                draft_grid=draft_grid,
                draft_report=draft_report,
                draft_preview_scale=cfg.asset.ai_grid_draft_preview_scale,
                retries=inputs.grid.retries,
            )
        else:
            notify("grid_extract_start", {"size": list(params.output_size), "colors": params.colors})
            grid = _extract_grid_from_source(cfg, inputs, source_path)
    except Exception as exc:
        if inputs.grid.fallback != "extract" or inputs.grid.mode == "extract":
            raise
        notify("grid_fallback", {"mode": "extract", "error": str(exc)})
        grid = _extract_grid_from_source(cfg, inputs, source_path, fallback=True)
        grid_meta.update({"used_fallback": True, "fallback_reason": str(exc)})

    if cfg.asset.grid_cleanup or cfg.asset.grid_outline:
        grid = polish_pixel_grid(
            grid,
            cleanup=cfg.asset.grid_cleanup,
            outline=cfg.asset.grid_outline,
            outline_strength=cfg.asset.grid_outline_strength,
            min_neighbors=cfg.asset.grid_min_neighbors,
            max_colors=params.colors,
        )
    if cfg.asset.fit_canvas:
        grid = fit_pixel_grid_to_canvas(
            grid,
            padding=cfg.asset.fit_padding,
            mode=cfg.asset.fit_mode,
            min_axis_coverage=cfg.asset.fit_min_axis_coverage,
        )
    if inputs.grid.review:
        notify("grid_review_start", {})
        grid = review_pixel_grid(cfg, grid, model=inputs.vl_model, instruction=inputs.grid.instruction)

    report = evaluate_grid_readability(grid, max_colors=params.colors)
    grid.metadata["readability"] = report.to_dict()
    ai_grid_meta = grid.metadata.get("ai_grid")
    if isinstance(ai_grid_meta, dict):
        grid_meta["attempts"] = ai_grid_meta.get("attempts")
        grid_meta["max_attempts"] = ai_grid_meta.get("max_attempts")
        grid_meta["repaired"] = bool(ai_grid_meta.get("repaired", False))
        grid_meta["source_prompt_used"] = bool(ai_grid_meta.get("source_prompt_used", False))
        grid_meta["draft"] = ai_grid_meta.get("draft")
    grid_meta["readability"] = report.to_dict()
    grid_path = run_dir / "03_pixelized.grid.json"
    save_grid(grid, grid_path)
    pixel_img = render_pixel_grid(grid)
    preview_img = None
    scale = max(0, int(params.preview_scale))
    if scale > 1:
        preview_img = pixel_img.resize(
            (pixel_img.width * scale, pixel_img.height * scale), Image.Resampling.NEAREST
        )
    pix_meta = {
        "effective_params": {
            "output_size": list(params.output_size),
            "colors": params.colors,
            "dither": params.dither,
            "preset": params.preset or "auto",
            "preview_scale": params.preview_scale,
            "remove_bg": params.remove_bg,
            "auto_crop": params.auto_crop,
        },
        "palette": [color.hex for color in grid.palette],
        "palette_size": len(grid.palette),
        "used_analysis": False,
        "grid": grid_meta,
    }
    return pixel_img, preview_img, pix_meta, grid_path


def run_pipeline(
    cfg: AppConfig,
    inputs: PipelineInput,
    progress: ProgressCb | None = None,
) -> PipelineResult:
    """执行完整管线。"""
    notify = progress or _noop
    start = time.time()

    if inputs.prompt is None and inputs.image_path is None:
        raise ValueError("必须提供 prompt 或 image_path 之一")

    # 1. 运行目录
    seed_parts = [inputs.prompt or ""]
    if inputs.image_path is not None:
        seed_parts.append(str(inputs.image_path))
    seed = "\n".join(p for p in seed_parts if p)
    out_root = Path(inputs.out_root or cfg.output.root)
    run_dir = new_run_dir(out_root, seed=seed)
    notify("run_start", {"run_dir": str(run_dir)})

    # 记录输入
    (run_dir / "00_input.txt").write_text(
        f"prompt={inputs.prompt or ''}\nimage_path={inputs.image_path or ''}\n",
        encoding="utf-8",
    )

    cache = Cache(cfg.cache.dir, enabled=cfg.cache.enabled and inputs.use_cache)

    # 2. 生图 / 图生图 / 复用已有图片
    source_path = run_dir / "01_source.png"
    source_mode = "upload"
    if inputs.image_path is not None and inputs.prompt:
        input_hash = sha256_of_file(inputs.image_path)
        material = {
            "prompt": inputs.prompt,
            "image_sha256": input_hash,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.image_gen.quality,
            "model": inputs.image_model or cfg.image_gen.model,
            "output_format": cfg.image_gen.output_format,
            "input_fidelity": cfg.image_gen.edit_input_fidelity,
        }
        cached = None if inputs.refresh_cache else cache.lookup("imageedit", material, "png")
        if cached is not None:
            source_path.write_bytes(cached.read_bytes())
            source_mode = "edit_cache"
            notify("source_ready", {"path": str(source_path), "mode": source_mode})
        else:
            notify("image_edit_start", {"image_path": str(inputs.image_path), **material})
            edit_image(
                cfg,
                inputs.image_path,
                inputs.prompt,
                source_path,
                size=inputs.image_size,
                quality=inputs.image_quality,
                model=inputs.image_model,
            )
            cache.store_copy("imageedit", material, "png", source_path)
            source_mode = "edited"
            notify("source_ready", {"path": str(source_path), "mode": source_mode})
    elif inputs.image_path is not None:
        # 复制到 run_dir
        data = Path(inputs.image_path).read_bytes()
        source_path.write_bytes(data)
        source_mode = "upload"
        notify("source_ready", {"path": str(source_path), "mode": source_mode})
    else:
        assert inputs.prompt is not None
        material = {
            "prompt": inputs.prompt,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.image_gen.quality,
            "model": inputs.image_model or cfg.image_gen.model,
            "output_format": cfg.image_gen.output_format,
        }
        cached = None if inputs.refresh_cache else cache.lookup("imagegen", material, "png")
        if cached is not None:
            source_path.write_bytes(cached.read_bytes())
            source_mode = "cache"
            notify("source_ready", {"path": str(source_path), "mode": source_mode})
        else:
            notify("image_gen_start", {"prompt": inputs.prompt, **material})
            generate_image(
                cfg,
                inputs.prompt,
                source_path,
                size=inputs.image_size,
                quality=inputs.image_quality,
                model=inputs.image_model,
            )
            cache.store_copy("imagegen", material, "png", source_path)
            source_mode = "generated"
            notify("source_ready", {"path": str(source_path), "mode": source_mode})

    # 3. 多模态分析
    analysis: PixAnalysis | None = None
    analysis_path: Path | None = None
    if not inputs.skip_vl:
        model_name = inputs.vl_model or cfg.vision.model
        source_hash = sha256_of_file(source_path)
        material = {"image_sha256": source_hash, "model": model_name, "schema_v": 1}
        cached = None if inputs.refresh_cache else cache.lookup("vl", material, "json")
        analysis_path = run_dir / "02_analysis.json"
        if cached is not None:
            analysis_path.write_text(cached.read_text(encoding="utf-8"), encoding="utf-8")
            try:
                analysis = PixAnalysis.model_validate_json(analysis_path.read_text(encoding="utf-8"))
                notify("analysis_ready", {"path": str(analysis_path), "mode": "cache"})
            except Exception:
                analysis = None
                notify("analysis_cache_invalid", {"path": str(analysis_path)})
        if analysis is None:
            try:
                notify("analysis_start", {"model": model_name})
                analysis = analyze_image(cfg, source_path, model=model_name)
                analysis_json = analysis.model_dump_json(indent=2)
                analysis_path.write_text(analysis_json, encoding="utf-8")
                cache.store("vl", material, "json", analysis_json)
                notify("analysis_ready", {"path": str(analysis_path), "mode": "generated"})
            except (VisionParseError, Exception) as exc:
                notify("analysis_failed", {"error": str(exc)})
                analysis = None
                analysis_path.write_text(
                    json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    # 4. 像素化 / Pixel Grid 直绘
    notify("pixelize_start", {"grid_mode": inputs.grid.mode})
    preview_path: Path | None = None
    grid_path: Path | None = None
    pixel_path = run_dir / "03_pixelized.png"
    if inputs.grid.mode == "off":
        pixel_img, preview_img, pix_meta = pixelize(
            source_path, inputs.pixelize_params, analysis=analysis
        )
    else:
        try:
            pixel_img, preview_img, pix_meta, grid_path = _run_grid_pixelize(
                cfg, inputs, source_path, run_dir, notify
            )
        except Exception as exc:
            if inputs.grid.fallback != "pixelize":
                raise
            notify("grid_fallback", {"mode": "pixelize", "error": str(exc)})
            pixel_img, preview_img, pix_meta = pixelize(
                source_path, inputs.pixelize_params, analysis=analysis
            )
            pix_meta["grid"] = {
                "mode": inputs.grid.mode,
                "failed": True,
                "fallback": "pixelize",
                "error": str(exc),
            }
    pixel_img.save(pixel_path)
    if preview_img is not None:
        preview_path = run_dir / "04_pixelized_preview.png"
        preview_img.save(preview_path)
    notify("pixelize_ready", {"path": str(pixel_path), "grid": str(grid_path) if grid_path else None})

    # 5. meta
    meta = {
        "version": __version__,
        "duration_seconds": round(time.time() - start, 3),
        "input": {
            "prompt": inputs.prompt,
            "image_path": str(inputs.image_path) if inputs.image_path else None,
        },
        "image_gen": {
            "model": inputs.image_model or cfg.image_gen.model,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.image_gen.quality,
            "output_format": cfg.image_gen.output_format,
            "input_fidelity": cfg.image_gen.edit_input_fidelity,
            "used": inputs.prompt is not None,
            "mode": source_mode,
        },
        "vision": {
            "model": inputs.vl_model or cfg.vision.model,
            "skipped": inputs.skip_vl,
            "ok": analysis is not None,
        },
        "pixelize": pix_meta,
        "cache": {"enabled": cache.enabled, "refresh": inputs.refresh_cache},
        "outputs": {
            "source": source_path.name,
            "analysis": analysis_path.name if analysis_path else None,
            "pixelized": pixel_path.name,
            "preview": preview_path.name if preview_path else None,
            "grid": grid_path.name if grid_path else None,
        },
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return PipelineResult(
        run_dir=run_dir,
        source_path=source_path,
        analysis_path=analysis_path,
        analysis=analysis,
        pixel_path=pixel_path,
        preview_path=preview_path,
        meta_path=meta_path,
        meta=meta,
        grid_path=grid_path,
    )
