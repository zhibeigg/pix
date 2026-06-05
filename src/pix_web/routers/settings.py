"""公开设置端点（无需认证）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pix.config import AppConfig
from pix_web.security import get_db, get_settings
from pix_web.config import WebSettings
from pix_web.system_settings import load_managed_pix_config

router = APIRouter(prefix="/settings", tags=["settings"])

# 支持的生图模型列表（与 is_gemini_model() 对应）
IMAGE_MODELS = ["gpt-image-2", "gemini-3.1-flash-image-preview"]


class ImageModelsResponse(BaseModel):
    default: str
    models: list[str] = Field(default_factory=list)


@router.get("/image-models", response_model=ImageModelsResponse)
def available_image_models(
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> ImageModelsResponse:
    """返回当前可用的生图模型列表和默认模型。"""
    cfg: AppConfig = load_managed_pix_config(db, web_settings)
    default_model = cfg.image_gen.model or "gpt-image-2"
    return ImageModelsResponse(
        default=default_model,
        models=IMAGE_MODELS,
    )
