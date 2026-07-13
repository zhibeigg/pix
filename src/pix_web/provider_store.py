"""数据库为准的上游供应商：DB↔配置转换、注入 AppConfig、首次种子。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pix.config import AppConfig, ImageProviderConfig, ImageProviderModelConfig, load_config
from pix_web.models import ImageProvider

_MODEL_STR_FIELDS = ("id", "provider_model", "label", "protocol", "endpoint", "edit_endpoint", "edit_mode")
_MODEL_LIST_FIELDS = ("operations", "sizes", "qualities", "output_formats")


def _model_from_dict(data: dict[str, Any]) -> ImageProviderModelConfig:
    model = ImageProviderModelConfig()
    for fld in _MODEL_STR_FIELDS:
        value = data.get(fld)
        if isinstance(value, str):
            setattr(model, fld, value)
    for fld in _MODEL_LIST_FIELDS:
        value = data.get(fld)
        if isinstance(value, list):
            setattr(model, fld, [str(item) for item in value])
    if isinstance(data.get("supports_n"), bool):
        model.supports_n = data["supports_n"]
    if isinstance(data.get("requires_public_image_url"), bool):
        model.requires_public_image_url = data["requires_public_image_url"]
    if isinstance(data.get("extra"), dict):
        model.extra = dict(data["extra"])
    return model


def _model_to_dict(model: ImageProviderModelConfig) -> dict[str, Any]:
    return {
        "id": model.id,
        "provider_model": model.provider_model,
        "label": model.label,
        "protocol": model.protocol,
        "operations": list(model.operations),
        "sizes": list(model.sizes),
        "qualities": list(model.qualities),
        "output_formats": list(model.output_formats),
        "edit_mode": model.edit_mode,
        "supports_n": bool(model.supports_n),
        "requires_public_image_url": bool(model.requires_public_image_url),
        "extra": dict(model.extra),
    }


def _config_from_row(row: ImageProvider) -> ImageProviderConfig:
    return ImageProviderConfig(
        id=row.id,
        display_name=row.display_name or row.id,
        enabled=bool(row.enabled),
        base_url=row.base_url or "",
        api_key_env=row.api_key_env or "",
        api_key=row.api_key or None,
        priority=int(row.priority or 100),
        discover_models=bool(row.discover_models),
        protocols=[str(p) for p in (row.protocols or [])] or ["openai_images"],
        models=[_model_from_dict(m) for m in (row.models or []) if isinstance(m, dict)],
    )


def image_providers_from_db(db: Session) -> list[ImageProviderConfig]:
    rows = db.scalars(select(ImageProvider)).all()
    return [_config_from_row(row) for row in rows]


def apply_db_image_providers(cfg: AppConfig, db: Session) -> AppConfig:
    """DB 有供应商时整体替换 cfg.image_providers（DB 为唯一真相源），按 priority 排序。"""
    providers = image_providers_from_db(db)
    if providers:
        providers.sort(key=lambda item: int(item.priority or 100))
        cfg.image_providers = providers
    return cfg


def ensure_seeded_image_providers(db: Session) -> None:
    """首次启动：表为空时，从 load_config()（已合并 config.toml + .env）导入供应商做种子。幂等。"""
    if db.scalar(select(ImageProvider).limit(1)) is not None:
        return
    cfg = load_config()
    for provider in cfg.image_providers:
        if not provider.id:
            continue
        db.add(
            ImageProvider(
                id=provider.id,
                display_name=provider.display_name or provider.id,
                enabled=bool(provider.enabled),
                base_url=provider.base_url or "",
                api_key=provider.api_key or "",
                api_key_env=provider.api_key_env or "",
                priority=int(provider.priority or 100),
                discover_models=bool(provider.discover_models),
                protocols=list(provider.protocols or []),
                models=[_model_to_dict(m) for m in (provider.models or [])],
                preset_key=provider.id,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # 并发启动时另一进程已种子，安全忽略
