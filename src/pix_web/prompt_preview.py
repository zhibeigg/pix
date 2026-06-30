"""任务 Prompt Preview 构建。"""

from __future__ import annotations

from fastapi import HTTPException, status

from pix.asset import build_asset_prompt
from pix.config import AppConfig
from pix.contact_sheet import resolve_key_color
from pix.prompt_style import compile_style_profile
from pix.sprite_mosaic import SpriteMosaicInput, _ensure_row_prompts, _resolve_settings, build_mosaic_prompt
from pix_web.pipeline_adapter import RAW_REFERENCE_IMAGE_ALIAS, _asset_reference_prompt_appendix, pixelize_params_from_json
from pix_web.schemas import JobCreateRequest, PromptPreviewResponse


_DUAL_GRID_TRANSPARENT_TOKENS = {"", "transparent"}


def _style_profile(req: JobCreateRequest) -> dict[str, object]:
    return req.style_profile.model_dump(mode="json")


def _asset_subject(req: JobCreateRequest) -> str:
    return (req.asset.name or req.prompt or "").strip()


def _asset_prompt_preview(req: JobCreateRequest, cfg: AppConfig) -> PromptPreviewResponse:
    params = pixelize_params_from_json({"pixelize": req.pixelize.model_dump(mode="json")})
    style_profile = _style_profile(req)
    compiled_style = compile_style_profile(style_profile)
    asset_kind = req.asset.asset_kind

    if asset_kind == "dual_grid":
        material_a = (req.asset.material_a or "").strip()
        material_b = (req.asset.material_b or "").strip()
        transparent = material_b.casefold() in _DUAL_GRID_TRANSPARENT_TOKENS
        prompts: list[str] = []
        if material_a:
            prompts.append(
                "Material A prompt:\n"
                + build_asset_prompt(
                    cfg.asset.prompt_template,
                    material_a,
                    size=params.output_size,
                    asset_kind="tile_texture",
                    subject_kind="tileable_pattern",
                    texture_kind=req.asset.material_a_texture_kind or "auto",
                    max_colors=params.colors,
                    style_profile=style_profile,
                )
            )
        if not transparent:
            prompts.append(
                "Material B prompt:\n"
                + build_asset_prompt(
                    cfg.asset.prompt_template,
                    material_b,
                    size=params.output_size,
                    asset_kind="tile_texture",
                    subject_kind="tileable_pattern",
                    texture_kind=req.asset.material_b_texture_kind or "auto",
                    max_colors=params.colors,
                    style_profile=style_profile,
                )
            )
        return PromptPreviewResponse(
            mode="dual_grid",
            positive_prompt="\n\n".join(prompts).strip(),
            applied_style_profile=compiled_style.applied_rules,
            warnings=[] if prompts else ["双瓦片至少需要材质 A 描述。"],
        )

    subject = _asset_subject(req)
    key_hex, _ = resolve_key_color(cfg.image_gen.green_screen_color, subject)
    prompt = build_asset_prompt(
        cfg.asset.prompt_template,
        subject,
        size=params.output_size,
        extra_prompt=req.asset.extra_prompt or "",
        asset_kind=asset_kind,
        subject_kind=req.asset.subject_kind,
        texture_kind=req.asset.texture_kind,
        key_color=key_hex,
        key_tolerance=cfg.image_gen.green_screen_tolerance,
        max_colors=params.colors,
        style_profile=style_profile,
    )
    reference_appendix = _asset_reference_prompt_appendix(asset_kind, bool(req.input_image_path))
    if reference_appendix:
        prompt = f"{prompt} {reference_appendix}"
    if req.input_image_path:
        prompt = f"{prompt} {RAW_REFERENCE_IMAGE_ALIAS}"
    return PromptPreviewResponse(
        mode="asset" if asset_kind != "tile_texture" else "tile_texture",
        positive_prompt=prompt.strip(),
        applied_style_profile=compiled_style.applied_rules,
    )


def _sprite_prompt_preview(req: JobCreateRequest, cfg: AppConfig) -> PromptPreviewResponse:
    style_profile = _style_profile(req)
    compiled_style = compile_style_profile(style_profile)
    inputs = SpriteMosaicInput(
        prompt=(req.prompt or "").strip(),
        rows=req.sprite.rows,
        cols=req.sprite.cols,
        row_prompts=list(req.sprite.row_prompts or []),
        reference_image_path=None,
        image_size=req.image_size,
        image_quality=req.image_quality,
        image_model=req.image_model,
        pixelize_params=pixelize_params_from_json({"pixelize": req.pixelize.model_dump(mode="json")}),
        fps=req.sprite.fps,
        duration_ms=req.sprite.duration_ms,
        loop=req.sprite.loop,
        gif_export=req.sprite.gif_export,
        style_profile=style_profile,
    )
    description = inputs.prompt
    settings = _resolve_settings(cfg, inputs, description)
    safe_row_prompts = _ensure_row_prompts(inputs.row_prompts, settings.rows, description)
    prompt = build_mosaic_prompt(
        cfg,
        description,
        rows=settings.rows,
        cols=settings.cols,
        row_prompts=safe_row_prompts,
        sheet_pixel_size=settings.sheet_pixel_size,
        frame_pixel_size=settings.target_size,
        api_size_pixel=settings.api_size_pixel,
        anchor=settings.anchor,
        key_color=settings.key_color,
        key_tolerance=settings.key_tolerance,
        max_colors=settings.max_colors,
        use_reference=bool(req.sprite.reference_image_path),
        style_profile=style_profile,
    )
    return PromptPreviewResponse(
        mode="sprite_sheet",
        positive_prompt=prompt.strip(),
        applied_style_profile=compiled_style.applied_rules,
    )


def build_prompt_preview(req: JobCreateRequest, cfg: AppConfig) -> PromptPreviewResponse:
    if req.job_type == "asset":
        return _asset_prompt_preview(req, cfg)
    if req.job_type == "sprite_sheet":
        return _sprite_prompt_preview(req, cfg)
    if req.job_type in {"local_pixelize", "local_bg_remove", "repixelize"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="当前模式不调用生图模型，没有可预览的 Prompt。",
        )
    if req.job_type in {"text_to_image", "image_to_image"}:
        compiled_style = compile_style_profile(_style_profile(req))
        style_prompt = compiled_style.prompt
        prompt = (req.prompt or "").strip()
        if style_prompt:
            prompt = f"{prompt} {style_prompt}".strip()
        return PromptPreviewResponse(
            mode=req.job_type,
            positive_prompt=prompt,
            applied_style_profile=compiled_style.applied_rules,
            warnings=["原生生图模式仅预览用户 Prompt 与风格档案，不包含素材后处理模板。"],
        )
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持预览该任务类型。")
