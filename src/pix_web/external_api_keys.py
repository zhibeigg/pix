"""长期对外 API Key 的生成、校验与 scope 权限。"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import ExternalApiKey, User, utcnow
from pix_web.security import get_db

API_KEY_SCOPES: tuple[str, ...] = (
    "me:read",
    "balance:read",
    "models:read",
    "uploads:create",
    "jobs:create",
    "jobs:read",
    "files:read",
    "characters:read",
    "characters:write",
)
DEFAULT_API_KEY_SCOPES: tuple[str, ...] = API_KEY_SCOPES
API_KEY_PREFIX = "pix_live_"
API_KEY_HEX_BYTES = 32
API_KEY_PATTERN = re.compile(r"^pix_live_[A-Za-z0-9_-]{32,128}$")


@dataclass(frozen=True)
class ExternalApiPrincipal:
    user: User
    api_key: ExternalApiKey
    scopes: tuple[str, ...]


def normalize_api_key_scopes(scopes: list[str] | tuple[str, ...] | None, *, default_all: bool = True) -> list[str]:
    if not scopes:
        return list(DEFAULT_API_KEY_SCOPES) if default_all else []
    allowed = set(API_KEY_SCOPES)
    normalized: list[str] = []
    for raw in scopes:
        scope = str(raw or "").strip()
        if not scope:
            continue
        if scope not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"未知 API 权限：{scope}",
            )
        if scope not in normalized:
            normalized.append(scope)
    return normalized or (list(DEFAULT_API_KEY_SCOPES) if default_all else [])


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_hex(API_KEY_HEX_BYTES)}"


def normalize_custom_api_key(value: str | None) -> str | None:
    key = (value or "").strip()
    if not key:
        return None
    if not API_KEY_PATTERN.fullmatch(key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="API Key 格式无效：必须以 pix_live_ 开头，并仅包含字母、数字、下划线或连字符",
        )
    return key


def key_display_prefix(value: str) -> str:
    return value[:22]


def create_external_api_key(
    db: Session,
    user: User,
    *,
    name: str,
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
    custom_key: str | None = None,
) -> tuple[str, ExternalApiKey]:
    raw_key = normalize_custom_api_key(custom_key) or generate_api_key()
    key_hash = hash_api_key(raw_key)
    if db.scalar(select(ExternalApiKey.id).where(ExternalApiKey.key_hash == key_hash)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="API Key 已存在，请重新生成")
    row = ExternalApiKey(
        user_id=user.id,
        name=(name or "").strip()[:120] or "API Key",
        key_prefix=key_display_prefix(raw_key),
        key_hash=key_hash,
        scopes=normalize_api_key_scopes(scopes),
        enabled=True,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return raw_key, row


def _extract_api_key(request: Request) -> str:
    header_key = (request.headers.get("x-pix-api-key") or "").strip()
    if header_key:
        return header_key
    authorization = (request.headers.get("authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _is_expired(row: ExternalApiKey) -> bool:
    if row.expires_at is None:
        return False
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= datetime.now(timezone.utc)


def authenticate_external_api_key(request: Request, db: Session) -> ExternalApiPrincipal:
    raw_key = _extract_api_key(request)
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 API Key")
    row = db.scalar(select(ExternalApiKey).where(ExternalApiKey.key_hash == hash_api_key(raw_key)))
    if row is None or not row.enabled or row.revoked_at is not None or _is_expired(row):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效或已停用")
    user = db.get(User, row.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 所属用户不可用")
    scopes = tuple(normalize_api_key_scopes([str(scope) for scope in (row.scopes or [])]))
    row.last_used_at = utcnow()
    db.commit()
    return ExternalApiPrincipal(user=user, api_key=row, scopes=scopes)


def require_external_scope(scope: str) -> Callable[[Request, Session], ExternalApiPrincipal]:
    def dependency(request: Request, db: Session = Depends(get_db)) -> ExternalApiPrincipal:
        principal = authenticate_external_api_key(request, db)
        if scope not in principal.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"API Key 缺少权限：{scope}")
        return principal

    return dependency
