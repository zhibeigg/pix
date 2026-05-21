"""认证与权限。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.models import User

_password_hasher = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
_PRIVATE_PROXY_NETWORKS = tuple(
    ip_network(network)
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fc00::/7",
        "fe80::/10",
    )
)


def _hostname_from_value(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if "://" in raw:
        return (urlsplit(raw).hostname or "").strip("[]").lower()
    try:
        ip_address(raw.strip("[]"))
        return raw.strip("[]").lower()
    except ValueError:
        return (urlsplit(f"//{raw}").hostname or "").strip("[]").lower()


def _ip_from_hostname(value: str | None):
    if not value:
        return None
    host = _hostname_from_value(value)
    try:
        return ip_address(host)
    except ValueError:
        return None


def _is_local_hostname(value: str | None) -> bool:
    if not value:
        return False
    host = _hostname_from_value(value)
    if host == "localhost" or host.endswith(".localhost"):
        return True
    parsed = _ip_from_hostname(value)
    if parsed is None:
        return False
    if parsed.is_loopback:
        return True
    mapped = getattr(parsed, "ipv4_mapped", None)
    return bool(mapped and mapped.is_loopback)


def _is_private_or_local_hostname(value: str | None) -> bool:
    if _is_local_hostname(value):
        return True
    parsed = _ip_from_hostname(value)
    if parsed is None:
        return False
    mapped = getattr(parsed, "ipv4_mapped", None)
    if mapped is not None:
        parsed = mapped
    return any(parsed in network for network in _PRIVATE_PROXY_NETWORKS)


def _local_host_header(request: Request) -> bool:
    return _is_local_hostname(request.headers.get("x-forwarded-host")) or _is_local_hostname(request.headers.get("host"))


def _local_browser_headers(request: Request) -> bool:
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value and not _is_local_hostname(value):
            return False
    return True


def is_local_request(request: Request) -> bool:
    """Return whether a request is from a local browser/dev client, including local reverse proxies."""
    if not _local_host_header(request) or not _local_browser_headers(request):
        return False
    client_host = request.client.host if request.client else ""
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    return _is_local_hostname(client_host) or _is_private_or_local_hostname(client_host) or _is_private_or_local_hostname(forwarded_for)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user: User, settings: WebSettings, *, local_only: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    if local_only:
        payload["local_only"] = True
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_db(request: Request) -> Session:
    session_factory = request.app.state.SessionLocal
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_settings(request: Request) -> WebSettings:
    return request.app.state.web_settings


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", "0"))
    except Exception as exc:
        raise credentials_error from exc
    if payload.get("local_only") is True and not is_local_request(request):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise credentials_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))
