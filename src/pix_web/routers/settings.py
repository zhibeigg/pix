"""公开设置端点（无需认证）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pix.api.image_model_registry import available_model_infos, public_image_model_id
from pix.config import AppConfig
from pix_web.config import WebSettings
from pix_web.security import get_db, get_settings
from pix_web.system_settings import load_managed_pix_config

router = APIRouter(prefix="/settings", tags=["settings"])


class ImageModelInfoResponse(BaseModel):
    id: str
    label: str
    providers: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    qualities: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    provider_count: int = 0
    default_size: str = "1024x1024"
    default_quality: str = "auto"


class PromptLimitsResponse(BaseModel):
    prompt_max_chars: int = 3000
    raw_image_prompt_max_chars: int = 3000
    asset_subject_max_chars: int = 160
    asset_extra_prompt_max_chars: int = 3000
    sprite_subject_max_chars: int = 3000
    sprite_row_prompt_max_chars: int = 600


class ImageModelsResponse(BaseModel):
    default: str
    models: list[str] = Field(default_factory=list)
    items: list[ImageModelInfoResponse] = Field(default_factory=list)
    limits: PromptLimitsResponse = Field(default_factory=PromptLimitsResponse)


@router.get("/image-models", response_model=ImageModelsResponse)
def available_image_models(
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> ImageModelsResponse:
    """返回当前可用的生图模型列表和默认模型。

    `models` 保留给旧前端兼容；新前端应优先读取 `items` 中的能力信息。
    """
    cfg: AppConfig = load_managed_pix_config(db, web_settings)
    infos = available_model_infos(cfg)
    if not infos:
        infos = []
    model_ids = [item.id for item in infos]
    default_model = public_image_model_id(cfg.image_gen.model) or (model_ids[0] if model_ids else "image2")
    if default_model not in model_ids:
        model_ids.insert(0, default_model)
    return ImageModelsResponse(
        default=default_model,
        models=model_ids,
        items=[ImageModelInfoResponse(**item.to_dict()) for item in infos],
        limits=PromptLimitsResponse(
            prompt_max_chars=max(1, int(cfg.image_gen.prompt_guard_max_chars)),
            raw_image_prompt_max_chars=max(1, int(cfg.image_gen.prompt_guard_max_chars)),
            asset_subject_max_chars=max(1, int(cfg.asset.subject_max_chars)),
            asset_extra_prompt_max_chars=max(1, int(cfg.asset.extra_prompt_max_chars)),
            sprite_subject_max_chars=max(1, int(cfg.sprite.subject_max_chars)),
            sprite_row_prompt_max_chars=max(1, int(cfg.sprite.row_prompt_max_chars)),
        ),
    )
