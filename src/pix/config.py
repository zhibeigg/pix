"""统一的配置加载与合并。

优先级（后者覆盖前者）：
    默认值 < config.toml < .env < 环境变量 < 调用方显式覆盖
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore[misc]
        return False


# ---------- dataclass 定义 ----------


@dataclass
class ApiConfig:
    base_url: str = "https://www.packyapi.com"
    # 连接与读取超时（秒）；生图/序列帧高 quality 时单次响应可能持续数分钟。
    timeout: float = 600.0
    # 远端网关在长 idle 阶段偶尔会 close 连接；多重试几次能显著提升成功率。
    max_retries: int = 5
    # 旧 Packy 兼容生图 key；新部署优先使用 image_providers。
    image_api_key: str | None = None
    # default 分组 key，用于 VL（Claude / Gemini / gpt-4o）
    vl_api_key: str | None = None
    # 旧 Gemini 生图专用 key（用于 gemini-3.1-flash-image-preview 等兼容模型）
    gemini_api_key: str | None = None
    # 是否信任进程级代理 / 系统代理。本地常见的 Clash 等本地代理会在长时间空闲时主动断开
    # 生图连接，造成 RemoteProtocolError；默认禁用，需要走代理时再显式开启。
    trust_env_proxies: bool = False
    # 显式 HTTPS 代理。优先级高于系统代理；为空字符串表示不使用代理。
    proxy: str | None = None


@dataclass
class ImageProviderModelConfig:
    """单个上游 Provider 下的模型能力描述。"""

    id: str = ""
    provider_model: str = ""
    label: str = ""
    protocol: str = "openai_images"
    operations: list[str] = field(default_factory=lambda: ["text_to_image", "image_to_image"])
    sizes: list[str] = field(default_factory=list)
    qualities: list[str] = field(default_factory=list)
    output_formats: list[str] = field(default_factory=list)
    endpoint: str = ""
    edit_endpoint: str = ""
    edit_mode: str = "multipart"  # multipart | image_input | none
    supports_n: bool = False
    requires_public_image_url: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageProviderConfig:
    """生图 Provider 配置；同一个 logical model 可由多个 Provider 承载。"""

    id: str = ""
    display_name: str = ""
    enabled: bool = True
    base_url: str = ""
    api_key_env: str = ""
    api_key: str | None = None
    priority: int = 100
    discover_models: bool = False
    protocols: list[str] = field(default_factory=lambda: ["openai_images"])
    models: list[ImageProviderModelConfig] = field(default_factory=list)
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ImageGenConfig:
    model: str = "image2"
    size: str = "1024x1024"
    # auto 让 provider 自适配 quality；high 单次响应可能持续数分钟，超过远端网关 idle 上限
    # 会被 RemoteProtocolError 截断；如需高画质请显式在管理后台改回 high。
    quality: str = "auto"
    output_format: str = "png"
    # 图生图编辑时尽量保留原图主体和细节：low | high（OpenAI Images 兼容参数）
    edit_input_fidelity: str = "high"
    # 多 Provider 失败切换。仅对网络、限流、5xx、空响应、结构异常等可重试错误生效。
    failover_enabled: bool = True
    failover_on: list[str] = field(default_factory=lambda: [
        "network",
        "timeout",
        "rate_limit",
        "server_error",
        "empty_response",
        "malformed_response",
        "provider_unavailable",
        "auth",
        "quota",
    ])
    model_discovery_enabled: bool = True
    model_discovery_ttl_seconds: int = 3600
    provider_poll_interval_seconds: float = 2.0
    # 受控候选生图：默认关闭，避免素材任务一次生成多张候选导致上游成本放大。
    contact_sheet_enabled: bool = False
    contact_sheet_rows: int = 3
    contact_sheet_cols: int = 3
    green_screen_color: str = "auto"
    green_screen_tolerance: int = 48
    contact_sheet_prompt_template: str = (
        "Create a {rows}x{cols} contact sheet containing exactly {count} distinct TRUE pixel-art game asset candidates from this generation brief: {description}. "
        "In every cell, follow the generation brief exactly, not a painted digital illustration. "
        "Canvas size for each candidate must be exactly {width}x{height} pixels, where each pixel is one square grid cell. "
        "Use large, chunky readable pixels, limited colors, and a simple silhouette. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and clean extraction. "
        "Use pure solid key-color {green} for all empty/background cells for chroma-key removal; keep every visible subject color outside the maximum key-color tolerance ({key_tolerance} RGB Euclidean distance) from {green}. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. "
        "The output image should be pixel-perfect, each grid cell only contains one color. No text, no watermark, no extra frame, no labels."
    )
    # Prompt guard 只审核用户原始输入，不把服务端模板暴露给模型。
    prompt_guard_enabled: bool = True
    prompt_guard_remote: bool = True
    prompt_guard_model: str = ""
    prompt_guard_failure_policy: str = "local"  # local | reject
    # 用户原始描述上限；Web 表单和后端校验统一为 3000 字。
    prompt_guard_max_chars: int = 3000
    # 候选图评分：把候选图片直接上传到 VL，按像素素材质量排序并选择最高分。
    candidate_vl_ranking_enabled: bool = True
    candidate_vl_ranking_model: str = ""
    candidate_vl_ranking_failure_policy: str = "first"  # first | reject
    # 候选生成策略：
    #   n_sample     —— 直接调用 n=N 让模型返回 N 张独立 full-res 图，每张单独抠色评分（默认）
    #   contact_sheet —— 旧路径：生成 RxC 九宫格再切图
    candidate_mode: str = "n_sample"
    # n-sample 候选数量；默认 1 个，避免候选模式开启时放大上游成本。
    n_sample_count: int = 1
    # 若 provider 不支持 n=N 单次返回，fallback 循环调用时追加的 prompt 变体（非强约束，仅鼓励差异）
    n_sample_prompt_variations: list[str] = field(default_factory=lambda: [
        "slight variation in color tone.",
        "slight variation in lighting and highlight.",
        "slight variation in material texture emphasis.",
        "slight variation in silhouette pose.",
    ])
    # n-sample 单图 prompt 模板；与 contact_sheet_prompt_template 类似但不含 rows/cols
    n_sample_prompt_template: str = (
        "Create one TRUE pixel-art game asset candidate from this generation brief: {description}. "
        "Follow the generation brief exactly, not a painted digital illustration. "
        "Canvas size must be exactly {width}x{height} pixels, where each pixel is one square grid cell. "
        "Use large, chunky readable pixels, limited colors, and a simple silhouette. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and clean extraction. "
        "Use pure solid key-color {green} for all empty/background cells for chroma-key removal; keep every visible subject color outside the maximum key-color tolerance ({key_tolerance} RGB Euclidean distance) from {green}. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. "
        "The output image should be pixel-perfect, each grid cell only contains one color. No text, no watermark, no extra frame, no labels."
    )


@dataclass
class VisionConfig:
    model: str = "claude-opus-4-8"
    temperature: float = 0.2
    max_tokens: int = 2048
    retry_on_parse: int = 1


@dataclass
class PixelizeConfig:
    output_size: tuple[int, int] = (128, 128)
    colors: int = 16
    dither: str = "floyd_steinberg"
    preset: str = "auto"
    preview_scale: int = 4
    edge_enhance: float = 0.1
    saturation: float = 1.0
    # 下采样模式：smart（自动对齐像素格）| box | bicubic | lanczos | nearest
    resample: str = "smart"
    # 是否在 smart 模式下尝试探测输入像素格并吸附到整数倍
    snap_to_grid: bool = True
    # 自动抠背景（参考 pixel_bg：边框中位数 key 色 + 双阈值连通域 + 二值 alpha）
    remove_bg: bool = False
    bg_tolerance: int = 12
    bg_feather: int = 0
    # 边缘风格：hard | feather | outline。bg_feather 表示对应强度。
    edge_style: str = "hard"
    # 自动裁剪主体，再缩小到目标像素尺寸
    auto_crop: bool = False
    crop_padding: float = 0.12
    crop_square: bool = True
    # 调色板策略：auto（保持原 K-means） | ramp（VL/本地色相阶梯） | kmeans（强制 K-means）
    palette_mode: str = "auto"
    # AI 生图/图生图结果的第一步网格对齐预处理；本地上传默认不启用。
    # perfect_pixel | legacy | none
    generated_preprocess_method: str = "perfect_pixel"


@dataclass
class AssetConfig:
    """游戏素材直出默认参数。"""

    output_dir: str = "图片"
    pixel_size: tuple[int, int] = (16, 16)
    colors: int = 8
    dither: str = "none"
    preview_scale: int = 12
    source_copy: bool = True
    image_quality: str = "low"
    skip_vl: bool = True
    remove_bg: bool = True
    bg_tolerance: int = 26
    bg_feather: int = 0
    edge_style: str = "hard"
    bg_removal_algorithm: str = "pixel_bg"  # pixel_bg 双阈值连通域 + 二值 alpha；旧值运行时兼容
    color_to_alpha_shape: str = "sphere"  # sphere | cube
    color_to_alpha_transparency: int = 48
    color_to_alpha_opacity: int = 255
    color_to_alpha_interpolation: str = "linear"
    auto_crop: bool = True
    crop_padding: float = 0.12
    crop_square: bool = True
    grid_mode: bool = True
    grid_json: bool = True
    grid_cleanup: bool = False
    grid_outline: bool = False
    grid_outline_strength: int = 1
    grid_min_neighbors: int = 1
    fit_canvas: bool = False
    fit_mode: str = "smart"
    fit_padding: int = 1
    fit_min_axis_coverage: float = 0.7
    # Asset 直出默认使用 README 中的 TRUE pixel-art + 动态纯色背景标准模板；
    # 具体语义由 asset_kind 分流（物品图标 / UI 组件 / 平铺纹理 / 游戏 Logo）。
    palette_mode: str = "auto"
    prompt_template: str = (
        "Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} "
        "designed for {asset_usage_label}, not a painted digital illustration. Subject: {name}. "
        "Subject kind: {subject_kind_label}. Canvas size must be exactly {width}x{height} pixels, "
        "where each pixel is one square grid cell. Use large, chunky readable pixels, limited colors, "
        "and a simple silhouette. "
        "Use no more than {max_colors} visible subject colors; background color does not count. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty pixel rows around all edges for safe sprite padding "
        "and {placement_context}. Use a pure solid single-color background for chroma-key removal; "
        "choose a background color that is not close to any visible subject color, with color-distance greater "
        "than the removal tolerance ({key_tolerance} RGB Euclidean distance). No anti-aliasing or smoothing — "
        "every pixel must be a perfect square aligned to the grid. The output image should be pixel-perfect, "
        "each grid cell only contains one color. {forbidden_elements}"
    )


@dataclass
class SpriteConfig:
    """序列帧默认参数（mosaic 单图模式）。

    1 次 API 调用产出 rows×cols 网格 sprite sheet，后端按格切图（基于前景投影找
    最佳切分线）+ chroma-key 抠色 + 共享调色板。
    """

    output_dir: str = "图片/sprites"
    # mosaic 网格默认值；前端可显式覆盖。
    rows: int = 1
    cols: int = 8
    frame_count: int = 8
    # 单次任务总帧数上限（rows × cols ≤ max_frame_count）。
    max_frame_count: int = 64
    # 网格行/列上限（前端面板与后端校验共用）。
    max_grid_rows: int = 8
    max_grid_cols: int = 8
    fps: int = 8
    pixel_size: tuple[int, int] = (64, 64)
    colors: int = 16
    dither: str = "none"
    image_quality: str = "high"
    # 兼容旧 GIF 间隔字段；新流程以 fps 为主，默认不生成 GIF。
    duration_ms: int = 125
    loop: int = 0
    gif_export: bool = False
    frame_size_step: int = 16
    anchor: str = "bottom_center"
    green_screen_color: str = "auto"
    green_screen_tolerance: int = 48
    bg_tolerance: int = 26
    crop_padding: float = 0.12
    crop_square: bool = True
    shared_palette: bool = True
    # mosaic 模式 prompt 模板（无参考图，纯文生图）。
    # 占位符：{description}/{rows}/{cols}/{frame_width}/{frame_height}/{sheet_width}/{sheet_height}/{row_block}/{green}/{key_tolerance}/{max_colors}
    # 新增渲染尺寸占位符：{render_width}/{render_height}/{cell_render_width}/{cell_render_height}/{upscale}
    # - sheet_width/sheet_height/frame_width/frame_height 表示最终 pixel-art 粒度；
    # - render_width/render_height/cell_render_width/cell_render_height 表示 API 实际渲染画布；
    # - upscale 表示每个 pixel-art 像素应被画成多少 render pixels 的实心方块。
    mosaic_prompt_template: str = (
        "Create a TRUE pixel-art sprite sheet for the following subject. "
        "Subject: {description}. "
        "Layout: an exact {rows}x{cols} grid of sprites, read left-to-right then top-to-bottom. "
        "Render the entire image at exactly {render_width}x{render_height} render pixels; every cell occupies {cell_render_width}x{cell_render_height} render pixels. "
        "Each cell represents a {frame_width}x{frame_height} pixel-art sprite, so every pixel-art pixel must be drawn as a perfectly square block of {upscale}x{upscale} render pixels (no anti-aliasing inside the block). "
        "Each row is one independent animation loop with {cols} frames, listed below:\n{row_block}\n"
        "Character/subject consistency: keep the same identity, palette, outline thickness, scale, and proportions across every cell. "
        "Background: use pure solid key-color {green} for ALL empty/background pixels for chroma-key removal; keep visible colors outside the maximum key-color tolerance ({key_tolerance} RGB Euclidean distance) from {green}. "
        "Use no more than {max_colors} visible subject colors; background color does not count. "
        "Style: crisp pixel art, hard edges, limited palette, no painterly blending, no anti-aliased soft brush. "
        "Do not add text, watermark, UI, border, grid lines, labels, numbers, or shadows outside the subject. Do not draw extra frames outside the {rows}x{cols} grid."
    )
    # mosaic 模式 + 参考图（图生图）prompt 模板。
    # 额外占位符：{base_template} 会被替换为已渲染好的 mosaic_prompt_template 文本。
    mosaic_reference_prompt_template: str = (
        "Re-create the sprite sheet described below based on the provided reference image as the character source. "
        "The reference image defines the core character design (silhouette, palette, costume, proportions). "
        "Reuse the reference character identity in EVERY cell; only the action/pose changes per cell.\n\n"
        "{base_template}\n\n"
        "Strictly preserve the reference character's identity, color palette, and proportions across every cell."
    )


@dataclass
class CacheConfig:
    enabled: bool = True
    dir: str = ".pix_cache"


@dataclass
class OutputConfig:
    root: str = "outputs"


@dataclass
class HistoryConfig:
    max_items: int = 200


@dataclass
class UiConfig:
    language: str = "zh-CN"


@dataclass
class AppConfig:
    api: ApiConfig = field(default_factory=ApiConfig)
    image_gen: ImageGenConfig = field(default_factory=ImageGenConfig)
    image_providers: list[ImageProviderConfig] = field(default_factory=list)
    vision: VisionConfig = field(default_factory=VisionConfig)
    pixelize: PixelizeConfig = field(default_factory=PixelizeConfig)
    asset: AssetConfig = field(default_factory=AssetConfig)
    sprite: SpriteConfig = field(default_factory=SpriteConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- 合并 ----------



def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []



def _provider_model_from_mapping(data: Mapping[str, Any]) -> ImageProviderModelConfig:
    model = ImageProviderModelConfig()
    _update_dataclass(model, data)
    model.operations = _as_str_list(model.operations) or ["text_to_image", "image_to_image"]
    model.sizes = _as_str_list(model.sizes)
    model.qualities = _as_str_list(model.qualities)
    model.output_formats = _as_str_list(model.output_formats)
    model.provider_model = model.provider_model or model.id
    model.label = model.label or model.id
    return model



def _provider_from_mapping(data: Mapping[str, Any]) -> ImageProviderConfig:
    provider = ImageProviderConfig()
    simple = {key: value for key, value in data.items() if key != "models"}
    _update_dataclass(provider, simple)
    provider.protocols = _as_str_list(provider.protocols) or ["openai_images"]
    raw_models = data.get("models")
    if isinstance(raw_models, list):
        provider.models = [
            _provider_model_from_mapping(item)
            for item in raw_models
            if isinstance(item, Mapping)
        ]
    provider.display_name = provider.display_name or provider.id
    return provider



def _set_or_append_provider(cfg: AppConfig, provider: ImageProviderConfig) -> None:
    if not provider.id:
        return
    for index, existing in enumerate(cfg.image_providers):
        if existing.id == provider.id:
            cfg.image_providers[index] = provider
            return
    cfg.image_providers.append(provider)



def _packy_provider_from_legacy(cfg: AppConfig) -> ImageProviderConfig | None:
    api_key = cfg.api.image_api_key or os.getenv("PACKY_API_KEY")
    return ImageProviderConfig(
        id="packy",
        display_name="Packy",
        enabled=True,
        base_url=cfg.api.base_url or os.getenv("PACKY_BASE_URL", "https://www.packyapi.com"),
        api_key_env="PACKY_API_KEY",
        api_key=api_key,
        priority=10,
        discover_models=False,
        protocols=["openai_images"],
        models=[
            ImageProviderModelConfig(
                id="image2",
                provider_model="gpt-image-2",
                label="image2",
                protocol="openai_images",
                operations=["text_to_image", "image_to_image"],
                sizes=["auto", "1024x1024", "1536x1024", "1024x1536", "2048x1024", "1024x2048"],
                qualities=["auto", "low", "medium", "high"],
                output_formats=["png", "jpeg", "webp"],
                extra={"supports_input_fidelity": False},
            ),
            ImageProviderModelConfig(
                id="gemini-3.1-flash-image-preview",
                provider_model="gemini-3.1-flash-image-preview",
                label="Gemini 3.1 Flash Image Preview",
                protocol="openai_images",
                operations=["text_to_image", "image_to_image"],
                sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
                output_formats=["png"],
            ),
            ImageProviderModelConfig(
                id="gemini-3-pro-image-preview",
                provider_model="gemini-3-pro-image-preview",
                label="Gemini 3 Pro Image Preview",
                protocol="openai_images",
                operations=["text_to_image", "image_to_image"],
                sizes=["auto", "1024x1024", "1536x1024", "1024x1536"],
                output_formats=["png"],
            ),
        ],
    )



def _crazyrouter_provider_from_env() -> ImageProviderConfig | None:
    api_key = os.getenv("CRAZYROUTER_API_KEY")
    if not api_key:
        return None
    return ImageProviderConfig(
        id="crazyrouter",
        display_name="Crazyrouter",
        enabled=True,
        base_url=os.getenv("CRAZYROUTER_BASE_URL", "https://crazyrouter.com"),
        api_key_env="CRAZYROUTER_API_KEY",
        api_key=api_key,
        priority=30,
        discover_models=True,
        protocols=["openai_images", "midjourney", "ideogram", "fal", "kling", "gemini_native"],
        models=[],
    )



def _shengsuanyun_provider_from_env() -> ImageProviderConfig | None:
    api_key = os.getenv("SHENGSUANYUN_API_KEY")
    if not api_key:
        return None
    return ImageProviderConfig(
        id="shengsuanyun",
        display_name="ShengSuanYun（胜算云）",
        enabled=True,
        base_url=os.getenv("SHENGSUANYUN_BASE_URL", "https://router.shengsuanyun.com"),
        api_key_env="SHENGSUANYUN_API_KEY",
        api_key=api_key,
        priority=20,
        discover_models=False,
        protocols=["shengsuanyun"],
        models=[
            ImageProviderModelConfig(
                id="image2",
                provider_model="openai/gpt-image-2",
                label="image2",
                protocol="shengsuanyun",
                operations=["text_to_image", "image_to_image"],
                sizes=["auto", "1024x1024", "1536x1024", "1024x1536", "2048x1024", "1024x2048"],
                qualities=["auto", "low", "medium", "high"],
                output_formats=["png", "jpeg", "webp"],
                edit_mode="image_input",
                extra={"supports_input_fidelity": False},
            ),
        ],
    )



def _apply_providers_json(cfg: AppConfig, raw: str | None) -> None:
    if not raw:
        return
    try:
        parsed = json.loads(raw)
    except ValueError:
        return
    providers_raw = parsed.get("image_providers") if isinstance(parsed, dict) else parsed
    if not isinstance(providers_raw, list):
        return
    for item in providers_raw:
        if isinstance(item, Mapping):
            _set_or_append_provider(cfg, _provider_from_mapping(item))



def _normalize_image_providers(cfg: AppConfig) -> None:
    normalized: list[ImageProviderConfig] = []
    for provider in cfg.image_providers:
        if isinstance(provider, ImageProviderConfig):
            normalized.append(provider)
        elif isinstance(provider, Mapping):
            normalized.append(_provider_from_mapping(provider))
    cfg.image_providers = normalized
    crazy = _crazyrouter_provider_from_env()
    if crazy is not None:
        _set_or_append_provider(cfg, crazy)
    shengsuanyun = _shengsuanyun_provider_from_env()
    if shengsuanyun is not None:
        _set_or_append_provider(cfg, shengsuanyun)
    legacy = _packy_provider_from_legacy(cfg)
    if legacy is not None and not any(provider.id == "packy" for provider in cfg.image_providers):
        cfg.image_providers.append(legacy)
    _apply_providers_json(cfg, os.getenv("PIX_IMAGE_PROVIDERS_JSON"))
    cfg.image_providers.sort(key=lambda item: int(item.priority or 100))



def _update_dataclass(obj: Any, values: Mapping[str, Any]) -> None:

    """浅层更新 dataclass 字段；未识别的字段静默忽略。"""
    if not values:
        return
    annotations = getattr(type(obj), "__annotations__", {})
    for key, value in values.items():
        if key not in annotations:
            continue
        current = getattr(obj, key, None)
        # 特殊处理 tuple[int, int]
        if isinstance(current, tuple) and isinstance(value, (list, tuple)):
            try:
                setattr(obj, key, tuple(int(v) for v in value))
            except (TypeError, ValueError):
                setattr(obj, key, current)
            continue
        # 特殊处理布尔（避免被 "false" 这种字符串误转）
        if isinstance(current, bool) and isinstance(value, str):
            setattr(obj, key, value.strip().lower() in ("1", "true", "yes", "on"))
            continue
        # 简单数值转换
        if isinstance(current, int) and not isinstance(value, bool) and isinstance(value, (int, float, str)):
            try:
                setattr(obj, key, int(value))
                continue
            except (TypeError, ValueError):
                pass
        if isinstance(current, float) and isinstance(value, (int, float, str)):
            try:
                setattr(obj, key, float(value))
                continue
            except (TypeError, ValueError):
                pass
        setattr(obj, key, value)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fp:
        return tomllib.load(fp)


def _apply_mapping(cfg: AppConfig, data: Mapping[str, Any]) -> None:
    for section_name, section_values in data.items():
        if section_name == "image_providers" and isinstance(section_values, list):
            cfg.image_providers = [
                _provider_from_mapping(item)
                for item in section_values
                if isinstance(item, Mapping)
            ]
            continue
        if not isinstance(section_values, Mapping):
            continue
        section_obj = getattr(cfg, section_name, None)
        if section_obj is None:
            continue
        _update_dataclass(section_obj, section_values)


def _apply_env(cfg: AppConfig) -> None:
    """从环境变量覆盖关键字段。"""
    api_key = os.getenv("PACKY_API_KEY")
    vl_key = os.getenv("PACKY_VL_API_KEY") or api_key
    gemini_key = os.getenv("PACKY_GEMINI_API_KEY")
    base_url = os.getenv("PACKY_BASE_URL")
    default_model = os.getenv("PIX_IMAGE_DEFAULT_MODEL")

    if api_key:
        cfg.api.image_api_key = api_key
    if vl_key:
        cfg.api.vl_api_key = vl_key
    if gemini_key:
        cfg.api.gemini_api_key = gemini_key
    if base_url:
        cfg.api.base_url = base_url
    if default_model:
        cfg.image_gen.model = "image2" if default_model.strip().lower() == "gpt-image-2" else default_model


# ---------- 公共入口 ----------


def load_config(
    config_file: Path | str | None = None,
    overrides: Mapping[str, Any] | None = None,
    env_file: Path | str | None = ".env",
) -> AppConfig:
    """加载配置。

    Args:
        config_file: 可选 TOML 配置文件路径；默认检索 ./config.toml。
        overrides: 调用方传入的覆盖值，结构与 AppConfig 一致（section -> field -> value）。
        env_file: .env 路径，None 表示跳过。
    """
    # 1. 加载 .env
    if env_file is not None and not os.getenv("PIX_DISABLE_DOTENV"):
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()  # 尝试默认搜索

    cfg = AppConfig()

    # 2. 合并 config.toml
    candidate_paths: list[Path] = []
    if config_file is not None:
        candidate_paths.append(Path(config_file))
    else:
        candidate_paths.append(Path("config.toml"))
    for p in candidate_paths:
        _apply_mapping(cfg, _load_toml(p))

    # 3. 环境变量
    _apply_env(cfg)

    # 4. 显式 overrides
    if overrides:
        _apply_mapping(cfg, overrides)

    _normalize_image_providers(cfg)
    return cfg


def require_image_api_key(cfg: AppConfig) -> str:
    if not cfg.api.image_api_key:
        raise RuntimeError(
            "未找到可用生图 API key。旧 Packy 兼容路径请设置 PACKY_API_KEY；"
            "新 Provider 推荐设置 CRAZYROUTER_API_KEY 或配置 [[image_providers]]。"
        )
    return cfg.api.image_api_key


def require_vl_api_key(cfg: AppConfig) -> str:
    key = cfg.api.vl_api_key or cfg.api.image_api_key
    if not key:
        raise RuntimeError(
            "未找到 PACKY_VL_API_KEY / PACKY_API_KEY。请在 .env 中设置 VL 分组令牌。"
        )
    return key


def is_gemini_model(model: str) -> bool:
    """判断模型名是否为 Gemini 系列。"""
    return "gemini" in model.lower()


def require_image_api_key_for_model(cfg: AppConfig, model: str | None = None) -> str:
    """根据模型名选择对应的 API key。

    Gemini 模型优先使用 gemini_api_key，回退到 image_api_key；
    其他模型直接使用 image_api_key。
    """
    effective_model = model or cfg.image_gen.model
    if is_gemini_model(effective_model) and cfg.api.gemini_api_key:
        return cfg.api.gemini_api_key
    return require_image_api_key(cfg)
