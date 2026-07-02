"""接口限流（基于 slowapi），用于抵御登录 / 验证码接口的暴力破解与滥用。

限流 key 复用与 :mod:`pix_web.routers.auth` 一致的客户端 IP 提取逻辑（读取
``X-Forwarded-For`` / ``X-Real-IP``），避免在 nginx 等反向代理后所有请求被识别为
同一个代理 IP 而触发全局限流。

存储优先使用 Redis（多进程/多副本共享计数），未配置 Redis 时回退进程内存。
可用环境变量 ``PIX_WEB_RATE_LIMIT_ENABLED=false`` 全局关闭（默认开启），便于本地
开发与测试。
"""

from __future__ import annotations

import os
import sys

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def client_ip_key(request: Request) -> str:
    """与 auth._client_ip 同口径的限流 key：优先取代理转发头。"""
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded_for:
        return forwarded_for[:64]
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip[:64]
    return get_remote_address(request)


def rate_limit_enabled() -> bool:
    # 单元测试直接调用端点函数（非 HTTP 层），不应触发限流；pytest 运行时自动关闭。
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return os.getenv("PIX_WEB_RATE_LIMIT_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _storage_uri() -> str | None:
    backend = os.getenv("PIX_WEB_QUEUE_BACKEND", "database").strip().lower()
    redis_url = os.getenv("PIX_WEB_REDIS_URL", "").strip()
    # 仅当明确使用 rq/redis 时才把限流计数放到 Redis，保持跨副本一致；
    # database 模式下默认用进程内存，避免为限流强依赖 Redis。
    if backend == "rq" and redis_url:
        return redis_url
    return None


limiter = Limiter(
    key_func=client_ip_key,
    enabled=rate_limit_enabled(),
    storage_uri=_storage_uri(),
    # 关闭装饰器内联注入 X-RateLimit-* 头：限流由 SlowAPIMiddleware 在 HTTP 层强制，
    # 内联注入会在单元测试直接调用端点函数（返回 Pydantic 模型而非 Response）时报错。
    headers_enabled=False,
)

# 各类敏感接口的默认限额（可按需调整）。
LOGIN_RATE_LIMIT = "10/minute"
EMAIL_CODE_RATE_LIMIT = "5/minute"
PASSWORD_RESET_RATE_LIMIT = "10/minute"
REGISTER_RATE_LIMIT = "10/minute"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """统一的限流响应：429 + 中文提示，附带 Retry-After。"""
    retry_after = getattr(exc, "retry_after", None)
    headers = {"Retry-After": str(int(retry_after))} if retry_after else {}
    return JSONResponse(
        status_code=429,
        content={"detail": "请求过于频繁，请稍后再试"},
        headers=headers,
    )
