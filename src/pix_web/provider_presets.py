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


def _image_model(
    model_id: str,
    provider_model: str,
    protocol: str,
    *,
    label: str,
    edit_mode: str = "multipart",
    sizes: tuple[str, ...] | None = None,
    qualities: tuple[str, ...] | None = None,
    output_formats: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return {
        "id": model_id,
        "provider_model": provider_model,
        "label": label,
        "protocol": protocol,
        "operations": ["text_to_image", "image_to_image"],
        "sizes": list(tuple(_GPT_IMAGE_SIZES) if sizes is None else sizes),
        "qualities": list(tuple(_QUALITIES) if qualities is None else qualities),
        "output_formats": list(tuple(_FORMATS) if output_formats is None else output_formats),
        "edit_mode": edit_mode,
    }


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="packy", display_name="Packy", protocols=("openai_images",),
        base_url="https://www.packyapi.com", api_key_env="PACKY_API_KEY",
        models=(
            _image_model("image2", "gpt-image-2", "openai_images", label="image2"),
            _image_model(
                "gemini-3.1-flash-image-preview",
                "gemini-3.1-flash-image-preview",
                "openai_images",
                label="Gemini 3.1 Flash Image Preview",
                edit_mode="image_input",
                sizes=("auto", "1024x1024", "1536x1024", "1024x1536"),
                qualities=(),
                output_formats=("png",),
            ),
            _image_model(
                "gemini-3-pro-image-preview",
                "gemini-3-pro-image-preview",
                "openai_images",
                label="Gemini 3 Pro Image Preview",
                edit_mode="image_input",
                sizes=("auto", "1024x1024", "1536x1024", "1024x1536"),
                qualities=(),
                output_formats=("png",),
            ),
        ),
        note="OpenAI 兼容同步生图；模型选择收敛为 image2 与 Gemini Image。",
    ),
    ProviderPreset(
        key="shengsuanyun", display_name="ShengSuanYun（胜算云）", protocols=("shengsuanyun",),
        base_url="https://router.shengsuanyun.com", api_key_env="SHENGSUANYUN_API_KEY",
        models=(_image_model("image2", "openai/gpt-image-2", "shengsuanyun", label="image2", edit_mode="image_input"),),
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
        models=(),
        note="OpenAI 官方 Images API。默认不预置生图模型；如需使用请手动填写允许列表中的模型。",
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
