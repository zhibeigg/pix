"""Packy API HTTP 基础客户端：统一 header、超时、重试。"""

from __future__ import annotations

import time
from typing import Any

import httpx


class PackyError(RuntimeError):
    """Packy API 调用异常。"""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PackyClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 180.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self, *, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "*/*",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post(path, json=payload)

    def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        return self._post(path, data=data, files=files, content_type=None)

    def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        content_type: str | None = "application/json",
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(
                        url,
                        headers=self._headers(content_type=content_type),
                        json=json,
                        data=data,
                        files=files,
                    )
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise PackyError(
                        f"HTTP {resp.status_code} 服务器端错误",
                        status_code=resp.status_code,
                        body=resp.text[:2000],
                    )
                if resp.status_code >= 400:
                    raise PackyError(
                        f"HTTP {resp.status_code} 客户端错误：{resp.text[:500]}",
                        status_code=resp.status_code,
                        body=resp.text[:2000],
                    )
                try:
                    return resp.json()
                except ValueError as exc:
                    raise PackyError(
                        f"响应不是合法 JSON：{resp.text[:500]}",
                        status_code=resp.status_code,
                        body=resp.text[:2000],
                    ) from exc
            except (httpx.HTTPError, PackyError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                # 仅对 5xx / 429 / 网络错误重试；4xx 其他不重试
                if isinstance(exc, PackyError) and exc.status_code and exc.status_code < 500 and exc.status_code != 429:
                    break
                backoff = min(2 ** (attempt - 1), 8)
                time.sleep(backoff)
        assert last_exc is not None
        raise last_exc
