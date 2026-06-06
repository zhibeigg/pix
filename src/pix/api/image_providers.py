"""生图 Provider 协议适配器。"""

from __future__ import annotations

import asyncio
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pix.api.http_client import ProviderError, ProviderHttpClient
from pix.api.image_model_registry import IMAGE_TO_IMAGE, TEXT_TO_IMAGE, ProviderCandidate, provider_api_key
from pix.config import AppConfig, ImageProviderConfig, ImageProviderModelConfig
from pix.io_utils import image_to_base64_data_url


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
            payload["image_input"] = image_to_base64_data_url(request.image_path)
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
        provider_model = (self.model.provider_model or self.model.id).lower()
        if request.input_fidelity and request.operation == IMAGE_TO_IMAGE and "gpt-image" in provider_model:
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
            payload["image_url"] = image_to_base64_data_url(request.image_path)
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


_PROVIDER_BY_PROTOCOL = {
    "openai_images": OpenAIImagesProvider,
    "midjourney": MidjourneyProvider,
    "ideogram": IdeogramProvider,
    "fal": FalProvider,
    "kling": KlingProvider,
    "gemini_native": GeminiNativeProvider,
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
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
