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
    queue_backend: str = "database"
    redis_url: str = "redis://localhost:6379/0"
    rq_queue_name: str = "pix-jobs"
    rq_worker_class: str = "simple"
    public_base_url: str = "http://127.0.0.1:8000"
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_gateway: str = "https://openapi.alipay.com/gateway.do"
    wechat_app_id: str = ""
    wechat_mch_id: str = ""
    wechat_private_key: str = ""
    wechat_merchant_serial_no: str = ""
    wechat_api_v3_key: str = ""
    wechat_platform_cert: str = ""
    wechat_api_base: str = "https://api.mch.weixin.qq.com"


_DEFAULTS = {
    "PIX_WEB_DATABASE_URL": WebSettings.database_url,
    "PIX_WEB_JWT_SECRET": WebSettings.jwt_secret,
    "PIX_WEB_STORAGE_ROOT": str(WebSettings.storage_root),
    "PIX_WEB_MAX_UPLOAD_BYTES": str(WebSettings.max_upload_bytes),
    "PIX_WEB_AUTO_CREATE_DB": "true",
    "PIX_WEB_QUEUE_BACKEND": WebSettings.queue_backend,
    "PIX_WEB_REDIS_URL": WebSettings.redis_url,
    "PIX_WEB_RQ_QUEUE": WebSettings.rq_queue_name,
    "PIX_WEB_RQ_WORKER_CLASS": WebSettings.rq_worker_class,
    "PIX_WEB_PUBLIC_BASE_URL": WebSettings.public_base_url,
    "ALIPAY_GATEWAY": WebSettings.alipay_gateway,
    "WECHATPAY_API_BASE": WebSettings.wechat_api_base,
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
    queue_backend = os.getenv("PIX_WEB_QUEUE_BACKEND", _DEFAULTS["PIX_WEB_QUEUE_BACKEND"]).lower()
    redis_url = os.getenv("PIX_WEB_REDIS_URL", _DEFAULTS["PIX_WEB_REDIS_URL"])
    rq_queue_name = os.getenv("PIX_WEB_RQ_QUEUE", _DEFAULTS["PIX_WEB_RQ_QUEUE"])
    rq_worker_class = os.getenv("PIX_WEB_RQ_WORKER_CLASS", _DEFAULTS["PIX_WEB_RQ_WORKER_CLASS"]).lower()
    public_base_url = os.getenv("PIX_WEB_PUBLIC_BASE_URL", _DEFAULTS["PIX_WEB_PUBLIC_BASE_URL"]).rstrip("/")
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
        queue_backend=queue_backend if queue_backend in {"database", "rq"} else WebSettings.queue_backend,
        redis_url=redis_url,
        rq_queue_name=rq_queue_name or WebSettings.rq_queue_name,
        rq_worker_class=rq_worker_class if rq_worker_class in {"simple", "default"} else WebSettings.rq_worker_class,
        public_base_url=public_base_url,
        alipay_app_id=os.getenv("ALIPAY_APP_ID", ""),
        alipay_private_key=os.getenv("ALIPAY_PRIVATE_KEY", ""),
        alipay_public_key=os.getenv("ALIPAY_PUBLIC_KEY", ""),
        alipay_gateway=os.getenv("ALIPAY_GATEWAY", _DEFAULTS["ALIPAY_GATEWAY"]),
        wechat_app_id=os.getenv("WECHATPAY_APP_ID", ""),
        wechat_mch_id=os.getenv("WECHATPAY_MCH_ID", ""),
        wechat_private_key=os.getenv("WECHATPAY_PRIVATE_KEY", ""),
        wechat_merchant_serial_no=os.getenv("WECHATPAY_MERCHANT_SERIAL_NO", ""),
        wechat_api_v3_key=os.getenv("WECHATPAY_API_V3_KEY", ""),
        wechat_platform_cert=os.getenv("WECHATPAY_PLATFORM_CERT", ""),
        wechat_api_base=os.getenv("WECHATPAY_API_BASE", _DEFAULTS["WECHATPAY_API_BASE"]).rstrip("/"),
    )
