"""生图 Provider 协议适配器。"""

from __future__ import annotations

import asyncio
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from pix.api.http_client import ProviderError, ProviderHttpClient
from pix.api.image_model_registry import IMAGE_TO_IMAGE, ProviderCandidate, provider_api_key
from pix.config import AppConfig, ImageProviderModelConfig
from pix.io_utils import image_to_base64_data_url


PublicImageUrlResolver = Callable[[Path], str]
_PUBLIC_IMAGE_URL_RESOLVER_ATTR = "_pix_public_image_url_resolver"


def set_public_image_url_resolver(cfg: AppConfig, resolver: PublicImageUrlResolver) -> None:
    """注入 Web 运行时的受保护文件 URL 解析器；核心配置序列化不会持久化该闭包。"""
    setattr(cfg, _PUBLIC_IMAGE_URL_RESOLVER_ATTR, resolver)


@dataclass(frozen=True)
class ImageProviderRequest:
    operation: str
    prompt: str
    model: str
    size: str
    quality: str | None = None
    output_format: str | None = None
    input_fidelity: str | None = None
    image_path: Path | None = None


@dataclass(frozen=True)
class ImageProviderResult:
    url: str | None = None
    b64_json: str | None = None
    provider_id: str = ""
    provider_model: str = ""
    protocol: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def attempt(self) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "provider_model": self.provider_model,
            "protocol": self.protocol,
            "status": "success",
        }


class BaseImageProvider:
    def __init__(self, cfg: AppConfig, candidate: ProviderCandidate):
        self.cfg = cfg
        self.provider = candidate.provider
        self.model = candidate.model
        api_key = provider_api_key(self.provider)
        if not api_key:
            raise ProviderError(
                f"Provider {self.provider.id} 未配置 API key（{self.provider.api_key_env or 'api_key'}）",
                category="auth",
                provider_id=self.provider.id,
                retryable=True,
            )
        self.client = ProviderHttpClient(
            provider_id=self.provider.id,
            base_url=self.provider.base_url,
            api_key=api_key,
            timeout=self.cfg.api.timeout,
            max_retries=self.cfg.api.max_retries,
            trust_env=self.cfg.api.trust_env_proxies,
            proxy=self.cfg.api.proxy,
            extra_headers=self.provider.extra_headers,
        )

    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        raise NotImplementedError

    def edit(self, request: ImageProviderRequest) -> ImageProviderResult:
        raise ProviderError(
            f"模型 {self.model.id} 不支持图生图",
            category="unsupported_operation",
            provider_id=self.provider.id,
            retryable=False,
        )

    def _reference_value(self, image_path: Path) -> str:
        path = Path(image_path)
        if not self.model.requires_public_image_url:
            return image_to_base64_data_url(path)
        resolver = getattr(self.cfg, _PUBLIC_IMAGE_URL_RESOLVER_ATTR, None)
        if not callable(resolver):
            raise ProviderError(
                f"Provider {self.provider.id} 的模型 {self.model.id} 要求公网参考图 URL，但当前运行环境未提供安全 URL 解析器",
                category="provider_unavailable",
                provider_id=self.provider.id,
                retryable=True,
            )
        try:
            value = str(resolver(path)).strip()
        except Exception as exc:
            raise ProviderError(
                f"Provider {self.provider.id} 的安全参考图 URL 生成失败",
                category="provider_unavailable",
                provider_id=self.provider.id,
                retryable=True,
            ) from exc
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProviderError(
                f"Provider {self.provider.id} 的安全参考图 URL 无效",
                category="provider_unavailable",
                provider_id=self.provider.id,
                retryable=True,
            )
        return value

    def _result_from_response(self, resp: dict[str, Any]) -> ImageProviderResult:
        url, b64 = pick_image_entry(resp)
        if not url and not b64:
            raise ProviderError(
                f"图片响应缺少 url 和 b64_json：{str(resp)[:500]}",
                category="empty_response",
                provider_id=self.provider.id,
            )
        return ImageProviderResult(
            url=url,
            b64_json=b64,
            provider_id=self.provider.id,
            provider_model=self.model.provider_model or self.model.id,
            protocol=self.model.protocol,
            raw=resp,
        )


class OpenAIImagesProvider(BaseImageProvider):
    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        payload = self._base_payload(request)
        if request.operation == IMAGE_TO_IMAGE and self.model.edit_mode == "image_input":
            if request.image_path is None:
                raise ProviderError("图生图缺少参考图", category="invalid_request", provider_id=self.provider.id, retryable=False)
            payload["image_input"] = self._reference_value(request.image_path)
        resp = self.client.post_json(self.model.endpoint or "/v1/images/generations", payload)
        return self._result_from_response(resp)

    def edit(self, request: ImageProviderRequest) -> ImageProviderResult:
        if request.image_path is None:
            raise ProviderError("图生图缺少参考图", category="invalid_request", provider_id=self.provider.id, retryable=False)
        if self.model.edit_mode == "image_input":
            return self.generate(request)
        if self.model.edit_mode == "none":
            return super().edit(request)
        data = self._base_payload(request)
        # multipart 表单中 n 按 OpenAI Images 兼容惯例传字符串更稳妥。
        data["n"] = str(data.get("n", 1))
        image_path = Path(request.image_path)
        mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
        files = {"image": (image_path.name, image_path.read_bytes(), mime)}
        resp = self.client.post_multipart(self.model.edit_endpoint or "/v1/images/edits", data=data, files=files)
        return self._result_from_response(resp)

    def _base_payload(self, request: ImageProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model.provider_model or request.model,
            "prompt": request.prompt,
            "n": 1,
        }
        if request.size and request.size != "auto":
            payload["size"] = request.size
        elif request.size == "auto" and _supports_value(self.model.sizes, "auto"):
            payload["size"] = "auto"
        if request.quality and _supports_value(self.model.qualities, request.quality):
            payload["quality"] = request.quality
        if request.output_format and _supports_value(self.model.output_formats, request.output_format):
            payload["output_format"] = request.output_format
        if request.input_fidelity and request.operation == IMAGE_TO_IMAGE and _supports_input_fidelity(self.model):
            payload["input_fidelity"] = request.input_fidelity
        # 尽量让兼容 API 直接返回 base64，若模型忽略该参数也会走 URL 兜底。
        payload["response_format"] = "b64_json"
        return payload


class MidjourneyProvider(BaseImageProvider):
    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        prompt = request.prompt
        if request.size and request.size != "auto":
            prompt = f"{prompt} --ar {_aspect_ratio(request.size)}"
        resp = self.client.post_json(self.model.endpoint or "/mj/submit/imagine", {"prompt": prompt})
        task_id = str(resp.get("result") or resp.get("task_id") or resp.get("id") or "")
        if not task_id:
            raise ProviderError(f"Midjourney 提交响应缺少 task id：{str(resp)[:500]}", category="malformed_response", provider_id=self.provider.id)
        final = _run_async_poll(self._poll_task(task_id))
        return self._result_from_response(final)

    async def _poll_task(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + float(self.cfg.api.timeout or 600.0)
        interval = max(0.5, float(self.cfg.image_gen.provider_poll_interval_seconds or 2.0))
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.client.get_json(f"/mj/task/{task_id}/fetch")
            status = str(last.get("status") or last.get("state") or "").upper()
            if status in {"SUCCESS", "FINISHED", "DONE"}:
                return last
            if status in {"FAILURE", "FAILED", "ERROR", "CANCELLED"}:
                raise ProviderError(f"Midjourney 任务失败：{str(last)[:500]}", category="provider_unavailable", provider_id=self.provider.id)
            await asyncio.sleep(interval)
        raise ProviderError(f"Midjourney 任务超时：{str(last)[:500]}", category="timeout", provider_id=self.provider.id)


class IdeogramProvider(BaseImageProvider):
    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        endpoint = self.model.endpoint or _ideogram_endpoint(self.model.provider_model or self.model.id)
        payload: dict[str, Any] = {"prompt": request.prompt}
        if request.size and request.size != "auto":
            payload["aspect_ratio"] = _aspect_ratio(request.size)
        resp = self.client.post_json(endpoint, payload)
        return self._result_from_response(resp)


class FalProvider(BaseImageProvider):
    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        endpoint = self.model.endpoint or f"/{self.model.provider_model or self.model.id}"
        payload: dict[str, Any] = {"prompt": request.prompt}
        if request.operation == IMAGE_TO_IMAGE and request.image_path is not None:
            payload["image_url"] = self._reference_value(request.image_path)
        if request.size and request.size != "auto":
            payload["image_size"] = request.size
        resp = self.client.post_json(endpoint, payload)
        return self._result_from_response(resp)

    def edit(self, request: ImageProviderRequest) -> ImageProviderResult:
        return self.generate(request)


class KlingProvider(BaseImageProvider):
    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        payload: dict[str, Any] = {
            "model_name": self.model.provider_model or self.model.id,
            "prompt": request.prompt,
        }
        if request.size and request.size != "auto":
            payload["aspect_ratio"] = _aspect_ratio(request.size)
        resp = self.client.post_json(self.model.endpoint or "/kling/v1/images/generations", payload)
        task_id = str(resp.get("task_id") or resp.get("id") or (resp.get("data") or {}).get("task_id") or "")
        if not task_id:
            return self._result_from_response(resp)
        final = _run_async_poll(self._poll_task(task_id))
        return self._result_from_response(final)

    async def _poll_task(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + float(self.cfg.api.timeout or 600.0)
        interval = max(0.5, float(self.cfg.image_gen.provider_poll_interval_seconds or 2.0))
        last: dict[str, Any] = {}
        query_endpoint = self.model.edit_endpoint or f"/kling/v1/images/generations/{task_id}"
        while time.monotonic() < deadline:
            last = self.client.get_json(query_endpoint)
            status = str(last.get("status") or (last.get("data") or {}).get("task_status") or "").lower()
            if status in {"succeed", "success", "finished", "done"}:
                return last
            if status in {"failed", "failure", "error", "cancelled"}:
                raise ProviderError(f"Kling 任务失败：{str(last)[:500]}", category="provider_unavailable", provider_id=self.provider.id)
            await asyncio.sleep(interval)
        raise ProviderError(f"Kling 任务超时：{str(last)[:500]}", category="timeout", provider_id=self.provider.id)


class GeminiNativeProvider(OpenAIImagesProvider):
    """预留 Imagen/Gemini 原生协议扩展点；当前按 Images 兼容协议兜底。"""


class ShengSuanYunProvider(BaseImageProvider):
    """胜算云（ShengSuanYun）异步任务协议。

    请求体为 OpenAI gpt-image 兼容风格，但走「提交任务 + 轮询查询」异步流程：
        POST /api/v1/tasks/generations      → 响应 data.request_id / data.task_id
        GET  /api/v1/tasks/generations/{id} → 轮询 data.status 直到 COMPLETED
    成功结果图片位于 data.data.image_urls[]（仅 URL，无 base64）。
    图生图复用同一端点与轮询，仅额外传 image 字段（base64 data URL）。
    """

    def generate(self, request: ImageProviderRequest) -> ImageProviderResult:
        return self._submit_and_poll(self._base_payload(request))

    def edit(self, request: ImageProviderRequest) -> ImageProviderResult:
        if request.image_path is None:
            raise ProviderError(
                "图生图缺少参考图",
                category="invalid_request",
                provider_id=self.provider.id,
                retryable=False,
            )
        payload = self._base_payload(request)
        payload["image"] = self._reference_value(request.image_path)
        return self._submit_and_poll(payload)

    def _base_payload(self, request: ImageProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model.provider_model or request.model,
            "prompt": request.prompt,
            "n": 1,
        }
        if request.size and request.size != "auto":
            payload["size"] = request.size
        elif request.size == "auto" and _supports_value(self.model.sizes, "auto"):
            payload["size"] = "auto"
        if request.quality and _supports_value(self.model.qualities, request.quality):
            payload["quality"] = request.quality
        if request.output_format and _supports_value(self.model.output_formats, request.output_format):
            payload["output_format"] = request.output_format
            if request.output_format in {"jpeg", "webp"}:
                payload["output_compression"] = 100
        # 胜算云 gpt-image 兼容参数；与上游官方示例保持一致的默认值。
        payload["background"] = "auto"
        payload["moderation"] = "auto"
        return payload

    def _submit_and_poll(self, payload: dict[str, Any]) -> ImageProviderResult:
        endpoint = self.model.endpoint or "/api/v1/tasks/generations"
        resp = self.client.post_json(endpoint, payload)
        envelope = resp.get("data") if isinstance(resp.get("data"), dict) else resp
        task_id = str(envelope.get("request_id") or envelope.get("task_id") or "")
        if not task_id:
            raise ProviderError(
                f"胜算云提交响应缺少 request_id/task_id：{str(resp)[:500]}",
                category="malformed_response",
                provider_id=self.provider.id,
            )
        final = _run_async_poll(self._poll_task(endpoint, task_id))
        return self._result_from_task(final)

    async def _poll_task(self, endpoint: str, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + float(self.cfg.api.timeout or 600.0)
        interval = max(0.5, float(self.cfg.image_gen.provider_poll_interval_seconds or 2.0))
        query = f"{endpoint.rstrip('/')}/{task_id}"
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.client.get_json(query)
            envelope = last.get("data") if isinstance(last.get("data"), dict) else last
            status = str(envelope.get("status") or "").upper()
            if status == "COMPLETED":
                return last
            if status in {"FAILED", "CANCELLED"}:
                reason = str(envelope.get("fail_reason") or "").strip()
                raise ProviderError(
                    f"胜算云任务失败（{status}）：{reason or str(last)[:500]}",
                    category="provider_unavailable",
                    provider_id=self.provider.id,
                )
            await asyncio.sleep(interval)
        raise ProviderError(
            f"胜算云任务超时：{str(last)[:500]}",
            category="timeout",
            provider_id=self.provider.id,
        )

    def _result_from_task(self, resp: dict[str, Any]) -> ImageProviderResult:
        envelope = resp.get("data") if isinstance(resp.get("data"), dict) else {}
        inner = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
        image_urls = inner.get("image_urls") if isinstance(inner, dict) else None
        url: str | None = None
        if isinstance(image_urls, list):
            url = next((item for item in image_urls if isinstance(item, str) and item.strip()), None)
        if url:
            return ImageProviderResult(
                url=url,
                provider_id=self.provider.id,
                provider_model=self.model.provider_model or self.model.id,
                protocol=self.model.protocol,
                raw=resp,
            )
        # 兜底：兼容上游未来可能直接返回 data[].url / b64 的形态。
        fallback_url, fallback_b64 = pick_image_entry(resp)
        if not fallback_url and not fallback_b64:
            raise ProviderError(
                f"胜算云结果缺少 image_urls：{str(resp)[:500]}",
                category="empty_response",
                provider_id=self.provider.id,
            )
        return ImageProviderResult(
            url=fallback_url,
            b64_json=fallback_b64,
            provider_id=self.provider.id,
            provider_model=self.model.provider_model or self.model.id,
            protocol=self.model.protocol,
            raw=resp,
        )


_PROVIDER_BY_PROTOCOL = {
    "openai_images": OpenAIImagesProvider,
    "midjourney": MidjourneyProvider,
    "ideogram": IdeogramProvider,
    "fal": FalProvider,
    "kling": KlingProvider,
    "gemini_native": GeminiNativeProvider,
    "shengsuanyun": ShengSuanYunProvider,
}


def provider_for_candidate(cfg: AppConfig, candidate: ProviderCandidate) -> BaseImageProvider:
    provider_cls = _PROVIDER_BY_PROTOCOL.get(candidate.model.protocol)
    if provider_cls is None:
        raise ProviderError(
            f"不支持的生图协议：{candidate.model.protocol}",
            category="unsupported_protocol",
            provider_id=candidate.provider.id,
            retryable=False,
        )
    return provider_cls(cfg, candidate)


def pick_image_entry(resp: dict[str, Any]) -> tuple[str | None, str | None]:
    """从多种上游响应形态中提取第一张图片的 URL 或 b64。"""
    candidates: list[Any] = []
    for key in ("data", "images", "output", "result"):
        value = resp.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, dict):
            candidates.append(value)
        elif isinstance(value, str) and value.startswith(("http://", "https://", "data:image/")):
            candidates.append(value)
    if not candidates and isinstance(resp.get("image"), str):
        candidates.append(resp["image"])
    for item in candidates:
        if isinstance(item, str):
            if item.startswith("data:image/") and ";base64," in item:
                return None, item.split(",", 1)[1]
            return item, None
        if not isinstance(item, dict):
            continue
        url = _first_str(item, "url", "image_url", "output_url")
        b64 = _first_str(item, "b64_json", "base64", "image_base64")
        if not url and isinstance(item.get("image"), str):
            url = str(item["image"])
        if b64 and b64.startswith("data:image/") and ";base64," in b64:
            b64 = b64.split(",", 1)[1]
        if url or b64:
            return url, b64
    return None, None


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _supports_value(values: list[str], value: str) -> bool:
    return bool(values) and value in values


def _extra_flag(model: ImageProviderModelConfig, key: str) -> bool | None:
    value = (model.extra or {}).get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _supports_input_fidelity(model: ImageProviderModelConfig) -> bool:
    configured = _extra_flag(model, "supports_input_fidelity")
    if configured is not None:
        return configured
    provider_model = (model.provider_model or model.id).lower()
    return "gpt-image-1" in provider_model


def _aspect_ratio(size: str) -> str:
    try:
        left, right = size.lower().split("x", 1)
        w, h = max(1, int(left)), max(1, int(right))
    except (TypeError, ValueError):
        return "1:1"
    gcd = _gcd(w, h)
    return f"{w // gcd}:{h // gcd}"


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return max(1, a)


def _ideogram_endpoint(model_id: str) -> str:
    lower = model_id.lower()
    if "v3" in lower or "3" in lower:
        return "/ideogram/v1/ideogram-v3/generate"
    return "/ideogram/v1/generate"


def _run_async_poll(coro: Any) -> dict[str, Any]:
    """在同步上下文中运行异步轮询协程。

    pix 生图跑在同步 worker 线程（无运行中的事件循环），因此创建独立事件循环执行。
    不能用 `try asyncio.run() except RuntimeError` 兜底：ProviderError 继承自
    RuntimeError，轮询任务失败 / 超时抛出的 ProviderError 会被 except 误捕获，进而重用
    已 await 的协程触发 "cannot reuse already awaited coroutine"，吞掉真正的失败原因并
    破坏多 Provider 失败切换。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
