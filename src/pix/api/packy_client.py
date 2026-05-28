"""Packy API HTTP 基础客户端：统一 header、超时、重试。"""

from __future__ import annotations

import json as _json
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
        timeout: float = 600.0,
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
        # 拆分超时：连接握手与写入用统一值，read/pool 给生图等长任务留足时间。
        # 同时设置 ``read=None`` 让 httpx 直接交给底层 socket 流式读取，避免 read 超时一刀切。
        timeout_config = httpx.Timeout(
            connect=min(60.0, self.timeout),
            read=None,
            write=min(120.0, self.timeout),
            pool=self.timeout,
        )
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout_config) as client:
                    with client.stream(
                        "POST",
                        url,
                        headers=self._headers(content_type=content_type),
                        json=json,
                        data=data,
                        files=files,
                    ) as resp:
                        body_bytes = bytearray()
                        for chunk in resp.iter_bytes(64 * 1024):
                            if chunk:
                                body_bytes.extend(chunk)
                        body_text = body_bytes.decode("utf-8", errors="replace")
                        status_code = resp.status_code
                if status_code >= 500 or status_code == 429:
                    raise PackyError(
                        f"HTTP {status_code} 服务器端错误",
                        status_code=status_code,
                        body=body_text[:2000],
                    )
                if status_code >= 400:
                    raise PackyError(
                        f"HTTP {status_code} 客户端错误：{body_text[:500]}",
                        status_code=status_code,
                        body=body_text[:2000],
                    )
                try:
                    return _json.loads(body_text)
                except ValueError as exc:
                    raise PackyError(
                        f"响应不是合法 JSON：{body_text[:500]}",
                        status_code=status_code,
                        body=body_text[:2000],
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
