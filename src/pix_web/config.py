"""Web 后端配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebSettings:
    database_url: str = "sqlite:///pix_web.db"
    jwt_secret: str = "pix-web-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    storage_root: Path = Path("web_outputs")
    max_upload_bytes: int = 10 * 1024 * 1024
    auto_create_db: bool = True
    pix_config_file: Path | None = None
    poll_interval_seconds: float = 2.0


_DEFAULTS = {
    "PIX_WEB_DATABASE_URL": WebSettings.database_url,
    "PIX_WEB_JWT_SECRET": WebSettings.jwt_secret,
    "PIX_WEB_STORAGE_ROOT": str(WebSettings.storage_root),
    "PIX_WEB_MAX_UPLOAD_BYTES": str(WebSettings.max_upload_bytes),
    "PIX_WEB_AUTO_CREATE_DB": "true",
}


def load_web_settings() -> WebSettings:
    """从环境变量加载 Web 配置。"""
    database_url = os.getenv("PIX_WEB_DATABASE_URL", _DEFAULTS["PIX_WEB_DATABASE_URL"])
    jwt_secret = os.getenv("PIX_WEB_JWT_SECRET", _DEFAULTS["PIX_WEB_JWT_SECRET"])
    storage_root = Path(os.getenv("PIX_WEB_STORAGE_ROOT", _DEFAULTS["PIX_WEB_STORAGE_ROOT"]))
    pix_config_raw = os.getenv("PIX_WEB_PIX_CONFIG")
    upload_raw = os.getenv("PIX_WEB_MAX_UPLOAD_BYTES", _DEFAULTS["PIX_WEB_MAX_UPLOAD_BYTES"])
    poll_raw = os.getenv("PIX_WEB_POLL_INTERVAL_SECONDS", "2.0")
    token_raw = os.getenv("PIX_WEB_ACCESS_TOKEN_MINUTES", str(WebSettings.access_token_minutes))
    auto_create_raw = os.getenv("PIX_WEB_AUTO_CREATE_DB", _DEFAULTS["PIX_WEB_AUTO_CREATE_DB"])
    try:
        poll_interval = max(0.1, float(poll_raw))
    except ValueError:
        poll_interval = WebSettings.poll_interval_seconds
    try:
        access_token_minutes = max(1, int(token_raw))
    except ValueError:
        access_token_minutes = WebSettings.access_token_minutes
    try:
        max_upload_bytes = max(1024, int(upload_raw))
    except ValueError:
        max_upload_bytes = WebSettings.max_upload_bytes
    return WebSettings(
        database_url=database_url,
        jwt_secret=jwt_secret,
        storage_root=storage_root,
        max_upload_bytes=max_upload_bytes,
        auto_create_db=auto_create_raw.lower() not in {"0", "false", "no", "off"},
        pix_config_file=Path(pix_config_raw) if pix_config_raw else None,
        poll_interval_seconds=poll_interval,
        access_token_minutes=access_token_minutes,
    )
