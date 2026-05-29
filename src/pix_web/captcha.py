"""人机校验（Cloudflare Turnstile）。

只在 ``WebSettings.turnstile_enabled`` 为真且 secret_key 已配置时生效。
通过 :func:`verify_turnstile_token` 在受保护路由内同步校验客户端 token；
失败抛 ``HTTPException(400)``，调用方无需自行处理 ``httpx`` 异常。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from pix_web.config import WebSettings

logger = logging.getLogger(__name__)

_VERIFY_TIMEOUT_SECONDS = 8.0
_TURNSTILE_TOKEN_MAX_LENGTH = 2048


def is_turnstile_active(settings: WebSettings) -> bool:
    """开关 + 必填 secret 双重判断；缺一不算激活。"""

    return bool(settings.turnstile_enabled and settings.turnstile_secret_key.strip())


def verify_turnstile_token(
    settings: WebSettings,
    token: str,
    *,
    remote_ip: str | None = None,
) -> None:
    """同步校验 Turnstile token。

    - 开关关闭或 secret 未配置时直接放行（保留默认行为，便于本地开发）。
    - token 缺失或被远端拒绝时抛 ``HTTPException(400)``。
    - Cloudflare 服务暂不可达视为 503。
    """

    if not is_turnstile_active(settings):
        return

    cleaned = (token or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先完成人机校验",
        )
    if len(cleaned) > _TURNSTILE_TOKEN_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人机校验数据无效",
        )

    payload: dict[str, str] = {
        "secret": settings.turnstile_secret_key,
        "response": cleaned,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        with httpx.Client(timeout=_VERIFY_TIMEOUT_SECONDS) as client:
            response = client.post(settings.turnstile_verify_url, data=payload)
    except httpx.HTTPError as exc:  # 网络抖动/超时
        logger.warning("Turnstile verify request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="人机校验服务暂不可用，请稍后再试",
        ) from exc

    if response.status_code >= 500:
        logger.warning("Turnstile verify upstream %s: %s", response.status_code, response.text[:200])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="人机校验服务暂不可用，请稍后再试",
        )

    try:
        body: Any = response.json()
    except ValueError as exc:
        logger.warning("Turnstile verify returned non-JSON: %s", response.text[:200])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="人机校验响应解析失败",
        ) from exc

    if not isinstance(body, dict) or not body.get("success"):
        codes = []
        if isinstance(body, dict):
            raw_codes = body.get("error-codes")
            if isinstance(raw_codes, list):
                codes = [str(item) for item in raw_codes]
        logger.info("Turnstile verify rejected: %s", codes)
        # 用户可重新触发；返回 400 以便前端 reset widget 后重试
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人机校验未通过，请重试",
        )
