"""Packy API HTTP 基础客户端：统一 header、超时、重试。"""

from __future__ import annotations

import json as _json
import time
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from pix.config import AppConfig


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
        *,
        trust_env: bool = False,
        proxy: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.trust_env = trust_env
        self.proxy = (proxy or "").strip() or None

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
        # 拆分超时：连接握手与写入用统一值；read=None 允许生图这类长任务等待完整 JSON 响应。
        # Packy gpt-image-2 Images API 不支持 stream/partial_images，这里使用普通 POST，不启用流式响应。
        timeout_config = httpx.Timeout(
            connect=min(60.0, self.timeout),
            read=None,
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
                    resp = client.post(
                        url,
                        headers=self._headers(content_type=content_type),
                        json=json,
                        data=data,
                        files=files,
                    )
                    body_text = resp.text
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
                # RemoteProtocolError 多半是远端网关把长 idle 连接 close，等久一点再试
                if isinstance(exc, httpx.RemoteProtocolError):
                    backoff = max(backoff, 15)
                time.sleep(backoff)
        assert last_exc is not None
        raise last_exc


def make_packy_client(cfg: "AppConfig", api_key: str) -> PackyClient:
    """统一构造 PackyClient，并把代理/超时配置一次性注入。"""
    api = cfg.api
    return PackyClient(
        base_url=api.base_url,
        api_key=api_key,
        timeout=api.timeout,
        max_retries=api.max_retries,
        trust_env=api.trust_env_proxies,
        proxy=api.proxy,
    )
