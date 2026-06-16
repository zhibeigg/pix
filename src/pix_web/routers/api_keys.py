"""用户对外 API Key 管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.external_api_keys import create_external_api_key, normalize_api_key_scopes
from pix_web.models import ExternalApiKey, User, utcnow
from pix_web.schemas import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse, ApiKeyUpdateRequest
from pix_web.security import get_current_user, get_db

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _get_user_key(db: Session, user: User, key_id: int) -> ExternalApiKey:
    row = db.scalar(select(ExternalApiKey).where(ExternalApiKey.id == key_id, ExternalApiKey.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
    return row


@router.get("", response_model=list[ApiKeyResponse])
def list_api_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ExternalApiKey]:
    return list(
        db.scalars(
            select(ExternalApiKey)
            .where(ExternalApiKey.user_id == user.id)
            .order_by(ExternalApiKey.created_at.desc(), ExternalApiKey.id.desc())
        )
    )


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    req: ApiKeyCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreateResponse:
    raw_key, row = create_external_api_key(
        db,
        user,
        name=req.name,
        scopes=req.scopes,
        expires_at=req.expires_at,
    )
    return ApiKeyCreateResponse(key=raw_key, item=ApiKeyResponse.model_validate(row))


@router.patch("/{key_id}", response_model=ApiKeyResponse)
def update_api_key(
    key_id: int,
    req: ApiKeyUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExternalApiKey:
    row = _get_user_key(db, user, key_id)
    fields = req.model_fields_set
    if "name" in fields and req.name is not None:
        row.name = req.name.strip()[:120] or row.name
    if "enabled" in fields and req.enabled is not None:
        row.enabled = bool(req.enabled)
        if row.enabled and row.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已撤销的 API Key 不能重新启用")
    if "scopes" in fields and req.scopes is not None:
        row.scopes = normalize_api_key_scopes(req.scopes)
    if "expires_at" in fields:
        row.expires_at = req.expires_at
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{key_id}", response_model=ApiKeyResponse)
def revoke_api_key(
    key_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExternalApiKey:
    row = _get_user_key(db, user, key_id)
    if row.revoked_at is None:
        row.revoked_at = utcnow()
    row.enabled = False
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
