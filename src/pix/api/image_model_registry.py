"""生图模型注册表：合并内置协议映射、配置和上游发现结果。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
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


def provider_api_key(provider: ImageProviderConfig) -> str:
    if provider.api_key:
        return provider.api_key
    if provider.api_key_env:
        return os.getenv(provider.api_key_env, "")
    return ""


def built_in_model(model_id: str) -> ImageProviderModelConfig | None:
    """按模型名推断协议和基础能力。未知模型返回 None，避免前端暴露必失败选项。"""
    mid = (model_id or "").strip()
    if not mid:
        return None
    lower = mid.lower()
    label = _label_from_model_id(mid)
    base_sizes = ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x1024", "1024x2048"]
    base_qualities = ["auto", "low", "medium", "high"]
    base_formats = ["png", "jpeg", "webp"]

    if lower in {"gpt-image-2", "gpt-image-1"} or "gpt-image" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="openai_images",
            operations=[TEXT_TO_IMAGE, IMAGE_TO_IMAGE],
            sizes=base_sizes,
            qualities=base_qualities,
            output_formats=base_formats,
            extra={"supports_input_fidelity": "gpt-image-1" in lower},
        )
    if "dall-e" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="openai_images",
            operations=[TEXT_TO_IMAGE],
            sizes=["1024x1024", "1792x1024", "1024x1792"],
            qualities=["standard", "hd"] if "3" in lower else [],
            output_formats=["png"],
        )
    if "qwen" in lower and "image" in lower:
        ops = [TEXT_TO_IMAGE, IMAGE_TO_IMAGE] if "edit" in lower else [TEXT_TO_IMAGE]
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="openai_images",
            operations=ops,
            sizes=base_sizes,
            qualities=[],
            output_formats=base_formats,
            edit_mode="image_input" if "edit" in lower else "multipart",
        )
    if "seedream" in lower or ("doubao" in lower and any(token in lower for token in ("image", "vision"))):
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="openai_images",
            operations=[TEXT_TO_IMAGE, IMAGE_TO_IMAGE],
            sizes=base_sizes,
            qualities=[],
            output_formats=base_formats,
            edit_mode="image_input",
        )
    if "grok" in lower and "image" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="openai_images",
            operations=[TEXT_TO_IMAGE],
            sizes=base_sizes,
            qualities=[],
            output_formats=["png"],
        )
    if "nano-banana" in lower or ("gemini" in lower and "image" in lower):
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="openai_images",
            operations=[TEXT_TO_IMAGE, IMAGE_TO_IMAGE],
            sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
            qualities=[],
            output_formats=["png"],
            edit_mode="image_input",
        )
    if "midjourney" in lower or lower.startswith("mj-"):
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="midjourney",
            operations=[TEXT_TO_IMAGE],
            sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
            output_formats=["png"],
        )
    if "ideogram" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="ideogram",
            operations=[TEXT_TO_IMAGE],
            sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
            output_formats=["png"],
        )
    if lower.startswith("fal") or "fal-ai" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="fal",
            operations=[TEXT_TO_IMAGE, IMAGE_TO_IMAGE],
            sizes=["auto", "1024x1024"],
            output_formats=["png"],
            edit_mode="image_input",
        )
    if "kling" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="kling",
            operations=[TEXT_TO_IMAGE],
            sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
            output_formats=["png"],
        )
    if "imagen" in lower:
        return ImageProviderModelConfig(
            id=mid,
            provider_model=mid,
            label=label,
            protocol="gemini_native",
            operations=[TEXT_TO_IMAGE],
            sizes=["auto", "1024x1024"],
            output_formats=["png"],
        )
    return None


def default_builtin_models() -> list[ImageProviderModelConfig]:
    ids = [
        "gpt-image-2",
        "gpt-image-1",
        "dall-e-3",
        "qwen-image",
        "qwen-image-edit",
        "doubao-seedream-4-0-250828",
        "doubao-seedream-3-0-t2i-250415",
        "grok-2-image",
        "nano-banana",
        "nano-banana-2",
        "nano-banana-pro",
        "midjourney",
        "ideogram-v3",
        "kling-image-v1",
        "gemini-3.1-flash-image-preview",
    ]
    return [model for mid in ids if (model := built_in_model(mid)) is not None]


def provider_models(cfg: AppConfig, provider: ImageProviderConfig, *, include_discovered: bool = True) -> list[ImageProviderModelConfig]:
    models = [model for model in provider.models if model.id]
    if provider.id == "crazyrouter":
        configured_ids = {model.id for model in models}
        models.extend(model for model in default_builtin_models() if model.id not in configured_ids)
    if include_discovered and provider.discover_models and cfg.image_gen.model_discovery_enabled:
        configured_ids = {model.id for model in models}
        for model in discover_provider_models(cfg, provider):
            if model.id not in configured_ids:
                models.append(model)
                configured_ids.add(model.id)
    return models


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
    infos.sort(key=lambda item: (0 if item.id == cfg.image_gen.model else 1, item.label.lower(), item.id))
    return infos


def candidates_for_model(cfg: AppConfig, model_id: str, operation: str) -> list[ProviderCandidate]:
    result: list[ProviderCandidate] = []
    requested = model_id or cfg.image_gen.model
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
