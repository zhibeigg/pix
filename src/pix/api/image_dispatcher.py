"""生图请求分发与多 Provider 失败切换。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pix.api.http_client import ProviderError
from pix.api.image_model_registry import IMAGE_TO_IMAGE, TEXT_TO_IMAGE, available_model_infos, candidates_for_model
from pix.api.image_providers import ImageProviderRequest, ImageProviderResult, provider_for_candidate
from pix.config import AppConfig

_HISTORY = threading.local()


@dataclass(frozen=True)
class DispatchResult:
    image: ImageProviderResult
    attempts: list[dict[str, Any]]

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.image.provider_id,
            "provider_model": self.image.provider_model,
            "protocol": self.image.protocol,
            "attempts": self.attempts,
        }


def clear_image_provider_history() -> None:
    _HISTORY.events = []


def image_provider_history() -> list[dict[str, Any]]:
    return list(getattr(_HISTORY, "events", []) or [])


def _record_event(event: dict[str, Any]) -> None:
    events = list(getattr(_HISTORY, "events", []) or [])
    events.append(event)
    _HISTORY.events = events


def dispatch_image_request(
    cfg: AppConfig,
    *,
    operation: str,
    prompt: str,
    model: str | None,
    size: str,
    quality: str | None,
    output_format: str | None,
    input_fidelity: str | None = None,
    image_path: Path | None = None,
) -> DispatchResult:
    requested_model = model or cfg.image_gen.model
    logical_model = requested_model
    candidates = candidates_for_model(cfg, logical_model, operation)
    if not candidates and not model:
        fallback_model = _default_fallback_model(cfg, requested_model, operation)
        if fallback_model:
            logical_model = fallback_model
            candidates = candidates_for_model(cfg, logical_model, operation)
    if not candidates:
        built = f"模型 {requested_model} 不支持 {operation} 或未配置可用 Provider"
        raise ProviderError(built, category="unsupported_model", provider_id="", retryable=False)

    attempts: list[dict[str, Any]] = []
    failover_categories = set(cfg.image_gen.failover_on or [])
    last_error: ProviderError | None = None
    request = ImageProviderRequest(
        operation=operation,
        prompt=prompt,
        model=logical_model,
        size=size,
        quality=quality,
        output_format=output_format,
        input_fidelity=input_fidelity,
        image_path=image_path,
    )
    for index, candidate in enumerate(candidates):
        try:
            provider = provider_for_candidate(cfg, candidate)
            if operation == IMAGE_TO_IMAGE:
                image = provider.edit(request)
            elif operation == TEXT_TO_IMAGE:
                image = provider.generate(request)
            else:
                raise ProviderError(
                    f"不支持的生图操作：{operation}",
                    category="unsupported_operation",
                    provider_id=candidate.provider.id,
                    retryable=False,
                )
            attempts.append(image.attempt())
            result = DispatchResult(image=image, attempts=attempts)
            _record_event({
                "model": logical_model,
                "operation": operation,
                **result.metadata(),
            })
            return result
        except ProviderError as exc:
            last_error = exc
            attempt = exc.to_attempt(provider=candidate.provider.id, model=candidate.model.provider_model or candidate.model.id)
            attempt["protocol"] = candidate.model.protocol
            attempts.append(attempt)
            should_failover = (
                bool(cfg.image_gen.failover_enabled)
                and index < len(candidates) - 1
                and (exc.retryable or exc.category in failover_categories)
                and exc.category in failover_categories
            )
            if not should_failover:
                _record_event({
                    "model": logical_model,
                    "operation": operation,
                    "provider": candidate.provider.id,
                    "provider_model": candidate.model.provider_model or candidate.model.id,
                    "protocol": candidate.model.protocol,
                    "attempts": attempts,
                    "status": "failed",
                })
                raise
    message = _combined_failure_message(logical_model, attempts)
    if last_error is not None:
        raise ProviderError(
            message,
            category=last_error.category,
            status_code=last_error.status_code,
            body=last_error.body,
            provider_id=last_error.provider_id,
            retryable=False,
        ) from last_error
    raise ProviderError(message, category="provider_unavailable", retryable=False)


def _default_fallback_model(cfg: AppConfig, requested_model: str, operation: str) -> str | None:
    """配置默认模型不可用时，回退到当前 Provider 列表里第一个可执行同类操作的图片模型。"""
    for info in available_model_infos(cfg):
        if info.id == requested_model:
            continue
        if operation in (info.operations or (TEXT_TO_IMAGE,)):
            return info.id
    return None


def _combined_failure_message(model: str, attempts: list[dict[str, Any]]) -> str:
    parts = []
    for attempt in attempts:
        provider = attempt.get("provider") or "unknown"
        category = attempt.get("category") or "error"
        message = str(attempt.get("message") or "")[:180]
        parts.append(f"{provider}:{category}{' - ' + message if message else ''}")
    return f"模型 {model} 的所有 Provider 均调用失败：" + "；".join(parts)
