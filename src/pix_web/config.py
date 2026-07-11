"""Web 后端配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore[misc]
        return False


@dataclass(frozen=True)
class WebSettings:
    database_url: str = "sqlite:///pix_web.db"
    env: str = "dev"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: float = 30.0
    db_pool_recycle: int = 1800
    jwt_secret: str = "pix-web-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    session_cookie_secure: bool | None = None
    session_cookie_samesite: str = "lax"
    storage_root: Path = Path("web_outputs")
    max_upload_bytes: int = 10 * 1024 * 1024
    auto_create_db: bool = True
    pix_config_file: Path | None = None
    poll_interval_seconds: float = 2.0
    worker_concurrency: int = 3
    running_job_timeout_minutes: int = 60
    running_job_cleanup_interval_seconds: int = 60
    queue_backend: str = "database"
    redis_url: str = "redis://localhost:6379/0"
    rq_queue_name: str = "pix-jobs"
    rq_worker_class: str = "simple"
    public_base_url: str = "http://127.0.0.1:8000"
    frontend_base_url: str = ""
    cors_origins: tuple[str, ...] = ()
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_gateway: str = "https://openapi.alipay.com/gateway.do"
    alipay_mode: str = "auto"
    alipay_app_cert: str = ""
    alipay_public_cert: str = ""
    alipay_root_cert: str = ""
    wechat_app_id: str = ""
    wechat_mch_id: str = ""
    wechat_private_key: str = ""
    wechat_merchant_serial_no: str = ""
    wechat_api_v3_key: str = ""
    wechat_platform_cert: str = ""
    wechat_api_base: str = "https://api.mch.weixin.qq.com"
    email_provider: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    smtp_ssl: bool = False
    email_code_ttl_seconds: int = 600
    email_code_resend_seconds: int = 60
    email_code_max_attempts: int = 5
    email_debug_codes: bool = False
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    turnstile_email_window_seconds: int = 3600
    turnstile_email_max_without_challenge: int = 2
    turnstile_ip_window_seconds: int = 3600
    turnstile_ip_max_without_challenge: int = 5

    def session_cookie_secure_enabled(self) -> bool:
        """生产环境默认启用 Secure；开发环境可通过环境变量显式覆盖。"""
        if self.session_cookie_secure is None:
            return self.env == "prod"
        return self.session_cookie_secure

    def engine_pool_kwargs(self) -> dict[str, Any]:
        """SQLAlchemy 连接池参数（SQLite 会在 make_engine 内忽略）。"""
        return {
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
            "pool_recycle": self.db_pool_recycle,
        }


_DEFAULTS = {
    "PIX_WEB_DATABASE_URL": WebSettings.database_url,
    "PIX_WEB_DB_POOL_SIZE": str(WebSettings.db_pool_size),
    "PIX_WEB_DB_MAX_OVERFLOW": str(WebSettings.db_max_overflow),
    "PIX_WEB_DB_POOL_TIMEOUT": str(WebSettings.db_pool_timeout),
    "PIX_WEB_DB_POOL_RECYCLE": str(WebSettings.db_pool_recycle),
    "PIX_WEB_JWT_SECRET": WebSettings.jwt_secret,
    "PIX_WEB_SESSION_COOKIE_SECURE": "",
    "PIX_WEB_SESSION_COOKIE_SAMESITE": WebSettings.session_cookie_samesite,
    "PIX_WEB_STORAGE_ROOT": str(WebSettings.storage_root),
    "PIX_WEB_MAX_UPLOAD_BYTES": str(WebSettings.max_upload_bytes),
    "PIX_WEB_AUTO_CREATE_DB": "true",
    "PIX_WEB_WORKER_CONCURRENCY": str(WebSettings.worker_concurrency),
    "PIX_WEB_RUNNING_JOB_TIMEOUT_MINUTES": str(WebSettings.running_job_timeout_minutes),
    "PIX_WEB_RUNNING_JOB_CLEANUP_INTERVAL_SECONDS": str(WebSettings.running_job_cleanup_interval_seconds),
    "PIX_WEB_QUEUE_BACKEND": WebSettings.queue_backend,
    "PIX_WEB_REDIS_URL": WebSettings.redis_url,
    "PIX_WEB_RQ_QUEUE": WebSettings.rq_queue_name,
    "PIX_WEB_RQ_WORKER_CLASS": WebSettings.rq_worker_class,
    "PIX_WEB_PUBLIC_BASE_URL": WebSettings.public_base_url,
    "PIX_WEB_FRONTEND_BASE_URL": WebSettings.frontend_base_url,
    "PIX_WEB_CORS_ORIGINS": "",
    "ALIPAY_GATEWAY": WebSettings.alipay_gateway,
    "ALIPAY_MODE": WebSettings.alipay_mode,
    "WECHATPAY_API_BASE": WebSettings.wechat_api_base,
    "PIX_WEB_EMAIL_PROVIDER": WebSettings.email_provider,
    "PIX_WEB_SMTP_PORT": str(WebSettings.smtp_port),
    "PIX_WEB_SMTP_TLS": "true",
    "PIX_WEB_SMTP_SSL": "false",
    "PIX_WEB_EMAIL_CODE_TTL_SECONDS": str(WebSettings.email_code_ttl_seconds),
    "PIX_WEB_EMAIL_CODE_RESEND_SECONDS": str(WebSettings.email_code_resend_seconds),
    "PIX_WEB_EMAIL_CODE_MAX_ATTEMPTS": str(WebSettings.email_code_max_attempts),
    "PIX_WEB_EMAIL_DEBUG_CODES": "false",
    "PIX_WEB_TURNSTILE_ENABLED": "false",
    "PIX_WEB_TURNSTILE_VERIFY_URL": WebSettings.turnstile_verify_url,
    "PIX_WEB_TURNSTILE_EMAIL_WINDOW_SECONDS": str(WebSettings.turnstile_email_window_seconds),
    "PIX_WEB_TURNSTILE_EMAIL_MAX_WITHOUT_CHALLENGE": str(WebSettings.turnstile_email_max_without_challenge),
    "PIX_WEB_TURNSTILE_IP_WINDOW_SECONDS": str(WebSettings.turnstile_ip_window_seconds),
    "PIX_WEB_TURNSTILE_IP_MAX_WITHOUT_CHALLENGE": str(WebSettings.turnstile_ip_max_without_challenge),
}


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


def _env_optional_flag(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, _DEFAULTS.get(name, ""))
    return tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())


def load_web_settings() -> WebSettings:
    """从 .env 与环境变量加载 Web 配置。"""
    if not os.getenv("PIX_DISABLE_DOTENV"):
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()
    database_url = os.getenv("PIX_WEB_DATABASE_URL", _DEFAULTS["PIX_WEB_DATABASE_URL"])
    env = os.getenv("PIX_WEB_ENV", "dev").strip().lower()
    if env not in {"dev", "prod"}:
        env = "dev"
    db_pool_size = _env_int("PIX_WEB_DB_POOL_SIZE", WebSettings.db_pool_size, 1)
    db_max_overflow = _env_int("PIX_WEB_DB_MAX_OVERFLOW", WebSettings.db_max_overflow, 0)
    db_pool_recycle = _env_int("PIX_WEB_DB_POOL_RECYCLE", WebSettings.db_pool_recycle, -1)
    try:
        db_pool_timeout = max(1.0, float(os.getenv("PIX_WEB_DB_POOL_TIMEOUT", str(WebSettings.db_pool_timeout))))
    except ValueError:
        db_pool_timeout = WebSettings.db_pool_timeout
    jwt_secret = os.getenv("PIX_WEB_JWT_SECRET", _DEFAULTS["PIX_WEB_JWT_SECRET"])
    session_cookie_secure = _env_optional_flag("PIX_WEB_SESSION_COOKIE_SECURE")
    session_cookie_samesite = os.getenv(
        "PIX_WEB_SESSION_COOKIE_SAMESITE", _DEFAULTS["PIX_WEB_SESSION_COOKIE_SAMESITE"]
    ).strip().lower()
    if session_cookie_samesite not in {"lax", "strict", "none"}:
        session_cookie_samesite = WebSettings.session_cookie_samesite
    storage_root = Path(os.getenv("PIX_WEB_STORAGE_ROOT", _DEFAULTS["PIX_WEB_STORAGE_ROOT"]))
    pix_config_raw = os.getenv("PIX_WEB_PIX_CONFIG")
    upload_raw = os.getenv("PIX_WEB_MAX_UPLOAD_BYTES", _DEFAULTS["PIX_WEB_MAX_UPLOAD_BYTES"])
    poll_raw = os.getenv("PIX_WEB_POLL_INTERVAL_SECONDS", "2.0")
    token_raw = os.getenv("PIX_WEB_ACCESS_TOKEN_MINUTES", str(WebSettings.access_token_minutes))
    auto_create_raw = os.getenv("PIX_WEB_AUTO_CREATE_DB", _DEFAULTS["PIX_WEB_AUTO_CREATE_DB"])
    worker_concurrency = _env_int("PIX_WEB_WORKER_CONCURRENCY", WebSettings.worker_concurrency, 1)
    running_job_timeout_minutes = _env_int(
        "PIX_WEB_RUNNING_JOB_TIMEOUT_MINUTES",
        WebSettings.running_job_timeout_minutes,
        1,
    )
    running_job_cleanup_interval_seconds = _env_int(
        "PIX_WEB_RUNNING_JOB_CLEANUP_INTERVAL_SECONDS",
        WebSettings.running_job_cleanup_interval_seconds,
        1,
    )
    queue_backend = os.getenv("PIX_WEB_QUEUE_BACKEND", _DEFAULTS["PIX_WEB_QUEUE_BACKEND"]).lower()
    redis_url = os.getenv("PIX_WEB_REDIS_URL", _DEFAULTS["PIX_WEB_REDIS_URL"])
    rq_queue_name = os.getenv("PIX_WEB_RQ_QUEUE", _DEFAULTS["PIX_WEB_RQ_QUEUE"])
    rq_worker_class = os.getenv("PIX_WEB_RQ_WORKER_CLASS", _DEFAULTS["PIX_WEB_RQ_WORKER_CLASS"]).lower()
    public_base_url = os.getenv("PIX_WEB_PUBLIC_BASE_URL", _DEFAULTS["PIX_WEB_PUBLIC_BASE_URL"]).rstrip("/")
    frontend_base_url = os.getenv("PIX_WEB_FRONTEND_BASE_URL", _DEFAULTS["PIX_WEB_FRONTEND_BASE_URL"]).rstrip("/")
    cors_origins = _env_csv("PIX_WEB_CORS_ORIGINS")
    email_provider = os.getenv("PIX_WEB_EMAIL_PROVIDER", _DEFAULTS["PIX_WEB_EMAIL_PROVIDER"]).strip().lower()
    alipay_mode_raw = os.getenv("ALIPAY_MODE", _DEFAULTS["ALIPAY_MODE"]).strip().lower()
    smtp_port = _env_int("PIX_WEB_SMTP_PORT", WebSettings.smtp_port, 1)
    smtp_ssl = _env_flag("PIX_WEB_SMTP_SSL", smtp_port == 465 or WebSettings.smtp_ssl)
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
        env=env,
        db_pool_size=db_pool_size,
        db_max_overflow=db_max_overflow,
        db_pool_timeout=db_pool_timeout,
        db_pool_recycle=db_pool_recycle,
        jwt_secret=jwt_secret,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        storage_root=storage_root,
        max_upload_bytes=max_upload_bytes,
        auto_create_db=auto_create_raw.lower() not in {"0", "false", "no", "off"},
        pix_config_file=Path(pix_config_raw) if pix_config_raw else None,
        poll_interval_seconds=poll_interval,
        worker_concurrency=worker_concurrency,
        running_job_timeout_minutes=running_job_timeout_minutes,
        running_job_cleanup_interval_seconds=running_job_cleanup_interval_seconds,
        access_token_minutes=access_token_minutes,
        queue_backend=queue_backend if queue_backend in {"database", "rq"} else WebSettings.queue_backend,
        redis_url=redis_url,
        rq_queue_name=rq_queue_name or WebSettings.rq_queue_name,
        rq_worker_class=rq_worker_class if rq_worker_class in {"simple", "default"} else WebSettings.rq_worker_class,
        public_base_url=public_base_url,
        frontend_base_url=frontend_base_url,
        cors_origins=cors_origins,
        alipay_app_id=os.getenv("ALIPAY_APP_ID", ""),
        alipay_private_key=os.getenv("ALIPAY_PRIVATE_KEY", ""),
        alipay_public_key=os.getenv("ALIPAY_PUBLIC_KEY", ""),
        alipay_gateway=os.getenv("ALIPAY_GATEWAY", _DEFAULTS["ALIPAY_GATEWAY"]),
        alipay_mode=alipay_mode_raw if alipay_mode_raw in {"auto", "public_key", "certificate"} else WebSettings.alipay_mode,
        alipay_app_cert=os.getenv("ALIPAY_APP_CERT", "") or os.getenv("ALIPAY_APP_CERT_PATH", ""),
        alipay_public_cert=os.getenv("ALIPAY_PUBLIC_CERT", "") or os.getenv("ALIPAY_PUBLIC_CERT_PATH", ""),
        alipay_root_cert=os.getenv("ALIPAY_ROOT_CERT", "") or os.getenv("ALIPAY_ROOT_CERT_PATH", ""),
        wechat_app_id=os.getenv("WECHATPAY_APP_ID", ""),
        wechat_mch_id=os.getenv("WECHATPAY_MCH_ID", ""),
        wechat_private_key=os.getenv("WECHATPAY_PRIVATE_KEY", ""),
        wechat_merchant_serial_no=os.getenv("WECHATPAY_MERCHANT_SERIAL_NO", ""),
        wechat_api_v3_key=os.getenv("WECHATPAY_API_V3_KEY", ""),
        wechat_platform_cert=os.getenv("WECHATPAY_PLATFORM_CERT", ""),
        wechat_api_base=os.getenv("WECHATPAY_API_BASE", _DEFAULTS["WECHATPAY_API_BASE"]).rstrip("/"),
        email_provider=email_provider if email_provider in {"console", "smtp"} else WebSettings.email_provider,
        smtp_host=os.getenv("PIX_WEB_SMTP_HOST", ""),
        smtp_port=smtp_port,
        smtp_user=os.getenv("PIX_WEB_SMTP_USER", ""),
        smtp_password=os.getenv("PIX_WEB_SMTP_PASSWORD", ""),
        smtp_from=os.getenv("PIX_WEB_SMTP_FROM", ""),
        smtp_tls=_env_flag("PIX_WEB_SMTP_TLS", WebSettings.smtp_tls),
        smtp_ssl=smtp_ssl,
        email_code_ttl_seconds=_env_int(
            "PIX_WEB_EMAIL_CODE_TTL_SECONDS", WebSettings.email_code_ttl_seconds, 60
        ),
        email_code_resend_seconds=_env_int(
            "PIX_WEB_EMAIL_CODE_RESEND_SECONDS", WebSettings.email_code_resend_seconds, 0
        ),
        email_code_max_attempts=_env_int(
            "PIX_WEB_EMAIL_CODE_MAX_ATTEMPTS", WebSettings.email_code_max_attempts, 1
        ),
        email_debug_codes=_env_flag("PIX_WEB_EMAIL_DEBUG_CODES", WebSettings.email_debug_codes),
        turnstile_enabled=_env_flag("PIX_WEB_TURNSTILE_ENABLED", WebSettings.turnstile_enabled),
        turnstile_site_key=os.getenv("PIX_WEB_TURNSTILE_SITE_KEY", ""),
        turnstile_secret_key=os.getenv("PIX_WEB_TURNSTILE_SECRET_KEY", ""),
        turnstile_verify_url=os.getenv(
            "PIX_WEB_TURNSTILE_VERIFY_URL", _DEFAULTS["PIX_WEB_TURNSTILE_VERIFY_URL"]
        ).strip()
        or WebSettings.turnstile_verify_url,
        turnstile_email_window_seconds=_env_int(
            "PIX_WEB_TURNSTILE_EMAIL_WINDOW_SECONDS",
            WebSettings.turnstile_email_window_seconds,
            0,
        ),
        turnstile_email_max_without_challenge=_env_int(
            "PIX_WEB_TURNSTILE_EMAIL_MAX_WITHOUT_CHALLENGE",
            WebSettings.turnstile_email_max_without_challenge,
            0,
        ),
        turnstile_ip_window_seconds=_env_int(
            "PIX_WEB_TURNSTILE_IP_WINDOW_SECONDS",
            WebSettings.turnstile_ip_window_seconds,
            0,
        ),
        turnstile_ip_max_without_challenge=_env_int(
            "PIX_WEB_TURNSTILE_IP_MAX_WITHOUT_CHALLENGE",
            WebSettings.turnstile_ip_max_without_challenge,
            0,
        ),
    )
