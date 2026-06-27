"""通用上游 Provider HTTP 客户端。"""

from __future__ import annotations

import json as _json
from typing import Any

import httpx


class ProviderError(RuntimeError):
    """上游 Provider 调用异常，带可用于失败切换的分类。"""

    def __init__(
        self,
        message: str,
        *,
        category: str = "provider_error",
        status_code: int | None = None,
        body: str | None = None,
        provider_id: str = "",
        retryable: bool | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.body = body
        self.provider_id = provider_id
        self.retryable = _default_retryable(category, status_code) if retryable is None else retryable

    def to_attempt(self, *, provider: str | None = None, model: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "provider": provider or self.provider_id,
            "status": "failed",
            "category": self.category,
            "message": str(self),
            "retryable": self.retryable,
        }
        if model:
            data["provider_model"] = model
        if self.status_code is not None:
            data["status_code"] = self.status_code
        return data


def _default_retryable(category: str, status_code: int | None) -> bool:
    if category in {"network", "timeout", "rate_limit", "server_error", "empty_response", "malformed_response", "provider_unavailable"}:
        return True
    if status_code is not None and (status_code == 429 or status_code >= 500):
        return True
    return False


def category_for_status(status_code: int, body: str = "") -> str:
    lower = body.lower()
    if status_code == 429:
        return "rate_limit"
    if status_code in {401, 403}:
        return "auth"
    if status_code == 402 or "insufficient" in lower or "quota" in lower or "balance" in lower:
        return "quota"
    if status_code == 408:
        return "timeout"
    if status_code >= 500:
        return "server_error"
    if "content policy" in lower or "safety" in lower or "policy" in lower:
        return "content_policy"
    return "client_error"


class ProviderHttpClient:
    """统一 header、超时、代理和重试的同步 HTTP 客户端。

    这里不做阻塞 sleep 退避；调用方可在异步任务协议的轮询中使用 asyncio.sleep。
    """

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        api_key: str,
        timeout: float = 600.0,
        max_retries: int = 3,
        trust_env: bool = False,
        proxy: str | None = None,
        error_type: type[ProviderError] = ProviderError,
        extra_headers: dict[str, str] | None = None,
    ):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries or 1))
        self.trust_env = trust_env
        self.proxy = (proxy or "").strip() or None
        self.error_type = error_type
        self.extra_headers = dict(extra_headers or {})

    def headers(self, *, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "*/*",
            **self.extra_headers,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def get_json(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=payload)

    def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        return self._request("POST", path, data=data, files=files, content_type=None)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        content_type: str | None = "application/json",
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        last_exc: Exception | None = None
        timeout_config = httpx.Timeout(
            connect=min(60.0, self.timeout),
            # 有限读超时：避免上游连上后挂起/慢速吐数据时无限阻塞，长期占住 worker 槽位
            # 与 DB 连接。以 self.timeout（默认 600s）为单次读上限，足够大图响应。
            read=self.timeout,
            write=min(120.0, self.timeout),
            pool=self.timeout,
        )
        for attempt in range(1, self.max_retries + 1):
            try:
                client_kwargs: dict[str, Any] = {
                    "timeout": timeout_config,
                    "trust_env": self.trust_env,
                    "follow_redirects": True,
                }
                if self.proxy:
                    client_kwargs["proxy"] = self.proxy
                with httpx.Client(**client_kwargs) as client:
                    resp = client.request(
                        method,
                        url,
                        headers=self.headers(content_type=content_type),
                        json=json,
                        data=data,
                        files=files,
                    )
                    body_text = resp.text
                    status_code = resp.status_code
                if status_code >= 400:
                    category = category_for_status(status_code, body_text)
                    raise self.error_type(
                        f"HTTP {status_code} 上游错误：{body_text[:500]}",
                        category=category,
                        status_code=status_code,
                        body=body_text[:2000],
                        provider_id=self.provider_id,
                    )
                if not body_text.strip():
                    raise self.error_type(
                        "上游响应为空",
                        category="empty_response",
                        status_code=status_code,
                        provider_id=self.provider_id,
                    )
                try:
                    parsed = _json.loads(body_text)
                except ValueError as exc:
                    raise self.error_type(
                        f"响应不是合法 JSON：{body_text[:500]}",
                        category="malformed_response",
                        status_code=status_code,
                        body=body_text[:2000],
                        provider_id=self.provider_id,
                    ) from exc
                if not isinstance(parsed, dict):
                    raise self.error_type(
                        f"响应 JSON 顶层必须是对象：{str(parsed)[:500]}",
                        category="malformed_response",
                        status_code=status_code,
                        provider_id=self.provider_id,
                    )
                return parsed
            except httpx.TimeoutException as exc:
                last_exc = self.error_type(str(exc), category="timeout", provider_id=self.provider_id)
            except httpx.HTTPError as exc:
                last_exc = self.error_type(str(exc), category="network", provider_id=self.provider_id)
            except ProviderError as exc:
                last_exc = exc
                if not exc.retryable:
                    break
            if attempt >= self.max_retries:
                break
        assert last_exc is not None
        raise last_exc
