"""管理员：上游生图供应商 CRUD + 预设目录。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import ImageProvider, User
from pix_web.provider_presets import PROVIDER_PRESETS, preset_to_dict
from pix_web.schemas import (
    ImageProviderCreateRequest,
    ImageProviderModelPayload,
    ImageProviderPresetResponse,
    ImageProviderResponse,
    ImageProviderUpdateRequest,
)
from pix_web.security import get_db, require_admin

router = APIRouter(prefix="/admin/providers", tags=["admin"])

PROTOCOL_WHITELIST = {"openai_images", "midjourney", "ideogram", "fal", "kling", "gemini_native", "shengsuanyun"}


def _to_response(row: ImageProvider) -> ImageProviderResponse:
    return ImageProviderResponse(
        id=row.id,
        display_name=row.display_name or row.id,
        enabled=bool(row.enabled),
        base_url=row.base_url or "",
        has_api_key=bool(row.api_key),
        api_key_env=row.api_key_env or "",
        priority=int(row.priority or 100),
        discover_models=bool(row.discover_models),
        protocols=[str(p) for p in (row.protocols or [])],
        models=[ImageProviderModelPayload(**m) for m in (row.models or []) if isinstance(m, dict)],
        preset_key=row.preset_key,
    )


def _validate(protocols: list[str], base_url: str) -> None:
    if not protocols:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="至少选择一个协议")
    for proto in protocols:
        if proto not in PROTOCOL_WHITELIST:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"未知协议：{proto}")
    if not base_url.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="base_url 不能为空")


@router.get("", response_model=list[ImageProviderResponse])
def list_providers(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[ImageProviderResponse]:
    rows = db.scalars(select(ImageProvider).order_by(ImageProvider.priority.asc(), ImageProvider.id.asc())).all()
    return [_to_response(row) for row in rows]


@router.get("/presets", response_model=list[ImageProviderPresetResponse])
def list_presets(_admin: User = Depends(require_admin)) -> list[ImageProviderPresetResponse]:
    return [ImageProviderPresetResponse(**preset_to_dict(preset)) for preset in PROVIDER_PRESETS]


@router.post("", response_model=ImageProviderResponse)
def create_provider(
    req: ImageProviderCreateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImageProviderResponse:
    if db.get(ImageProvider, req.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="供应商已存在")
    _validate(req.protocols, req.base_url)
    row = ImageProvider(
        id=req.id,
        display_name=req.display_name or req.id,
        enabled=req.enabled,
        base_url=req.base_url.strip(),
        api_key=req.api_key,
        api_key_env=req.api_key_env,
        priority=req.priority,
        discover_models=req.discover_models,
        protocols=list(req.protocols),
        models=[m.model_dump() for m in req.models],
        preset_key=req.preset_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{provider_id}", response_model=ImageProviderResponse)
def update_provider(
    provider_id: str,
    req: ImageProviderUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImageProviderResponse:
    row = db.get(ImageProvider, provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    _validate(req.protocols, req.base_url)
    row.display_name = req.display_name or provider_id
    row.enabled = req.enabled
    row.base_url = req.base_url.strip()
    row.api_key_env = req.api_key_env
    row.priority = req.priority
    row.discover_models = req.discover_models
    row.protocols = list(req.protocols)
    row.models = [m.model_dump() for m in req.models]
    if req.clear_api_key:
        row.api_key = ""
    elif req.api_key:
        row.api_key = req.api_key
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    row = db.get(ImageProvider, provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    db.delete(row)
    db.commit()
    return {"deleted": True}
