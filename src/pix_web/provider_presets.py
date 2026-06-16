"""后台「新增供应商」可选的预设目录。取值与 config.py 的 env 注入默认保持一致。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_GPT_IMAGE_SIZES = ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x1024", "1024x2048"]
_QUALITIES = ["auto", "low", "medium", "high"]
_FORMATS = ["png", "jpeg", "webp"]


@dataclass(frozen=True)
class ProviderPreset:
    key: str
    display_name: str
    protocols: tuple[str, ...]
    base_url: str
    api_key_env: str
    discover_models: bool = False
    models: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    note: str = ""


def _gpt_image_model(model_id: str, provider_model: str, protocol: str, *, edit_mode: str = "multipart") -> dict[str, Any]:
    return {
        "id": model_id,
        "provider_model": provider_model,
        "label": "GPT Image 2",
        "protocol": protocol,
        "operations": ["text_to_image", "image_to_image"],
        "sizes": list(_GPT_IMAGE_SIZES),
        "qualities": list(_QUALITIES),
        "output_formats": list(_FORMATS),
        "edit_mode": edit_mode,
    }


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="packy", display_name="Packy", protocols=("openai_images",),
        base_url="https://www.packyapi.com", api_key_env="PACKY_API_KEY",
        models=(_gpt_image_model("gpt-image-2", "gpt-image-2", "openai_images"),),
        note="OpenAI 兼容同步生图。",
    ),
    ProviderPreset(
        key="shengsuanyun", display_name="ShengSuanYun（胜算云）", protocols=("shengsuanyun",),
        base_url="https://router.shengsuanyun.com", api_key_env="SHENGSUANYUN_API_KEY",
        models=(_gpt_image_model("gpt-image-2", "openai/gpt-image-2", "shengsuanyun", edit_mode="image_input"),),
        note="OpenAI 风格请求体 + 异步任务轮询。",
    ),
    ProviderPreset(
        key="crazyrouter", display_name="Crazyrouter",
        protocols=("openai_images", "midjourney", "ideogram", "fal", "kling", "gemini_native"),
        base_url="https://crazyrouter.com", api_key_env="CRAZYROUTER_API_KEY",
        discover_models=True, models=(),
        note="多协议聚合，支持模型自动发现（需开启全局模型发现）。",
    ),
    ProviderPreset(
        key="openai", display_name="OpenAI", protocols=("openai_images",),
        base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY",
        models=(_gpt_image_model("gpt-image-1", "gpt-image-1", "openai_images"),),
        note="OpenAI 官方 Images API。",
    ),
    ProviderPreset(
        key="midjourney", display_name="Midjourney", protocols=("midjourney",),
        base_url="", api_key_env="", models=(), note="异步轮询协议，填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="ideogram", display_name="Ideogram", protocols=("ideogram",),
        base_url="", api_key_env="", models=(), note="填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="fal", display_name="Fal", protocols=("fal",),
        base_url="", api_key_env="", models=(), note="填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="kling", display_name="Kling", protocols=("kling",),
        base_url="", api_key_env="", models=(), note="异步轮询协议，填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="custom", display_name="自定义（OpenAI 兼容）", protocols=("openai_images",),
        base_url="", api_key_env="", models=(), note="接任意 OpenAI 兼容上游，base_url 与模型自行填写。",
    ),
)


def preset_to_dict(preset: ProviderPreset) -> dict[str, Any]:
    return {
        "key": preset.key,
        "display_name": preset.display_name,
        "protocols": list(preset.protocols),
        "base_url": preset.base_url,
        "api_key_env": preset.api_key_env,
        "discover_models": preset.discover_models,
        "models": [dict(m) for m in preset.models],
        "note": preset.note,
    }
