"""生图模型注册表：合并内置协议映射、配置和上游发现结果。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field, replace
from typing import Any

from pix.api.http_client import ProviderError, ProviderHttpClient
from pix.config import AppConfig, ImageProviderConfig, ImageProviderModelConfig

TEXT_TO_IMAGE = "text_to_image"
IMAGE_TO_IMAGE = "image_to_image"


@dataclass(frozen=True)
class ImageModelInfo:
    id: str
    label: str
    providers: tuple[str, ...] = ()
    operations: tuple[str, ...] = (TEXT_TO_IMAGE,)
    sizes: tuple[str, ...] = ()
    qualities: tuple[str, ...] = ()
    output_formats: tuple[str, ...] = ()
    protocols: tuple[str, ...] = ()
    provider_count: int = 0
    default_size: str = "1024x1024"
    default_quality: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "providers": list(self.providers),
            "operations": list(self.operations),
            "sizes": list(self.sizes),
            "qualities": list(self.qualities),
            "output_formats": list(self.output_formats),
            "protocols": list(self.protocols),
            "provider_count": self.provider_count,
            "default_size": self.default_size,
            "default_quality": self.default_quality,
        }


@dataclass(frozen=True)
class ProviderCandidate:
    provider: ImageProviderConfig
    model: ImageProviderModelConfig


@dataclass
class _DiscoveryCacheEntry:
    expires_at: float
    models: list[ImageProviderModelConfig] = field(default_factory=list)


_DISCOVERY_CACHE: dict[str, _DiscoveryCacheEntry] = {}

IMAGE2_MODEL_ID = "image2"
_IMAGE_MODEL_ALLOWLIST = (
    IMAGE2_MODEL_ID,
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
)
_LEGACY_MODEL_ALIASES = {
    "gpt-image-2": IMAGE2_MODEL_ID,
    "openai/gpt-image-2": IMAGE2_MODEL_ID,
}


def provider_api_key(provider: ImageProviderConfig) -> str:
    if provider.api_key:
        return provider.api_key
    if provider.api_key_env:
        return os.getenv(provider.api_key_env, "")
    return ""


def built_in_model(model_id: str) -> ImageProviderModelConfig | None:
    """只暴露产品允许的生图模型；旧 gpt-image-2 归一为 image2。"""
    mid = (model_id or "").strip()
    if not mid:
        return None
    public_id = public_image_model_id(mid)
    if public_id is None:
        return None
    base_sizes = ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x1024", "1024x2048"]
    base_qualities = ["auto", "low", "medium", "high"]
    base_formats = ["png", "jpeg", "webp"]
    if public_id == IMAGE2_MODEL_ID:
        return ImageProviderModelConfig(
            id=IMAGE2_MODEL_ID,
            provider_model="gpt-image-2",
            label="image2",
            protocol="openai_images",
            operations=[TEXT_TO_IMAGE, IMAGE_TO_IMAGE],
            sizes=base_sizes,
            qualities=base_qualities,
            output_formats=base_formats,
            extra={"supports_input_fidelity": False},
        )
    return ImageProviderModelConfig(
        id=public_id,
        provider_model=mid,
        label=_label_from_model_id(public_id),
        protocol="openai_images",
        operations=[TEXT_TO_IMAGE, IMAGE_TO_IMAGE],
        sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
        qualities=[],
        output_formats=["png"],
        edit_mode="image_input",
    )


def public_image_model_id(model_id: str) -> str | None:
    """把旧模型名归一为公开 logical model，并过滤掉不再支持的候选。"""
    mid = (model_id or "").strip()
    if not mid:
        return None
    lower = mid.lower()
    public_id = _LEGACY_MODEL_ALIASES.get(lower, mid)
    if public_id in _IMAGE_MODEL_ALLOWLIST:
        return public_id
    return None


def default_builtin_models() -> list[ImageProviderModelConfig]:
    return [model for mid in _IMAGE_MODEL_ALLOWLIST if (model := built_in_model(mid)) is not None]


def provider_models(
    cfg: AppConfig,
    provider: ImageProviderConfig,
    *,
    include_discovered: bool = True,
) -> list[ImageProviderModelConfig]:
    models: list[ImageProviderModelConfig] = []
    configured_ids: set[str] = set()
    for item in provider.models:
        model = _normalize_provider_model(item)
        if model and model.id not in configured_ids:
            models.append(model)
            configured_ids.add(model.id)
    if provider.id == "crazyrouter":
        for model in default_builtin_models():
            if model.id not in configured_ids:
                models.append(model)
                configured_ids.add(model.id)
    if include_discovered and provider.discover_models and cfg.image_gen.model_discovery_enabled:
        for model in discover_provider_models(cfg, provider):
            normalized = _normalize_provider_model(model)
            if normalized and normalized.id not in configured_ids:
                models.append(normalized)
                configured_ids.add(normalized.id)
    return models


def _normalize_provider_model(model: ImageProviderModelConfig) -> ImageProviderModelConfig | None:
    public_id = public_image_model_id(model.id)
    if public_id is None:
        return None
    provider_model = model.provider_model or model.id
    label = model.label or _label_from_model_id(public_id)
    if public_id == IMAGE2_MODEL_ID:
        label = "image2"
        if provider_model == IMAGE2_MODEL_ID:
            provider_model = "gpt-image-2"
    return replace(model, id=public_id, provider_model=provider_model, label=label)


def discover_provider_models(cfg: AppConfig, provider: ImageProviderConfig) -> list[ImageProviderModelConfig]:
    cache_key = f"{provider.id}:{provider.base_url}"
    now = time.monotonic()
    cached = _DISCOVERY_CACHE.get(cache_key)
    if cached and cached.expires_at > now:
        return list(cached.models)
    models: list[ImageProviderModelConfig] = []
    api_key = provider_api_key(provider)
    if not api_key:
        return []
    client = ProviderHttpClient(
        provider_id=provider.id,
        base_url=provider.base_url,
        api_key=api_key,
        timeout=min(15.0, float(cfg.api.timeout or 15.0)),
        max_retries=1,
        trust_env=cfg.api.trust_env_proxies,
        proxy=cfg.api.proxy,
    )
    for path in ("/api/pricing?lang=en", "/v1/models"):
        try:
            data = client.get_json(path)
        except ProviderError:
            continue
        models = _models_from_discovery_payload(data)
        if models:
            break
    _DISCOVERY_CACHE[cache_key] = _DiscoveryCacheEntry(
        expires_at=now + max(60, int(cfg.image_gen.model_discovery_ttl_seconds or 3600)),
        models=models,
    )
    return list(models)


def _models_from_discovery_payload(data: dict[str, Any]) -> list[ImageProviderModelConfig]:
    raw_items: Any
    if isinstance(data.get("data"), list):
        raw_items = data["data"]
    elif isinstance(data.get("models"), list):
        raw_items = data["models"]
    elif isinstance(data.get("items"), list):
        raw_items = data["items"]
    else:
        raw_items = []
    result: list[ImageProviderModelConfig] = []
    for item in raw_items:
        if isinstance(item, str):
            model_id = item
            meta = {}
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("model") or item.get("name") or "")
            meta = item
        else:
            continue
        if not model_id:
            continue
        model_type = str(meta.get("type") or meta.get("category") or meta.get("endpoint") or "").lower()
        if model_type and not any(part in model_type for part in ("image", "mj", "ideogram", "kling", "fal")):
            continue
        inferred = built_in_model(model_id)
        if inferred is None:
            continue
        result.append(inferred)
    return result


def available_model_infos(cfg: AppConfig) -> list[ImageModelInfo]:
    buckets: dict[str, list[ProviderCandidate]] = {}
    for provider in cfg.image_providers:
        if not provider.enabled:
            continue
        for model in provider_models(cfg, provider):
            if not model.id:
                continue
            buckets.setdefault(model.id, []).append(ProviderCandidate(provider=provider, model=model))
    infos: list[ImageModelInfo] = []
    for model_id, candidates in buckets.items():
        providers = tuple(candidate.provider.id for candidate in sorted(candidates, key=lambda item: item.provider.priority))
        models = [candidate.model for candidate in candidates]
        operations = _union(models, "operations") or [TEXT_TO_IMAGE]
        sizes = _union(models, "sizes") or ["auto", cfg.image_gen.size]
        qualities = _union(models, "qualities") or ["auto"]
        output_formats = _union(models, "output_formats") or [cfg.image_gen.output_format]
        protocols = sorted({model.protocol for model in models if model.protocol})
        label = next((model.label for model in models if model.label and model.label != model.id), _label_from_model_id(model_id))
        infos.append(
            ImageModelInfo(
                id=model_id,
                label=label,
                providers=providers,
                operations=tuple(operations),
                sizes=tuple(sizes),
                qualities=tuple(qualities),
                output_formats=tuple(output_formats),
                protocols=tuple(protocols),
                provider_count=len(providers),
                default_size=cfg.image_gen.size if cfg.image_gen.size in sizes else sizes[0],
                default_quality=cfg.image_gen.quality if cfg.image_gen.quality in qualities else qualities[0],
            )
        )
    preferred_model = public_image_model_id(cfg.image_gen.model) or cfg.image_gen.model
    infos.sort(key=lambda item: (0 if item.id == preferred_model else 1, item.label.lower(), item.id))
    return infos


def candidates_for_model(cfg: AppConfig, model_id: str, operation: str) -> list[ProviderCandidate]:
    result: list[ProviderCandidate] = []
    requested = public_image_model_id(model_id or cfg.image_gen.model)
    for provider in cfg.image_providers:
        if not provider.enabled:
            continue
        for model in provider_models(cfg, provider):
            if model.id != requested:
                continue
            if operation not in (model.operations or []):
                continue
            if model.protocol not in (provider.protocols or [model.protocol]):
                continue
            result.append(ProviderCandidate(provider=provider, model=model))
    result.sort(key=lambda item: int(item.provider.priority or 100))
    return result


def _union(models: list[ImageProviderModelConfig], field_name: str) -> list[str]:
    values: list[str] = []
    for model in models:
        for item in getattr(model, field_name):
            if item not in values:
                values.append(item)
    return values


def _label_from_model_id(model_id: str) -> str:
    return model_id.replace("/", " / ").replace("-", " ").replace("_", " ").title().replace("Gpt", "GPT").replace("Dall", "DALL").replace("Ai", "AI")
