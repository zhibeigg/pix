"""主编排：prompt/图片 → 生图 → 分析 → 像素化。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pix import __version__
from pix.analysis.schema import PixAnalysis
from pix.api.image_gen import edit_image, generate_image
from pix.api.vision import VisionParseError, analyze_image
from pix.cache import Cache
from pix.config import AppConfig
from pix.io_utils import new_run_dir, sha256_of_file
from pix.pixelize.core import PixelizeParams, pixelize


ProgressCb = Callable[[str, dict], None]


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


def _noop(_step: str, _payload: dict) -> None:
    pass


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

    # 4. 像素化
    notify("pixelize_start", {})
    pixel_img, preview_img, pix_meta = pixelize(
        source_path, inputs.pixelize_params, analysis=analysis
    )
    pixel_path = run_dir / "03_pixelized.png"
    pixel_img.save(pixel_path)
    preview_path: Path | None = None
    if preview_img is not None:
        preview_path = run_dir / "04_pixelized_preview.png"
        preview_img.save(preview_path)
    notify("pixelize_ready", {"path": str(pixel_path)})

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
    )
