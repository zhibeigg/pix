"""认证与权限。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.models import User

_password_hasher = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
SESSION_COOKIE_NAME = "pix_web_session"
_SAFE_BROWSER_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
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


def _canonical_origin(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 80 if parsed.scheme == "http" else 443
    port_suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{parsed.scheme}://{host}{port_suffix}"


def _request_base_origin(request: Request) -> str | None:
    # 不直接信任客户端可伪造的 X-Forwarded-*；可信代理应由 ASGI 服务器先规范化 request.url。
    host = (request.headers.get("host") or "").strip()
    return _canonical_origin(f"{request.url.scheme}://{host}") if host else None


def _allowed_browser_origins(request: Request, settings: WebSettings) -> set[str]:
    values = [
        *settings.cors_origins,
        settings.frontend_base_url,
        settings.public_base_url,
        _request_base_origin(request) or "",
    ]
    return {origin for value in values if (origin := _canonical_origin(value)) is not None}


def require_browser_origin(request: Request, settings: WebSettings) -> None:
    """Cookie 会话的写请求必须来自当前站点或显式配置的前端 Origin。"""
    if request.method.upper() in _SAFE_BROWSER_METHODS:
        return
    origin = _canonical_origin(request.headers.get("origin"))
    if origin is not None and origin in _allowed_browser_origins(request, settings):
        return
    if settings.env != "prod" and origin is not None and _is_local_hostname(origin):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请求来源不受信任")


def set_session_cookie(response: Response, token: str, settings: WebSettings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max(60, settings.access_token_minutes * 60),
        path="/",
        secure=settings.session_cookie_secure_enabled(),
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def clear_session_cookie(response: Response, settings: WebSettings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure_enabled(),
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


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
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    if local_only:
        payload["local_only"] = True
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# 文件访问票据：短时效、单用途（scope=file）令牌，供 <img>/下载链接以 query 参数携带，
# 避免把长期登录 token 暴露在 URL、浏览器历史、Referer 与反代日志中。
FILE_TICKET_SCOPE = "file"
FILE_TICKET_TTL_SECONDS = 300


def create_file_ticket(user: User, settings: WebSettings, *, ttl_seconds: int = FILE_TICKET_TTL_SECONDS) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "scope": FILE_TICKET_SCOPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=max(30, ttl_seconds))).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_file_ticket(token: str, settings: WebSettings) -> int | None:
    """校验文件票据，返回用户 id；非票据或无效时返回 None（调用方可回退旧 token 校验）。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception:
        return None
    if payload.get("scope") != FILE_TICKET_SCOPE:
        return None
    try:
        return int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        return None


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
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    effective_token = token or cookie_token
    if not effective_token:
        raise credentials_error
    if token is None and cookie_token:
        require_browser_origin(request, settings)
    try:
        payload = jwt.decode(effective_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", "0"))
    except Exception as exc:
        raise credentials_error from exc
    # 文件票据等受限 JWT 绝不能提升为完整会话；无 token_type 的旧 access token 在过渡期继续兼容。
    if payload.get("scope") is not None or payload.get("token_type") not in {None, "access"}:
        raise credentials_error
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
