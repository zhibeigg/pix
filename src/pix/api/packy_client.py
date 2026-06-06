"""Packy 兼容客户端：保留旧导入路径，内部复用通用 Provider HTTP 客户端。"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from pix.api.http_client import ProviderError, ProviderHttpClient

if TYPE_CHECKING:
    from pix.config import AppConfig


class PackyError(ProviderError):
    """Packy API 调用异常。"""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None, **kwargs: Any):
        provider_id = str(kwargs.pop("provider_id", "packy") or "packy")
        super().__init__(message, status_code=status_code, body=body, provider_id=provider_id, **kwargs)


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
        self._client = ProviderHttpClient(
            provider_id="packy",
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            trust_env=trust_env,
            proxy=proxy,
            error_type=PackyError,
        )
        self.base_url = self._client.base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.trust_env = trust_env
        self.proxy = (proxy or "").strip() or None

    def _headers(self, *, content_type: str | None = "application/json") -> dict[str, str]:
        return self._client.headers(content_type=content_type)

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.post_json(path, payload)

    def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        return self._client.post_multipart(path, data=data, files=files)


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
