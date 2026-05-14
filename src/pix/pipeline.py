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
from pix.api.candidate_ranker import fallback_ranking, rank_candidates
from pix.api.image_gen import edit_image, edit_images_batch, generate_image, generate_images_batch
from pix.api.prompt_guard import PromptPolicyError, validate_user_prompt
from pix.api.vision import VisionParseError, analyze_image
from pix.cache import Cache
from pix.config import AppConfig
from pix.contact_sheet import (
    apply_candidate_ranking,
    build_contact_sheet_prompt,
    build_sample_prompt,
    candidate_count,
    candidate_mode,
    collect_independent_candidates,
    contact_sheet_enabled,
    copy_selected_candidate,
    resolve_key_color,
    split_contact_sheet,
)
from pix.grid.design import design_pixel_grid
from pix.grid.extract import extract_pixel_grid, infer_grid_aligned_output_size
from pix.grid.postprocess import fit_pixel_grid_to_canvas, polish_pixel_grid
from pix.grid.readability import evaluate_grid_readability
from pix.grid.render import render_pixel_grid
from pix.grid.review import review_pixel_grid
from pix.grid.schema import PixelGrid, save_grid
from pix.grid.style_reference import find_style_references
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
    repair_mode: Literal["off", "auto", "force"] = "auto"


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


def _prepare_prompt(cfg: AppConfig, inputs: PipelineInput, notify: ProgressCb) -> tuple[str | None, dict | None]:
    """审核用户原始输入，并生成发给生图模型的受控 prompt。"""
    if inputs.prompt is None:
        return None, None
    try:
        guard = validate_user_prompt(cfg, inputs.prompt)
    except PromptPolicyError as exc:
        notify("prompt_guard_rejected", exc.result.to_metadata())
        raise ValueError(str(exc)) from exc
    notify("prompt_guard_ready", guard.to_metadata())
    description = guard.normalized_description or inputs.prompt
    if contact_sheet_enabled(cfg, has_prompt=True):
        if candidate_mode(cfg) == "n_sample":
            effective = build_sample_prompt(
                cfg,
                description,
                target_size=inputs.pixelize_params.output_size,
            )
        else:
            effective = build_contact_sheet_prompt(
                cfg,
                description,
                target_size=inputs.pixelize_params.output_size,
            )
    else:
        effective = description
    return effective, guard.to_metadata()


def _material_prompt_fields(
    cfg: AppConfig,
    *,
    user_prompt: str,
    effective_prompt: str,
) -> dict:
    if not contact_sheet_enabled(cfg, has_prompt=True):
        return {"prompt": effective_prompt}
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, user_prompt)
    mode = candidate_mode(cfg)
    base = {
        "user_prompt": user_prompt,
        "effective_prompt": effective_prompt,
        "green_screen_color": key_hex,
        "background_key_color": key_hex,
        "green_screen_tolerance": cfg.image_gen.green_screen_tolerance,
        "candidate_mode": mode,
    }
    if mode == "n_sample":
        base["n_sample_count"] = int(getattr(cfg.image_gen, "n_sample_count", 4))
    else:
        base["contact_sheet_rows"] = max(1, int(cfg.image_gen.contact_sheet_rows))
        base["contact_sheet_cols"] = max(1, int(cfg.image_gen.contact_sheet_cols))
    return base


def _postprocess_contact_sheet(
    cfg: AppConfig,
    sheet_path: Path,
    source_path: Path,
    run_dir: Path,
    *,
    effective_prompt: str,
    user_prompt: str,
    target_size: tuple[int, int],
    rank_with_vl: bool,
    notify: ProgressCb,
) -> dict | None:
    if not contact_sheet_enabled(cfg, has_prompt=True):
        return None
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, user_prompt)
    result = split_contact_sheet(
        sheet_path,
        run_dir / "candidates",
        rows=cfg.image_gen.contact_sheet_rows,
        cols=cfg.image_gen.contact_sheet_cols,
        green_screen_color=key_hex,
        tolerance=cfg.image_gen.green_screen_tolerance,
        crop_padding=cfg.asset.crop_padding,
        crop_square=cfg.asset.crop_square,
    )
    return _finalize_candidate_result(
        cfg,
        result,
        source_path,
        run_dir,
        effective_prompt=effective_prompt,
        user_prompt=user_prompt,
        target_size=target_size,
        rank_with_vl=rank_with_vl,
        notify=notify,
        candidate_mode_name="contact_sheet",
        sheet_path=sheet_path,
    )


def _postprocess_n_sample_candidates(
    cfg: AppConfig,
    sample_paths: list[Path],
    source_path: Path,
    run_dir: Path,
    *,
    effective_prompt: str,
    user_prompt: str,
    target_size: tuple[int, int],
    rank_with_vl: bool,
    notify: ProgressCb,
) -> dict | None:
    if not contact_sheet_enabled(cfg, has_prompt=True):
        return None
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, user_prompt)
    result = collect_independent_candidates(
        sample_paths,
        run_dir / "candidates",
        green_screen_color=key_hex,
        tolerance=cfg.image_gen.green_screen_tolerance,
        crop_padding=cfg.asset.crop_padding,
        crop_square=cfg.asset.crop_square,
    )
    return _finalize_candidate_result(
        cfg,
        result,
        source_path,
        run_dir,
        effective_prompt=effective_prompt,
        user_prompt=user_prompt,
        target_size=target_size,
        rank_with_vl=rank_with_vl,
        notify=notify,
        candidate_mode_name="n_sample",
        sheet_path=None,
    )


def _finalize_candidate_result(
    cfg: AppConfig,
    result,
    source_path: Path,
    run_dir: Path,
    *,
    effective_prompt: str,
    user_prompt: str,
    target_size: tuple[int, int],
    rank_with_vl: bool,
    notify: ProgressCb,
    candidate_mode_name: str,
    sheet_path: Path | None,
) -> dict:
    """共用流程：评分 → 选最优 → 复制到 source_path → 落 meta。"""
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, user_prompt)
    ranking_model = cfg.image_gen.candidate_vl_ranking_model or cfg.vision.model
    ranking = None
    if cfg.image_gen.candidate_vl_ranking_enabled and rank_with_vl:
        try:
            notify(
                "candidate_ranking_start",
                {
                    "model": ranking_model,
                    "candidates": len(result.candidates),
                    "mode": candidate_mode_name,
                },
            )
            ranking = rank_candidates(
                cfg,
                [(candidate.index, candidate.path) for candidate in result.candidates],
                user_prompt=user_prompt,
                target_size=target_size,
                model=ranking_model,
            )
            notify("candidate_ranking_ready", {"selected_index": ranking.selected_index, "mode": ranking.mode})
        except Exception as exc:
            if cfg.image_gen.candidate_vl_ranking_failure_policy == "reject":
                raise
            ranking = fallback_ranking((candidate.index for candidate in result.candidates), model=ranking_model, error=str(exc))
            notify("candidate_ranking_failed", {"error": str(exc), "fallback": "first"})
    else:
        mode = "skipped" if not rank_with_vl else "disabled"
        ranking = fallback_ranking((candidate.index for candidate in result.candidates), model=ranking_model, error=mode)

    result = apply_candidate_ranking(result, [item.to_metadata() for item in ranking.candidates])
    scores_path = run_dir / "01_candidate_scores.json"
    scores_path.write_text(json.dumps(ranking.to_metadata(), ensure_ascii=False, indent=2), encoding="utf-8")
    copy_selected_candidate(result, source_path)
    meta = result.to_metadata(
        run_dir,
        enabled=True,
        effective_prompt=effective_prompt,
        user_prompt=user_prompt,
    )
    meta["green_screen_color"] = key_hex
    meta["background_key_color"] = key_hex
    meta["green_screen_tolerance"] = cfg.image_gen.green_screen_tolerance
    meta["ranking"] = ranking.to_metadata()
    meta["scores"] = scores_path.name
    meta["candidate_mode"] = candidate_mode_name
    if sheet_path is not None:
        meta.setdefault("sheet", sheet_path.name)
    notify(
        "contact_sheet_ready",
        {
            "sheet": str(sheet_path) if sheet_path else None,
            "candidates": len(result.candidates),
            "selected": str(source_path),
            "selected_index": result.selected.index,
            "mode": candidate_mode_name,
        },
    )
    return meta


def _render_candidate_pixel_outputs(
    result_meta: dict | None,
    run_dir: Path,
    params: PixelizeParams,
    analysis: PixAnalysis | None,
    *,
    grid_mode: str,
    notify: ProgressCb,
    cfg: AppConfig | None = None,
    source_description: str = "",
) -> dict | None:
    """为 contact sheet 的每个候选生成最终像素图，并更新候选 meta。"""
    if not result_meta or not isinstance(result_meta.get("candidates"), list):
        return None
    output_dir = run_dir / "candidate_outputs"
    candidates = result_meta["candidates"]
    if grid_mode != "off":
        result_meta["candidate_outputs_skipped_reason"] = "grid_mode"
        return {"enabled": False, "reason": "grid_mode", "dir": output_dir.name, "count": 0}

    output_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    selected_pixelized: str | None = None
    selected_preview: str | None = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_rel = item.get("path")
        if not candidate_rel:
            continue
        candidate_path = Path(candidate_rel)
        if not candidate_path.is_absolute():
            candidate_path = run_dir / candidate_path
        if not candidate_path.exists():
            item["pixelized_error"] = "candidate_missing"
            continue
        try:
            index = int(item.get("index") or generated + 1)
        except (TypeError, ValueError):
            index = generated + 1
        pixel_path = output_dir / f"candidate_{index:02d}_pixelized.png"
        preview_path = output_dir / f"candidate_{index:02d}_preview.png"
        try:
            pixel_img, preview_img, pix_meta = pixelize(
                candidate_path,
                params,
                analysis=analysis,
                cfg=cfg,
                source_description=source_description,
                auto_skip_redundant_bg=True,
            )
            pixel_img.save(pixel_path)
            if preview_img is not None:
                preview_img.save(preview_path)
                item["preview_path"] = preview_path.relative_to(run_dir).as_posix()
            else:
                item["preview_path"] = None
            item["pixelized_path"] = pixel_path.relative_to(run_dir).as_posix()
            item["pixelized_meta"] = pix_meta
            generated += 1
            if item.get("selected"):
                selected_pixelized = item["pixelized_path"]
                selected_preview = item["preview_path"]
        except Exception as exc:  # noqa: BLE001 - 单个候选失败不阻断主流程
            item["pixelized_error"] = str(exc)
    notify("candidate_pixelize_ready", {"count": generated, "dir": str(output_dir)})
    return {
        "enabled": True,
        "dir": output_dir.name,
        "count": generated,
        "selected_pixelized": selected_pixelized,
        "selected_preview": selected_preview,
    }


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
            style_references = find_style_references(
                cfg.asset.style_reference_dir,
                query=inputs.prompt or "",
                limit=cfg.asset.style_reference_limit,
            )
            grid_meta["style_references"] = [ref.label for ref in style_references]
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
                style_references=style_references,
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

    # 3.5 Ramp 调色板：把 grid 的 palette 重映射到 ramp 上的最近色，获得手绘色阶感。
    palette_mode_eff = (params.palette_mode or cfg.asset.palette_mode or "auto").lower()
    if palette_mode_eff == "ramp" and grid.palette:
        from pix.pixelize.ramp import (
            RampValidationError,
            build_local_ramp,
            ramp_from_vl,
            ramp_to_meta,
            remap_palette_to_ramp,
            rgb_to_hex,
        )

        ramp_info: dict = {"source": "local", "vl_error": None}
        ramp_palette_obj = None
        try:
            ramp_palette_obj = ramp_from_vl(
                cfg,
                source_path,
                max_colors=max(3, params.colors),
                output_size=params.output_size,
                description=inputs.prompt or "",
                draft_palette_hex=[c.hex for c in grid.palette],
                model=inputs.vl_model,
            )
            ramp_info["source"] = "vl"
        except (RampValidationError, Exception) as exc:  # noqa: BLE001
            ramp_info["vl_error"] = str(exc)
            ramp_info["source"] = "local_fallback"
            ramp_palette_obj = build_local_ramp(
                render_pixel_grid(grid),
                max_colors=max(3, params.colors),
            )

        if ramp_palette_obj is not None and ramp_palette_obj.rgb_list:
            old_rgb = [
                tuple(int(grid.palette[i].hex.lstrip("#")[s:s + 2], 16) for s in (0, 2, 4))
                for i in range(len(grid.palette))
            ]
            new_rgb = remap_palette_to_ramp(old_rgb, ramp_palette_obj)
            for color, new in zip(grid.palette, new_rgb, strict=True):
                color.hex = rgb_to_hex(new)
            grid_meta["ramp"] = ramp_to_meta(ramp_palette_obj)
            grid_meta["ramp_info"] = ramp_info
            notify("grid_ramp_remap", {"source": ramp_info["source"], "colors": len(new_rgb)})

    # 4. 局部修补（auto/force）：只在 readability 有 warning 但无 blocking 时调用 VL
    repair_mode = inputs.grid.repair_mode or cfg.asset.ai_grid_repair_mode
    if repair_mode != "off" and inputs.grid.mode == "ai":
        from pix.grid.repair import repair_or_passthrough

        grid, repair_info = repair_or_passthrough(
            cfg,
            grid,
            image_path=source_path,
            model=inputs.vl_model,
            max_colors=params.colors,
            repair_mode=repair_mode,
        )
        grid_meta["repair"] = repair_info
        notify("grid_repair_done", repair_info)

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
            "palette_mode": palette_mode_eff,
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
    effective_prompt, prompt_guard_meta = _prepare_prompt(cfg, inputs, notify)
    contact_sheet_meta: dict | None = None

    # 2. 生图 / 图生图 / 复用已有图片
    source_path = run_dir / "01_source.png"
    contact_sheet_path = run_dir / "01_contact_sheet.png"
    samples_dir = run_dir / "_samples"
    source_mode = "upload"
    use_sheet_overall = contact_sheet_enabled(cfg, has_prompt=True)
    candidate_mode_name = candidate_mode(cfg) if use_sheet_overall else "single"

    def _run_n_sample_generation(*, do_edit: bool, image_path: Path | None) -> list[Path]:
        """根据 mode 生成 N 张独立单图；命中缓存的逐张复用，缺失的用一次 batch 调用补齐。"""
        n = candidate_count(cfg)
        samples_dir.mkdir(parents=True, exist_ok=True)
        cached_paths: list[Path | None] = [None] * n
        material_base = {
            **_material_prompt_fields(cfg, user_prompt=inputs.prompt or "", effective_prompt=effective_prompt or ""),
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.image_gen.quality,
            "model": inputs.image_model or cfg.image_gen.model,
            "output_format": cfg.image_gen.output_format,
        }
        if do_edit:
            assert image_path is not None
            material_base["input_fidelity"] = cfg.image_gen.edit_input_fidelity
            material_base["image_sha256"] = sha256_of_file(image_path)
        cache_kind = "imageedit_n" if do_edit else "imagegen_n"
        # 1) 逐张查缓存
        for i in range(n):
            material = {**material_base, "index": i + 1}
            cached = None if inputs.refresh_cache else cache.lookup(cache_kind, material, "png")
            if cached is not None:
                dest = samples_dir / f"sample_{i + 1:02d}.png"
                dest.write_bytes(cached.read_bytes())
                cached_paths[i] = dest
        missing = [i for i, p in enumerate(cached_paths) if p is None]
        if missing:
            need = len(missing)
            tmp_dir = samples_dir / "_pending"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            variations = list(getattr(cfg.image_gen, "n_sample_prompt_variations", []) or [])
            assert effective_prompt is not None
            if do_edit:
                assert image_path is not None
                generated = edit_images_batch(
                    cfg,
                    image_path,
                    effective_prompt,
                    tmp_dir,
                    n=need,
                    size=inputs.image_size,
                    quality=inputs.image_quality,
                    model=inputs.image_model,
                    prompt_variations=variations,
                )
            else:
                generated = generate_images_batch(
                    cfg,
                    effective_prompt,
                    tmp_dir,
                    n=need,
                    size=inputs.image_size,
                    quality=inputs.image_quality,
                    model=inputs.image_model,
                    prompt_variations=variations,
                )
            for slot_index, src in zip(missing, generated, strict=False):
                target = samples_dir / f"sample_{slot_index + 1:02d}.png"
                target.write_bytes(Path(src).read_bytes())
                cached_paths[slot_index] = target
                # 写入缓存
                cache.store_copy(cache_kind, {**material_base, "index": slot_index + 1}, "png", target)
            # 清理 _pending 临时目录
            for p in tmp_dir.glob("*"):
                try:
                    p.unlink()
                except OSError:
                    pass
            try:
                tmp_dir.rmdir()
            except OSError:
                pass
        return [p for p in cached_paths if p is not None]

    if inputs.image_path is not None and effective_prompt:
        assert inputs.prompt is not None
        if use_sheet_overall and candidate_mode_name == "n_sample":
            sample_paths = _run_n_sample_generation(do_edit=True, image_path=inputs.image_path)
            contact_sheet_meta = _postprocess_n_sample_candidates(
                cfg,
                sample_paths,
                source_path,
                run_dir,
                effective_prompt=effective_prompt,
                user_prompt=inputs.prompt,
                target_size=inputs.pixelize_params.output_size,
                rank_with_vl=not inputs.skip_vl,
                notify=notify,
            )
            source_mode = "edited_n_sample"
            notify("source_ready", {"path": str(source_path), "mode": source_mode})
        else:
            input_hash = sha256_of_file(inputs.image_path)
            use_sheet = use_sheet_overall and candidate_mode_name == "contact_sheet"
            generated_path = contact_sheet_path if use_sheet else source_path
            material = {
                **_material_prompt_fields(cfg, user_prompt=inputs.prompt, effective_prompt=effective_prompt),
                "image_sha256": input_hash,
                "size": inputs.image_size or cfg.image_gen.size,
                "quality": inputs.image_quality or cfg.image_gen.quality,
                "model": inputs.image_model or cfg.image_gen.model,
                "output_format": cfg.image_gen.output_format,
                "input_fidelity": cfg.image_gen.edit_input_fidelity,
            }
            cached = None if inputs.refresh_cache else cache.lookup("imageedit", material, "png")
            if cached is not None:
                generated_path.write_bytes(cached.read_bytes())
                if use_sheet:
                    contact_sheet_meta = _postprocess_contact_sheet(
                        cfg,
                        generated_path,
                        source_path,
                        run_dir,
                        effective_prompt=effective_prompt,
                        user_prompt=inputs.prompt,
                        target_size=inputs.pixelize_params.output_size,
                        rank_with_vl=not inputs.skip_vl,
                        notify=notify,
                    )
                    source_mode = "edit_contact_sheet_cache"
                else:
                    source_mode = "edit_cache"
                notify("source_ready", {"path": str(source_path), "mode": source_mode})
            else:
                notify("image_edit_start", {"image_path": str(inputs.image_path), **material})
                edit_image(
                    cfg,
                    inputs.image_path,
                    effective_prompt,
                    generated_path,
                    size=inputs.image_size,
                    quality=inputs.image_quality,
                    model=inputs.image_model,
                )
                cache.store_copy("imageedit", material, "png", generated_path)
                if use_sheet:
                    contact_sheet_meta = _postprocess_contact_sheet(
                        cfg,
                        generated_path,
                        source_path,
                        run_dir,
                        effective_prompt=effective_prompt,
                        user_prompt=inputs.prompt,
                        target_size=inputs.pixelize_params.output_size,
                        rank_with_vl=not inputs.skip_vl,
                        notify=notify,
                    )
                    source_mode = "edited_contact_sheet"
                else:
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
        assert effective_prompt is not None
        if use_sheet_overall and candidate_mode_name == "n_sample":
            sample_paths = _run_n_sample_generation(do_edit=False, image_path=None)
            contact_sheet_meta = _postprocess_n_sample_candidates(
                cfg,
                sample_paths,
                source_path,
                run_dir,
                effective_prompt=effective_prompt,
                user_prompt=inputs.prompt,
                target_size=inputs.pixelize_params.output_size,
                rank_with_vl=not inputs.skip_vl,
                notify=notify,
            )
            source_mode = "n_sample_generated"
            notify("source_ready", {"path": str(source_path), "mode": source_mode})
        else:
            use_sheet = use_sheet_overall and candidate_mode_name == "contact_sheet"
            generated_path = contact_sheet_path if use_sheet else source_path
            material = {
                **_material_prompt_fields(cfg, user_prompt=inputs.prompt, effective_prompt=effective_prompt),
                "size": inputs.image_size or cfg.image_gen.size,
                "quality": inputs.image_quality or cfg.image_gen.quality,
                "model": inputs.image_model or cfg.image_gen.model,
                "output_format": cfg.image_gen.output_format,
            }
            cached = None if inputs.refresh_cache else cache.lookup("imagegen", material, "png")
            if cached is not None:
                generated_path.write_bytes(cached.read_bytes())
                if use_sheet:
                    contact_sheet_meta = _postprocess_contact_sheet(
                        cfg,
                        generated_path,
                        source_path,
                        run_dir,
                        effective_prompt=effective_prompt,
                        user_prompt=inputs.prompt,
                        target_size=inputs.pixelize_params.output_size,
                        rank_with_vl=not inputs.skip_vl,
                        notify=notify,
                    )
                    source_mode = "contact_sheet_cache"
                else:
                    source_mode = "cache"
                notify("source_ready", {"path": str(source_path), "mode": source_mode})
            else:
                notify("image_gen_start", {"prompt": effective_prompt, "user_prompt": inputs.prompt, **material})
                generate_image(
                    cfg,
                    effective_prompt,
                    generated_path,
                    size=inputs.image_size,
                    quality=inputs.image_quality,
                    model=inputs.image_model,
                )
                cache.store_copy("imagegen", material, "png", generated_path)
                if use_sheet:
                    contact_sheet_meta = _postprocess_contact_sheet(
                        cfg,
                        generated_path,
                        source_path,
                        run_dir,
                        effective_prompt=effective_prompt,
                        user_prompt=inputs.prompt,
                        target_size=inputs.pixelize_params.output_size,
                        rank_with_vl=not inputs.skip_vl,
                        notify=notify,
                    )
                    source_mode = "generated_contact_sheet"
                else:
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
    candidate_outputs_meta = _render_candidate_pixel_outputs(
        contact_sheet_meta,
        run_dir,
        inputs.pixelize_params,
        analysis,
        grid_mode=inputs.grid.mode,
        notify=notify,
        cfg=cfg,
        source_description=inputs.prompt or "",
    )
    selected_candidate = None
    if contact_sheet_meta and isinstance(contact_sheet_meta.get("candidates"), list):
        selected_candidate = next((item for item in contact_sheet_meta["candidates"] if isinstance(item, dict) and item.get("selected")), None)

    if selected_candidate and selected_candidate.get("pixelized_path"):
        candidate_pixel_path = run_dir / str(selected_candidate["pixelized_path"])
        pixel_path.write_bytes(candidate_pixel_path.read_bytes())
        preview_rel = selected_candidate.get("preview_path")
        pix_meta = selected_candidate.get("pixelized_meta") if isinstance(selected_candidate.get("pixelized_meta"), dict) else {}
        pix_meta = dict(pix_meta)
        pix_meta["candidate_outputs"] = candidate_outputs_meta
        if preview_rel:
            preview_src = run_dir / str(preview_rel)
            if preview_src.exists():
                preview_path = run_dir / "04_pixelized_preview.png"
                preview_path.write_bytes(preview_src.read_bytes())
    elif inputs.grid.mode == "off":
        pixel_img, preview_img, pix_meta = pixelize(
            source_path,
            inputs.pixelize_params,
            analysis=analysis,
            cfg=cfg,
            source_description=inputs.prompt or "",
            auto_skip_redundant_bg=True,
        )
        pixel_img.save(pixel_path)
        if preview_img is not None:
            preview_path = run_dir / "04_pixelized_preview.png"
            preview_img.save(preview_path)
        pix_meta["candidate_outputs"] = candidate_outputs_meta
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
                source_path,
                inputs.pixelize_params,
                analysis=analysis,
                cfg=cfg,
                source_description=inputs.prompt or "",
                auto_skip_redundant_bg=True,
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
        pix_meta["candidate_outputs"] = candidate_outputs_meta
    notify("pixelize_ready", {"path": str(pixel_path), "grid": str(grid_path) if grid_path else None})

    # 5. meta
    meta = {
        "version": __version__,
        "duration_seconds": round(time.time() - start, 3),
        "input": {
            "prompt": inputs.prompt,
            "effective_prompt": effective_prompt,
            "image_path": str(inputs.image_path) if inputs.image_path else None,
        },
        "prompt_guard": prompt_guard_meta,
        "image_gen": {
            "model": inputs.image_model or cfg.image_gen.model,
            "size": inputs.image_size or cfg.image_gen.size,
            "quality": inputs.image_quality or cfg.image_gen.quality,
            "output_format": cfg.image_gen.output_format,
            "input_fidelity": cfg.image_gen.edit_input_fidelity,
            "used": inputs.prompt is not None,
            "mode": source_mode,
            "contact_sheet": contact_sheet_meta,
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
            "contact_sheet": contact_sheet_path.name if contact_sheet_path.exists() else None,
            "candidate_scores": "01_candidate_scores.json" if (run_dir / "01_candidate_scores.json").exists() else None,
            "candidate_outputs": "candidate_outputs" if (run_dir / "candidate_outputs").exists() else None,
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
