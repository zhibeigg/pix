"""公开设置端点（无需认证）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pix.api.image_model_registry import available_model_infos
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


class ImageModelsResponse(BaseModel):
    default: str
    models: list[str] = Field(default_factory=list)
    items: list[ImageModelInfoResponse] = Field(default_factory=list)


@router.get("/image-models", response_model=ImageModelsResponse)
def available_image_models(
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> ImageModelsResponse:
    """返回当前可用的生图模型列表和默认模型。

    `models` 保留给旧前端兼容；新前端应优先读取 `items` 中的能力信息。
    """
    cfg: AppConfig = load_managed_pix_config(db, web_settings)
    default_model = cfg.image_gen.model or "gpt-image-2"
    infos = available_model_infos(cfg)
    if not infos:
        infos = []
    model_ids = [item.id for item in infos]
    if default_model not in model_ids:
        model_ids.insert(0, default_model)
    return ImageModelsResponse(
        default=default_model,
        models=model_ids,
        items=[ImageModelInfoResponse(**item.to_dict()) for item in infos],
    )
