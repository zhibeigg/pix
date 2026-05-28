"""统一的配置加载与合并。

优先级（后者覆盖前者）：
    默认值 < config.toml < .env < 环境变量 < 调用方显式覆盖
"""

from __future__ import annotations

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
    # sora 分组 key，用于 gpt-image-2
    image_api_key: str | None = None
    # default 分组 key，用于 VL（Claude / Gemini / gpt-4o）
    vl_api_key: str | None = None
    # 是否信任进程级代理 / 系统代理。本地常见的 Clash 等本地代理会在长时间空闲时主动断开
    # 生图连接，造成 RemoteProtocolError；默认禁用，需要走代理时再显式开启。
    trust_env_proxies: bool = False
    # 显式 HTTPS 代理。优先级高于系统代理；为空字符串表示不使用代理。
    proxy: str | None = None


@dataclass
class ImageGenConfig:
    model: str = "gpt-image-2"
    size: str = "1024x1024"
    # auto 让 packyapi 自适配 quality；high 单次响应可能 7~10 分钟，超过远端网关 idle 上限
    # 会被 RemoteProtocolError 截断；如需高画质请显式在管理后台改回 high。
    quality: str = "auto"
    output_format: str = "png"
    # 图生图编辑时尽量保留原图主体和细节：low | high（Packy/OpenAI 兼容参数）
    edit_input_fidelity: str = "high"
    # 受控生图：默认让模型一次生成九宫格候选，后端再切图和抠动态纯色 key background。
    contact_sheet_enabled: bool = True
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
    # 候选图评分：把切出的候选一次性送入 VL，按像素素材质量排序并选择最高分。
    candidate_vl_ranking_enabled: bool = True
    candidate_vl_ranking_model: str = ""
    candidate_vl_ranking_failure_policy: str = "first"  # first | reject
    # 候选生成策略：
    #   n_sample     —— 直接调用 n=N 让模型返回 N 张独立 full-res 图，每张单独抠色评分（默认）
    #   contact_sheet —— 旧路径：生成 RxC 九宫格再切图
    candidate_mode: str = "n_sample"
    # n-sample 候选数量；经验值 4 个；成本随 N 线性增长
    n_sample_count: int = 4
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
    model: str = "claude-opus-4-7"
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
    # 自动抠背景（以四角纯色作为 key，使用 Color-to-Alpha）
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
    colors: int = 12
    dither: str = "none"
    preview_scale: int = 12
    source_copy: bool = True
    image_quality: str = "low"
    skip_vl: bool = True
    remove_bg: bool = True
    bg_tolerance: int = 26
    bg_feather: int = 0
    edge_style: str = "hard"
    bg_removal_algorithm: str = "color_to_alpha"  # 固定使用 color_to_alpha；保留字段兼容旧配置
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
    # Asset 直出默认使用 README 中的 TRUE pixel-art + 动态纯色背景标准模板
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
    mosaic_prompt_template: str = (
        "Create a TRUE pixel-art sprite sheet for the following subject. "
        "Subject: {description}. "
        "Layout: an exact {rows}x{cols} grid of sprites, read left-to-right then top-to-bottom. "
        "Total canvas: {sheet_width}x{sheet_height} pixels. Each cell is exactly {frame_width}x{frame_height} pixels and aligned to the grid. "
        "Each row is one independent animation loop with {cols} frames, listed below:\n{row_block}\n"
        "Character/subject consistency: keep the same identity, palette, outline thickness, scale, and proportions across every cell. "
        "Background: use pure solid key-color {green} for ALL empty/background pixels for chroma-key removal; keep visible colors outside the maximum key-color tolerance ({key_tolerance} RGB Euclidean distance) from {green}. "
        "Use no more than {max_colors} visible subject colors; background color does not count. "
        "Style: crisp pixel art, hard edges, limited palette, no painterly blending, no anti-aliased soft brush. Every pixel must be a perfect square aligned to the grid. "
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
    base_url = os.getenv("PACKY_BASE_URL")

    if api_key:
        cfg.api.image_api_key = api_key
    if vl_key:
        cfg.api.vl_api_key = vl_key
    if base_url:
        cfg.api.base_url = base_url


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

    return cfg


def require_image_api_key(cfg: AppConfig) -> str:
    if not cfg.api.image_api_key:
        raise RuntimeError(
            "未找到 PACKY_API_KEY。请在 .env 中设置或导出环境变量。"
            "（gpt-image-2 需要 sora 分组的令牌）"
        )
    return cfg.api.image_api_key


def require_vl_api_key(cfg: AppConfig) -> str:
    key = cfg.api.vl_api_key or cfg.api.image_api_key
    if not key:
        raise RuntimeError(
            "未找到 PACKY_VL_API_KEY / PACKY_API_KEY。请在 .env 中设置 VL 分组令牌。"
        )
    return key
