"""Web API Pydantic schema。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import re

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator
from PIL import Image

from pix_web.storage import file_url

JobType = Literal[
    "asset",
    "text_to_image",
    "image_to_image",
    "local_pixelize",
    "local_bg_remove",
    "repixelize",
    "sprite_sheet",
]

# 尺寸重试最大尝试次数硬上限（请求层兜底；实际上限以系统配置 image_gen.size_retry_max_attempts_limit 为准）。
SIZE_RETRY_MAX_ATTEMPTS_LIMIT = 20


@lru_cache(maxsize=4096)
def _load_meta_json_cached(path: str, _mtime_ns: int, _size: int) -> dict[str, Any]:
    """按 (路径, mtime, 大小) 缓存解析结果。

    单次响应序列化里同一 meta.json 会被 20~30 个 computed_field 反复读取；
    缓存把每个 output 的上万次磁盘读盘降为一次解析 + 若干次 os.stat，避免
    序列化阶段长时间占用 DB 连接（连接池耗尽根因之一）。捕获范围用 ValueError
    覆盖 JSONDecodeError 与 UnicodeDecodeError（非法编码的旧 meta 文件），
    防止单个坏文件让整份列表序列化失败。
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_meta_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        stat = os.stat(path)
    except OSError:
        return {}
    return _load_meta_json_cached(path, stat.st_mtime_ns, stat.st_size)


def _grid_meta_from_output_meta(path: str | None) -> dict[str, Any]:
    pixelize = _load_meta_json(path).get("pixelize")
    if not isinstance(pixelize, dict):
        return {}
    grid = pixelize.get("grid")
    return grid if isinstance(grid, dict) else {}


def _contact_sheet_meta(path: str | None) -> dict[str, Any]:
    image_gen = _load_meta_json(path).get("image_gen")
    if not isinstance(image_gen, dict):
        return {}
    contact_sheet = image_gen.get("contact_sheet")
    return contact_sheet if isinstance(contact_sheet, dict) else {}


def _sprite_meta(path: str | None) -> dict[str, Any]:
    sprite = _load_meta_json(path).get("sprite")
    return sprite if isinstance(sprite, dict) else {}


def _size_retry_meta(path: str | None) -> dict[str, Any]:
    image_gen = _load_meta_json(path).get("image_gen")
    if not isinstance(image_gen, dict):
        return {}
    size_retry = image_gen.get("size_retry")
    return size_retry if isinstance(size_retry, dict) else {}


def _outputs_meta(path: str | None) -> dict[str, Any]:
    outputs = _load_meta_json(path).get("outputs")
    return outputs if isinstance(outputs, dict) else {}


def _as_size_pair(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        width, height = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return [width, height]


def _meta_pixelized_size(path: str | None) -> list[int] | None:
    pixelize = _load_meta_json(path).get("pixelize")
    if not isinstance(pixelize, dict):
        return None
    effective = pixelize.get("effective_params")
    if isinstance(effective, dict):
        size = _as_size_pair(effective.get("output_size"))
        if size:
            return size
    grid = pixelize.get("grid")
    if isinstance(grid, dict):
        readability = grid.get("readability")
        if isinstance(readability, dict):
            size = _as_size_pair([readability.get("width"), readability.get("height")])
            if size:
                return size
    return None


@lru_cache(maxsize=4096)
def _image_pixel_size_cached(path: str, _mtime_ns: int, _size: int) -> tuple[int, int] | None:
    try:
        with Image.open(path) as opened:
            return (int(opened.width), int(opened.height))
    except Exception:  # noqa: BLE001 - API 响应不能因为旧文件缺失/损坏失败
        return None


def _image_pixel_size(path: str | None) -> list[int] | None:
    if not path:
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    size = _image_pixel_size_cached(path, stat.st_mtime_ns, stat.st_size)
    return [size[0], size[1]] if size else None


def _resolve_meta_relative_path(meta_json_path: str | None, value: str | None) -> str | None:
    if not meta_json_path or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(
        Path(meta_json_path).with_name(value)
        if "/" not in value and "\\" not in value
        else Path(meta_json_path).parent / value
    )


JobStatus = Literal["pending", "running", "waiting", "succeeded", "failed", "cancelled"]
VideoBridgeModel = Literal[
    "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128",
    "doubao-seedance-2-0-mini-260615",
]


class EmailCodeRequest(BaseModel):
    email: EmailStr
    turnstile_token: str = Field(default="", max_length=2048)


class EmailCodeResponse(BaseModel):
    ok: bool = True
    retry_after_seconds: int
    expires_in_seconds: int
    debug_code: str | None = None


_RE_PASSWORD_LETTER = re.compile(r"[a-zA-Z]")
_RE_PASSWORD_DIGIT = re.compile(r"\d")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=9, max_length=128)
    display_name: str = Field(default="", max_length=120)
    verification_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    referral_code: str = Field(default="", max_length=32)

    @field_validator("password")
    @classmethod
    def _check_password_mixed(cls, v: str) -> str:
        if not _RE_PASSWORD_LETTER.search(v) or not _RE_PASSWORD_DIGIT.search(v):
            raise ValueError("密码必须同时包含英文和数字")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ResetCodeRequest(BaseModel):
    email: EmailStr
    turnstile_token: str = Field(default="", max_length=2048)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=9, max_length=128)
    verification_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("new_password")
    @classmethod
    def _check_password_mixed(cls, v: str) -> str:
        if not _RE_PASSWORD_LETTER.search(v) or not _RE_PASSWORD_DIGIT.search(v):
            raise ValueError("密码必须同时包含英文和数字")
        return v


class BootstrapAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SetupStatusResponse(BaseModel):
    needs_admin: bool
    user_count: int
    admin_count: int
    email_provider: str
    debug_codes_available: bool
    registration_bonus_credits: int = 0
    local_test_login_available: bool = False
    local_test_account_email: str | None = None
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BootstrapAdminResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreditBalanceResponse(BaseModel):
    available_credits: int
    reserved_credits: int
    total_recharged: int
    total_consumed: int


class FileTicketResponse(BaseModel):
    ticket: str
    expires_in: int


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(default="", max_length=120)
    scopes: list[str] = Field(default_factory=list, max_length=16)
    expires_at: datetime | None = None
    custom_key: str | None = Field(default=None, max_length=160)


class ApiKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    scopes: list[str] | None = Field(default=None, max_length=16)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: list[str] = []
    enabled: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(BaseModel):
    key: str
    item: ApiKeyResponse


class ExternalMeResponse(BaseModel):
    user: UserResponse
    scopes: list[str]
    key_prefix: str


class CreditTransactionResponse(BaseModel):
    id: int
    type: str
    amount: int
    balance_after: int
    job_id: int | None
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralCurrencyTotalsResponse(BaseModel):
    currency: str
    pending_cents: int
    available_cents: int
    total_reward_cents: int


class ReferralInviteResponse(BaseModel):
    id: int
    referred_user_id: int
    referred_user_email: str
    referred_user_display_name: str
    created_at: datetime


class ReferralRewardResponse(BaseModel):
    id: int
    referred_user_id: int
    referred_user_email: str
    order_id: int
    order_amount_cents: int
    order_credits: int
    amount_cents: int
    remaining_cents: int
    currency: str
    rate_bps: int
    status: str
    available_at: datetime
    created_at: datetime


class ReferralSettlementResponse(BaseModel):
    id: int
    type: str
    amount_cents: int
    currency: str
    credits: int
    status: str
    note: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReferralSummaryResponse(BaseModel):
    code: str
    invite_url: str
    enabled: bool
    commission_rate_bps: int
    pending_days: int
    primary_currency: str
    pending_cents: int
    available_cents: int
    total_reward_cents: int
    invited_count: int
    totals_by_currency: list[ReferralCurrencyTotalsResponse]
    invites: list[ReferralInviteResponse]
    rewards: list[ReferralRewardResponse]
    settlements: list[ReferralSettlementResponse]


class ReferralTransferRequest(BaseModel):
    currency: str = Field(default="cny", max_length=12)


class ReferralWithdrawalRequest(BaseModel):
    amount_cents: int = Field(ge=1)
    currency: str = Field(default="cny", max_length=12)
    note: str = Field(default="", max_length=500)


class PixelizeParamsSchema(BaseModel):
    output_size: tuple[int, int] = (128, 128)
    colors: int = Field(default=16, ge=2, le=256)
    dither: str = "floyd_steinberg"
    preset: str = "auto"
    preview_scale: int = Field(default=4, ge=0, le=64)
    edge_enhance: float = Field(default=0.1, ge=0.0, le=1.0)
    saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    resample: str = "smart"
    snap_to_grid: bool = True
    remove_bg: bool = False
    bg_tolerance: int = Field(default=12, ge=0, le=128)
    bg_feather: int = Field(default=0, ge=0, le=8)
    edge_style: Literal["hard", "feather", "outline"] = "hard"
    bg_removal_algorithm: Literal[
        "pixel_bg",
        "color_to_alpha",
        "auto",
        "imagemagick_fuzz_floodfill_alpha",
        "flood_fill",
        "hybrid",
    ] = "pixel_bg"
    auto_crop: bool = False
    crop_padding: float = Field(default=0.12, ge=0.0, le=1.0)
    crop_square: bool = True
    palette_mode: Literal["auto", "ramp", "kmeans"] = "auto"
    generated_preprocess_method: Literal["perfect_pixel", "legacy", "none"] = "perfect_pixel"


class GridDesignSchema(BaseModel):
    mode: Literal["off", "extract"] = "off"


class StyleProfileSchema(BaseModel):
    """项目级风格档案，作为用户可控的 prompt 补充约束。"""

    project_name: str = Field(default="", max_length=80)
    palette: str = Field(default="", max_length=120)
    line_style: str = Field(default="", max_length=120)
    lighting: str = Field(default="", max_length=120)
    view_rule: str = Field(default="", max_length=120)
    avoid_elements: str = Field(default="", max_length=200)


class PromptPreviewResponse(BaseModel):
    mode: str
    positive_prompt: str
    applied_style_profile: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SpriteParamsSchema(BaseModel):
    """序列帧任务参数（mosaic 单图模式）。

    1 次 API 调用产出 rows×cols 网格 sprite sheet。`row_prompts` 长度等于 rows，
    每条对应一行的动作循环描述。`reference_image_path` 提供时切到 image-edit 模式。
    """

    mode: Literal["mosaic", "video_bridge"] = "mosaic"
    rows: int = Field(default=1, ge=1, le=8)
    cols: int = Field(default=8, ge=1, le=8)
    row_prompts: list[str] = Field(default_factory=list, max_length=8)
    reference_image_path: str | None = None
    frame_count: int = Field(default=8, ge=1, le=64)
    fps: int = Field(default=8, ge=1, le=60)
    gif_export: bool = False
    duration_ms: int = Field(default=125, ge=20, le=2000)
    loop: int = Field(default=0, ge=0, le=999)
    video_action_prompt: str = Field(default="", max_length=600)
    video_return_to_first_frame: bool = False
    video_first_frame_only: bool = False
    video_model: VideoBridgeModel = "doubao-seedance-2-0-260128"
    video_duration_seconds: int | None = Field(default=None, ge=4, le=15)
    video_resolution: str | None = "480p"
    video_ratio: str | None = "1:1"

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy(cls, data: Any) -> Any:
        """兼容 1.46.x 之前的 iterative 老任务：把超出 mosaic 上限的字段 clamp 进合法范围。

        老任务通常是 rows=1, cols∈[9, 12]（逐帧任务的 frame_count 写到 cols 上）。
        这些任务已经跑完、结果文件都在 outputs，schema 只用于展示与重试。我们把
        cols clamp 到 8 让它能加载，并丢弃 generation_mode / 各种老抠色字段。
        """
        if not isinstance(data, dict):
            return data
        cleaned = {
            key: value
            for key, value in data.items()
            if key
            not in {
                "generation_mode",
                "key_mode",
                "key_tolerance",
                "key_softness",
                "key_alpha_floor",
                "key_despill",
            }
        }
        try:
            cols_val = int(cleaned.get("cols", 1) or 1)
            if cols_val > 8:
                cleaned["cols"] = 8
            rows_val = int(cleaned.get("rows", 1) or 1)
            if rows_val > 8:
                cleaned["rows"] = 8
        except (TypeError, ValueError):
            pass
        return cleaned

    @model_validator(mode="after")
    def _normalize(self) -> "SpriteParamsSchema":
        object.__setattr__(self, "frame_count", max(1, self.rows * self.cols))
        if len(self.row_prompts) > self.rows:
            object.__setattr__(self, "row_prompts", self.row_prompts[: self.rows])
        return self


class AssetParamsSchema(BaseModel):
    # 真实业务上限来自当前 Pix 配置（asset.subject_max_chars / extra_prompt_max_chars）；
    # 这里仅保留足够宽松的安全硬上限，避免在读取运行时配置前被 Pydantic 固定拦截。
    name: str = Field(default="", max_length=20000)
    extra_prompt: str = Field(default="", max_length=20000)
    asset_kind: Literal[
        "item_icon", "ui_component", "tile_texture", "game_logo", "dual_grid", "character"
    ] = "item_icon"
    subject_kind: Literal[
        "single_prop", "single_ui", "tileable_pattern", "logo_mark", "single_character"
    ] = "single_prop"
    texture_kind: Literal[
        "auto",
        "generic_texture",
        "terrain_ground",
        "path_floor",
        "wall_surface",
        "wood_planks",
        "water_liquid",
        "foliage_canopy",
        "roof_tile",
        "metal_panel",
        "fabric_carpet",
    ] = "auto"
    use_vl: bool | None = None
    no_preview: bool = False
    # dual_grid 专用：双瓦片两种材质 A/B 与过渡风格（material_b 为空串 = 透明模式）
    material_a: str = Field(default="", max_length=20000)
    material_b: str = Field(default="", max_length=20000)
    material_a_texture_kind: str = "auto"
    material_b_texture_kind: str = "auto"
    transition_style: Literal["rounded", "hard", "outline"] = "rounded"
    # 角色视图：three_view = 正/侧/背横向三视图拼合图（画布自动横向 3 倍宽）；single = 单张角色。
    # 默认三视图；仅在 asset_kind=character 时生效，其它类型会在归一时强制回落到 single。
    character_views: Literal["single", "three_view"] = "three_view"

    @model_validator(mode="after")
    def _normalize_subject_kind(self) -> "AssetParamsSchema":
        # 让 subject_kind 与 asset_kind 强一致：tile_texture / dual_grid → tileable_pattern；
        # ui_component → single_ui；game_logo → logo_mark；character → single_character；其它 → single_prop。
        if self.asset_kind == "tile_texture" and self.subject_kind != "tileable_pattern":
            object.__setattr__(self, "subject_kind", "tileable_pattern")
        elif self.asset_kind == "dual_grid" and self.subject_kind != "tileable_pattern":
            object.__setattr__(self, "subject_kind", "tileable_pattern")
        elif self.asset_kind == "ui_component" and self.subject_kind != "single_ui":
            object.__setattr__(self, "subject_kind", "single_ui")
        elif self.asset_kind == "game_logo" and self.subject_kind != "logo_mark":
            object.__setattr__(self, "subject_kind", "logo_mark")
        elif self.asset_kind == "character" and self.subject_kind != "single_character":
            object.__setattr__(self, "subject_kind", "single_character")
        elif self.asset_kind == "item_icon" and self.subject_kind not in {"single_prop"}:
            object.__setattr__(self, "subject_kind", "single_prop")
        # character_views 只对角色类型有意义；其它素材类型一律回落到 single，避免误带三视图标志。
        if self.asset_kind != "character" and self.character_views != "single":
            object.__setattr__(self, "character_views", "single")
        return self


class JobCreateRequest(BaseModel):
    job_type: JobType
    prompt: str | None = None
    input_image_path: str | None = None
    client_request_id: str = Field(default="", max_length=128)
    image_size: str | None = None
    image_quality: str | None = None
    image_model: str | None = None
    vl_model: str | None = None
    skip_vl: bool = False
    source_only: bool = False
    # 尺寸重试：开启后反复重新生成，直到透明成品尺寸匹配 pixelize.output_size 或达到上限；
    # 每次尝试按标准价 6 折计费（与全局折扣取更优）。stop_mode 二选一：
    #   attempts —— 用 size_retry_max_attempts 作为最大尝试次数停止条件
    #   credits  —— 用 size_retry_max_credits 作为最大点数预算（后端折算成次数）
    size_retry_enabled: bool = False
    size_retry_mode: Literal["attempts", "credits"] = "attempts"
    size_retry_max_attempts: int = Field(default=3, ge=1, le=SIZE_RETRY_MAX_ATTEMPTS_LIMIT)
    size_retry_max_credits: int = Field(default=0, ge=0, le=100000)
    pixelize: PixelizeParamsSchema = Field(default_factory=PixelizeParamsSchema)
    grid: GridDesignSchema = Field(default_factory=GridDesignSchema)
    style_profile: StyleProfileSchema = Field(default_factory=StyleProfileSchema)
    sprite: SpriteParamsSchema = Field(default_factory=SpriteParamsSchema)
    asset: AssetParamsSchema = Field(default_factory=AssetParamsSchema)


class JobBatchCreateRequest(BaseModel):
    jobs: list[JobCreateRequest] = Field(min_length=1, max_length=50)
    batch_name: str = Field(default="", max_length=160)
    mode: str = Field(default="mixed", max_length=32)


class JobBulkDeleteRequest(BaseModel):
    job_ids: list[int] = Field(min_length=1, max_length=200)

    @field_validator("job_ids")
    @classmethod
    def _normalize_job_ids(cls, value: list[int]) -> list[int]:
        normalized: list[int] = []
        seen: set[int] = set()
        for raw_id in value:
            job_id = int(raw_id)
            if job_id <= 0:
                raise ValueError("作品 ID 必须为正整数")
            if job_id in seen:
                continue
            seen.add(job_id)
            normalized.append(job_id)
        return normalized


class SequenceFrameAlignmentSchema(BaseModel):
    index: int = Field(ge=1, le=128)
    offset_x: int = Field(default=0, ge=-4096, le=4096)
    offset_y: int = Field(default=0, ge=-4096, le=4096)
    # 单帧主体缩放系数（绕帧中心缩放）。1.0 = 原图；0.25~4.0 之间。
    scale: float = Field(default=1.0, ge=0.25, le=4.0)


class SequenceAlignmentRequest(BaseModel):
    frames: list[SequenceFrameAlignmentSchema] = Field(min_length=1, max_length=128)
    fps: int | None = Field(default=None, ge=1, le=60)
    colors: int | None = Field(default=None, ge=2, le=256)
    gif_export: bool = True


class UploadResponse(BaseModel):
    path: str
    filename: str
    content_type: str
    size_bytes: int
    url: str | None = None


class CharacterCreateRequest(BaseModel):
    name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    image_path: str
    preview_path: str | None = None

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in value:
            tag = " ".join(str(raw or "").strip().split())[:40]
            key = tag.lower()
            if not tag or key in seen:
                continue
            seen.add(key)
            result.append(tag)
        return result


class CharacterFromJobRequest(BaseModel):
    name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    image_kind: Literal["source", "pixelized", "preview"] = "source"

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        return CharacterCreateRequest._normalize_tags(value)


class CharacterUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=20)
    status: Literal["active", "archived"] | None = None

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else CharacterCreateRequest._normalize_tags(value)


class CharacterResponse(BaseModel):
    id: int
    user_id: int
    source_job_id: int | None
    status: str
    name: str
    description: str = ""
    tags_json: list[Any] = Field(default_factory=list)
    image_path: str
    preview_path: str
    parameter_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def tags(self) -> list[str]:
        return [str(item) for item in self.tags_json if str(item).strip()]

    @computed_field
    @property
    def image_url(self) -> str | None:
        return file_url(self.image_path)

    @computed_field
    @property
    def preview_url(self) -> str | None:
        return file_url(self.preview_path or self.image_path)

    model_config = {"from_attributes": True}


class JobOutputResponse(BaseModel):
    run_dir: str
    source_path: str
    pixelized_path: str
    preview_path: str | None
    analysis_json_path: str | None
    meta_json_path: str

    @computed_field
    @property
    def pixelized_size(self) -> list[int] | None:
        return _image_pixel_size(self.pixelized_path) or _meta_pixelized_size(self.meta_json_path)

    @computed_field
    @property
    def grid_json_path(self) -> str | None:
        outputs = _load_meta_json(self.meta_json_path).get("outputs")
        if not isinstance(outputs, dict):
            return None
        grid_name = outputs.get("grid")
        if not grid_name:
            return None
        return str(Path(self.meta_json_path).with_name(str(grid_name)))

    @computed_field
    @property
    def grid_status(self) -> dict[str, Any] | None:
        grid = _grid_meta_from_output_meta(self.meta_json_path)
        if not grid or grid.get("mode") in (None, "off"):
            return None
        keys = ("mode", "readability", "ramp_info")
        return {key: grid[key] for key in keys if key in grid}

    @computed_field
    @property
    def grid_readability(self) -> dict[str, Any] | None:
        readability = _grid_meta_from_output_meta(self.meta_json_path).get("readability")
        return readability if isinstance(readability, dict) else None

    @computed_field
    @property
    def size_retry(self) -> dict[str, Any] | None:
        """尺寸重试结果（未启用时为 None）。供前端展示实际尝试次数与是否命中。"""
        meta = _size_retry_meta(self.meta_json_path)
        if not meta or not meta.get("enabled"):
            return None
        return meta

    @computed_field
    @property
    def contact_sheet_path(self) -> str | None:
        sheet = _contact_sheet_meta(self.meta_json_path).get("sheet")
        return _resolve_meta_relative_path(self.meta_json_path, str(sheet)) if sheet else None

    @computed_field
    @property
    def contact_sheet_url(self) -> str | None:
        return file_url(self.contact_sheet_path)

    @computed_field
    @property
    def candidates(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        contact_sheet = _contact_sheet_meta(self.meta_json_path)
        raw_candidates = contact_sheet.get("candidates")
        if isinstance(raw_candidates, list):
            for item in raw_candidates:
                if not isinstance(item, dict):
                    continue
                path = _resolve_meta_relative_path(self.meta_json_path, str(item.get("path") or ""))
                if not path:
                    continue
                pixelized_path = _resolve_meta_relative_path(
                    self.meta_json_path, str(item.get("pixelized_path") or "")
                )
                preview_path = _resolve_meta_relative_path(
                    self.meta_json_path, str(item.get("preview_path") or "")
                )
                result.append(
                    {
                        "candidate_kind": "contact_sheet",
                        "index": item.get("index"),
                        "row": item.get("row"),
                        "col": item.get("col"),
                        "path": path,
                        "url": file_url(path),
                        "bbox": item.get("bbox"),
                        "score": item.get("score"),
                        "rank": item.get("rank"),
                        "reason": item.get("reason"),
                        "selected": bool(item.get("selected")),
                        "pixelized_path": pixelized_path,
                        "pixelized_url": file_url(pixelized_path),
                        "preview_path": preview_path,
                        "preview_url": file_url(preview_path),
                    }
                )

        # 尺寸重试不是 contact sheet，但交互上同样是一组可选结果；复用 candidates 字段。
        # 前端对尺寸重试尝试做纯展示切换（预览/下载），普通 contact sheet 候选才进入本地像素化。
        size_retry = _size_retry_meta(self.meta_json_path)
        raw_attempts = size_retry.get("attempts")
        if isinstance(raw_attempts, list):
            for item in raw_attempts:
                if not isinstance(item, dict):
                    continue
                path_value = item.get("path") or item.get("pixelized_path") or item.get("source_path")
                path = _resolve_meta_relative_path(self.meta_json_path, str(path_value or ""))
                if not path:
                    continue
                pixelized_path = _resolve_meta_relative_path(
                    self.meta_json_path, str(item.get("pixelized_path") or path_value or "")
                )
                preview_path = _resolve_meta_relative_path(
                    self.meta_json_path, str(item.get("preview_path") or "")
                )
                source_path = _resolve_meta_relative_path(
                    self.meta_json_path, str(item.get("source_path") or "")
                )
                final_size = _as_size_pair(item.get("final_size") or item.get("actual_size"))
                target_size = _as_size_pair(item.get("target_size") or item.get("expected_size"))
                attempt = item.get("attempt") or item.get("index")
                result.append(
                    {
                        "candidate_kind": "size_retry_attempt",
                        "index": attempt,
                        "attempt": attempt,
                        "row": 0,
                        "col": max(0, int(attempt or 1) - 1),
                        "path": pixelized_path or path,
                        "url": file_url(pixelized_path or path),
                        "source_path": source_path,
                        "source_url": file_url(source_path),
                        "bbox": None,
                        "score": 1.0 if bool(item.get("matched")) else None,
                        "rank": attempt,
                        "reason": item.get("reason"),
                        "selected": bool(item.get("selected")),
                        "matched": bool(item.get("matched")),
                        "final_size": final_size,
                        "target_size": target_size,
                        "pixelized_path": pixelized_path or path,
                        "pixelized_url": file_url(pixelized_path or path),
                        "preview_path": preview_path,
                        "preview_url": file_url(preview_path),
                        "meta_json_path": _resolve_meta_relative_path(
                            self.meta_json_path, str(item.get("meta_json_path") or "")
                        ),
                    }
                )
        return result

    @computed_field
    @property
    def sprite_sheet_path(self) -> str | None:
        outputs = _outputs_meta(self.meta_json_path)
        sheet = outputs.get("sprite_sheet") or _sprite_meta(self.meta_json_path).get(
            "horizontal_sheet"
        )
        return _resolve_meta_relative_path(self.meta_json_path, str(sheet)) if sheet else None

    @computed_field
    @property
    def sprite_sheet_url(self) -> str | None:
        return file_url(self.sprite_sheet_path)

    @computed_field
    @property
    def sprite_mosaic_path(self) -> str | None:
        outputs = _outputs_meta(self.meta_json_path)
        mosaic = outputs.get("sprite_mosaic") or _sprite_meta(self.meta_json_path).get(
            "mosaic_sheet"
        )
        return _resolve_meta_relative_path(self.meta_json_path, str(mosaic)) if mosaic else None

    @computed_field
    @property
    def sprite_mosaic_url(self) -> str | None:
        return file_url(self.sprite_mosaic_path)

    @computed_field
    @property
    def dual_grid_atlas_path(self) -> str | None:
        atlas = _outputs_meta(self.meta_json_path).get("dual_grid_atlas")
        return _resolve_meta_relative_path(self.meta_json_path, str(atlas)) if atlas else None

    @computed_field
    @property
    def dual_grid_atlas_url(self) -> str | None:
        return file_url(self.dual_grid_atlas_path)

    @computed_field
    @property
    def dual_grid_preview_path(self) -> str | None:
        preview = _outputs_meta(self.meta_json_path).get("dual_grid_preview")
        return _resolve_meta_relative_path(self.meta_json_path, str(preview)) if preview else None

    @computed_field
    @property
    def dual_grid_preview_url(self) -> str | None:
        return file_url(self.dual_grid_preview_path)

    @computed_field
    @property
    def sprite_sheet_grid_path(self) -> str | None:
        outputs = _outputs_meta(self.meta_json_path)
        grid = outputs.get("sprite_sheet_grid") or _sprite_meta(self.meta_json_path).get(
            "grid_sheet"
        )
        return _resolve_meta_relative_path(self.meta_json_path, str(grid)) if grid else None

    @computed_field
    @property
    def sprite_sheet_grid_url(self) -> str | None:
        return file_url(self.sprite_sheet_grid_path)

    @computed_field
    @property
    def sprite_rows_outputs(self) -> list[dict[str, Any]]:
        """每行独立动画的产物：sheet + gif，前端可直接消费。"""
        sprite = _sprite_meta(self.meta_json_path)
        rows_outputs = sprite.get("rows_outputs")
        if not isinstance(rows_outputs, list):
            return []
        items: list[dict[str, Any]] = []
        for entry in rows_outputs:
            if not isinstance(entry, dict):
                continue
            sheet_value = entry.get("sheet")
            gif_value = entry.get("gif")
            sheet_path = (
                _resolve_meta_relative_path(self.meta_json_path, str(sheet_value))
                if sheet_value
                else None
            )
            gif_path = (
                _resolve_meta_relative_path(self.meta_json_path, str(gif_value))
                if gif_value
                else None
            )
            items.append(
                {
                    "row_index": entry.get("row_index"),
                    "frame_indices": entry.get("frame_indices") or [],
                    "action_phase": entry.get("action_phase") or "",
                    "sheet_path": sheet_path,
                    "sheet_url": file_url(sheet_path),
                    "gif_path": gif_path,
                    "gif_url": file_url(gif_path),
                }
            )
        return items

    @computed_field
    @property
    def sprite_grid(self) -> dict[str, int] | None:
        sprite = _sprite_meta(self.meta_json_path)
        if not sprite:
            return None
        rows = sprite.get("rows")
        cols = sprite.get("cols")
        try:
            rows_int = int(rows) if rows is not None else None
            cols_int = int(cols) if cols is not None else None
        except (TypeError, ValueError):
            return None
        if rows_int and cols_int:
            return {"rows": rows_int, "cols": cols_int}
        return None

    @computed_field
    @property
    def sprite_gif_path(self) -> str | None:
        outputs = _outputs_meta(self.meta_json_path)
        gif = outputs.get("sprite_gif") or _sprite_meta(self.meta_json_path).get("gif")
        return _resolve_meta_relative_path(self.meta_json_path, str(gif)) if gif else None

    @computed_field
    @property
    def sprite_gif_url(self) -> str | None:
        return file_url(self.sprite_gif_path)

    @computed_field
    @property
    def sequence_json_path(self) -> str | None:
        outputs = _outputs_meta(self.meta_json_path)
        sequence = outputs.get("sequence_json") or _sprite_meta(self.meta_json_path).get(
            "sequence_json"
        )
        return _resolve_meta_relative_path(self.meta_json_path, str(sequence)) if sequence else None

    @computed_field
    @property
    def sequence_json_url(self) -> str | None:
        return file_url(self.sequence_json_path)

    @computed_field
    @property
    def sprite_frames(self) -> list[dict[str, Any]]:
        raw_frames = _sprite_meta(self.meta_json_path).get("frames")
        if not isinstance(raw_frames, list):
            return []
        frames: list[dict[str, Any]] = []
        for item in raw_frames:
            if not isinstance(item, dict):
                continue
            path = _resolve_meta_relative_path(self.meta_json_path, str(item.get("path") or ""))
            raw_path = _resolve_meta_relative_path(
                self.meta_json_path, str(item.get("raw_path") or "")
            )
            reference_path = _resolve_meta_relative_path(
                self.meta_json_path, str(item.get("reference_path") or "")
            )
            if not path:
                continue
            frames.append(
                {
                    "index": item.get("index"),
                    "row": item.get("row"),
                    "col": item.get("col"),
                    "path": path,
                    "url": file_url(path),
                    "raw_path": raw_path,
                    "raw_url": file_url(raw_path),
                    "reference_path": reference_path,
                    "reference_url": file_url(reference_path),
                    "sheet_rect": item.get("sheet_rect"),
                    "action_phase": item.get("action_phase"),
                    "bbox": item.get("bbox"),
                }
            )
        return frames

    @computed_field
    @property
    def source_url(self) -> str | None:
        return file_url(self.source_path)

    @computed_field
    @property
    def pixelized_url(self) -> str | None:
        return file_url(self.pixelized_path)

    @computed_field
    @property
    def preview_url(self) -> str | None:
        return file_url(self.preview_path)

    model_config = {"from_attributes": True}


class JobShareSummary(BaseModel):
    id: int
    status: str
    like_count: int = 0
    download_count: int = 0
    reward_credits: int = 0
    review_note: str = ""
    reviewed_at: datetime | None = None
    published_at: datetime | None = None


class SharedDownloadOptionResponse(BaseModel):
    kind: str
    label: str
    description: str = ""
    url: str
    filename: str


class SharedWorkResponse(BaseModel):
    id: int
    job_id: int | None
    user_id: int
    status: str
    title: str
    asset_kind: str
    preview_url: str
    actual_size: tuple[int, int] | None = None
    sprite_sheet_url: str | None = None
    sprite_frames: list[dict[str, Any]] = Field(default_factory=list)
    sprite_fps: int | None = None
    parameter_snapshot: dict[str, Any] = Field(default_factory=dict)
    download_options: list[SharedDownloadOptionResponse] = Field(default_factory=list)
    like_count: int = 0
    download_count: int = 0
    reward_credits: int = 0
    liked_by_me: bool = False
    owned_by_me: bool = False
    review_note: str = ""
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SharedWorkFilterOptionResponse(BaseModel):
    value: str
    count: int


class SharedWorkFiltersResponse(BaseModel):
    asset_kinds: list[SharedWorkFilterOptionResponse] = Field(default_factory=list)
    output_sizes: list[SharedWorkFilterOptionResponse] = Field(default_factory=list)
    image_models: list[SharedWorkFilterOptionResponse] = Field(default_factory=list)


class SharedWorkListResponse(BaseModel):
    items: list[SharedWorkResponse]
    total: int
    limit: int
    offset: int
    filters: SharedWorkFiltersResponse = Field(default_factory=SharedWorkFiltersResponse)


class AdminSharedWorkResponse(BaseModel):
    """管理员审核视角的分享作品（含作者信息、审核字段）。"""

    id: int
    job_id: int | None
    user_id: int
    user_email: str = ""
    status: str
    title: str
    asset_kind: str
    preview_url: str
    parameter_snapshot: dict[str, Any] = Field(default_factory=dict)
    like_count: int = 0
    download_count: int = 0
    reward_credits: int = 0
    review_note: str = ""
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminSharedWorkListResponse(BaseModel):
    items: list[AdminSharedWorkResponse]
    total: int
    limit: int
    offset: int


class ShareRejectRequest(BaseModel):
    note: str = Field(default="", max_length=500)


class JobResponse(BaseModel):
    id: int
    user_id: int
    batch_id: int | None
    job_type: str
    status: str
    prompt: str | None
    input_image_path: str | None

    @computed_field
    @property
    def input_image_url(self) -> str | None:
        return file_url(self.input_image_path)

    @computed_field
    @property
    def sprite_reference_image_url(self) -> str | None:
        sprite = self.params_json.get("sprite") if isinstance(self.params_json, dict) else None
        if not isinstance(sprite, dict):
            return None
        value = sprite.get("reference_image_path")
        return file_url(str(value)) if value else None

    @computed_field
    @property
    def batch_name(self) -> str | None:
        batch = getattr(self, "batch", None)
        return getattr(batch, "name", None)

    params_json: dict[str, Any]
    price_credits: int
    reserved_credits: int
    error_message: str
    failure_type: str = ""
    failure_source: str = ""
    failure_code: str = ""
    candidate_failure_count: int = 0
    pipeline_warning_count: int = 0
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    outputs: list[JobOutputResponse] = []
    share: JobShareSummary | None = None

    model_config = {"from_attributes": True}


class AdminJobResponse(JobResponse):
    user_error_message: str = ""
    error_diagnostics_json: dict[str, Any] = Field(default_factory=dict)


def safe_user_job_error(job: Any) -> str:
    if getattr(job, "status", "") != "failed":
        return ""
    user_message = str(getattr(job, "user_error_message", "") or "").strip()
    if user_message:
        return user_message
    failure_type = str(getattr(job, "failure_type", "") or "")
    if failure_type == "policy_blocked":
        return "素材描述未通过安全检查，请调整描述后重试。"
    return "生成服务暂时不可用，系统已自动退款。请稍后重试。"


def public_job_response(job: Any) -> dict[str, Any]:
    data = JobResponse.model_validate(job).model_dump(mode="python")
    data["error_message"] = safe_user_job_error(job)
    shared = getattr(job, "shared_work", None)
    # deleted 状态的分享视为无分享，避免作品库残留失效状态。
    if shared is not None and getattr(shared, "status", None) == "deleted":
        shared = None
    data["share"] = None if shared is None else {
        "id": shared.id,
        "status": shared.status,
        "like_count": shared.like_count,
        "download_count": shared.download_count,
        "reward_credits": shared.reward_credits,
        "review_note": shared.review_note or "",
        "reviewed_at": shared.reviewed_at,
        "published_at": shared.published_at,
    }
    return data


class JobBatchCreateResponse(BaseModel):
    jobs: list[JobResponse]
    total_price_credits: int
    batch_id: int | None = None


class JobBulkDeleteResponse(BaseModel):
    deleted: bool = True
    deleted_count: int
    job_ids: list[int]


class GenerationBatchResponse(BaseModel):
    id: int
    name: str
    mode: str
    status: str
    created_at: datetime
    updated_at: datetime
    job_count: int
    succeeded_count: int
    failed_count: int
    running_count: int
    pending_count: int
    total_price_credits: int


class BatchUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    status: str | None = Field(default=None, max_length=32)


class AssetPackCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class AssetPackUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    status: str | None = Field(default=None, max_length=32)


class AssetPackAddItemRequest(BaseModel):
    job_id: int


class AssetPackResponse(BaseModel):
    id: int
    name: str
    status: str
    capacity: int
    item_count: int
    remaining_capacity: int
    created_at: datetime
    updated_at: datetime


class AssetPackQuotaResponse(BaseModel):
    pack_count: int
    pack_limit: int
    remaining_packs: int
    expand_price_credits: int
    pack_capacity: int


class GalleryQuotaResponse(BaseModel):
    retained_count: int
    retained_limit: int
    remaining_slots: int
    expand_price_credits: int
    expand_slots: int


class AdminAdjustCreditsRequest(BaseModel):
    amount: int
    note: str = ""


class AdminBatchAdjustCreditsRequest(BaseModel):
    user_ids: list[int] = Field(default_factory=list)
    all_users: bool = False
    amount: int
    note: str = ""

    @model_validator(mode="after")
    def validate_target(self) -> "AdminBatchAdjustCreditsRequest":
        if self.amount == 0:
            raise ValueError("点数变化不能为 0")
        if not self.all_users and not self.user_ids:
            raise ValueError("请选择至少一个用户，或启用 all_users")
        return self


class AdminBatchAdjustCreditsResponse(BaseModel):
    adjusted_count: int
    amount: int
    note: str
    all_users: bool = False
    transactions: list[CreditTransactionResponse] = Field(default_factory=list)


class PricingRuleResponse(BaseModel):
    key: str
    price_credits: int
    enabled: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingRuleUpdateRequest(BaseModel):
    price_credits: int = Field(ge=0)
    enabled: bool = True


class PricingDiscountResponse(BaseModel):
    active: bool
    rate: float
    label: str = ""


class SystemSettingResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime | None
    label: str = ""
    category: str = ""
    type: str = "string"
    help: str = ""
    options: list[str] = Field(default_factory=list)
    secret: bool = False
    masked: bool = False
    restart_required: bool = False
    editable: bool = True
    env_var: str = ""
    source: str = "database"

    model_config = {"from_attributes": True}


class SystemSettingUpdateRequest(BaseModel):
    value: str | None = Field(default=None, max_length=4000)
    clear: bool = False


class AnnouncementResponse(BaseModel):
    enabled: bool
    title: str = ""
    body: str = ""
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AnnouncementPublishRequest(BaseModel):
    title: str = Field(default="", max_length=80)
    body: str = Field(default="", max_length=1200)
    enabled: bool = True


class AnnouncementPublishResponse(AnnouncementResponse):
    email_notification_queued: bool = False
    email_recipient_count: int = 0
    email_skipped_reason: str = ""


class AnnouncementItemResponse(BaseModel):
    id: int
    title: str
    body: str
    enabled: bool
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementItemResponse]
    active_count: int


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(default="", max_length=80)
    body: str = Field(default="", max_length=2000)
    enabled: bool = True
    publish_now: bool = False
    notify: bool = True


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    body: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None


class AnnouncementTestEmailRequest(BaseModel):
    email: EmailStr
    title: str = Field(default="", max_length=80)
    body: str = Field(default="", max_length=2000)


class EmailTestRequest(BaseModel):
    email: EmailStr


class EmailTestResponse(BaseModel):
    ok: bool = True
    message: str
    debug_code: str | None = None


class CreditPackageResponse(BaseModel):
    key: str
    name: str
    credits: int
    amount_cents: int
    currency: str
    enabled: bool
    sort_order: int = 0

    model_config = {"from_attributes": True}


class CreditPackageCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    credits: int = Field(ge=1)
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="cny", max_length=12)
    enabled: bool = True
    sort_order: int = 0


class CreditPackageUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    credits: int = Field(ge=1)
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="cny", max_length=12)
    enabled: bool = True
    sort_order: int = 0


class PaymentRequestBase(BaseModel):
    package_key: str | None = Field(default=None, max_length=64)
    custom_credits: int | None = Field(default=None, ge=10, le=100000)

    @model_validator(mode="after")
    def validate_single_recharge_source(self):
        has_package = bool((self.package_key or "").strip())
        has_custom = self.custom_credits is not None
        if has_package == has_custom:
            raise ValueError("package_key 与 custom_credits 必须二选一")
        if self.package_key is not None:
            self.package_key = self.package_key.strip() or None
        return self


class PaymentOrderCreateRequest(PaymentRequestBase):
    provider: str = Field(default="mock", max_length=32)


class PaymentCheckoutRequest(PaymentRequestBase):
    provider: str = Field(default="mock", max_length=32)


class PaymentOrderResponse(BaseModel):
    id: int
    provider: str
    provider_order_id: str
    status: str
    amount_cents: int
    currency: str
    credits: int
    created_at: datetime
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class PaymentCheckoutResponse(BaseModel):
    order: PaymentOrderResponse
    provider: str
    payment_url: str | None = None
    code_url: str | None = None


class CustomRechargeOptionsResponse(BaseModel):
    min_credits: int
    max_credits: int
    currency: str
    unit_amount_cents_per_credit: float
    base_package_key: str | None = None
    base_package_credits: int
    base_package_amount_cents: int
    suggested_credits: list[int]


class MockWebhookRequest(BaseModel):
    order_id: int
    event_id: str = Field(max_length=160)


class AdminDashboardResponse(BaseModel):
    total_users: int
    new_users_today: int = 0
    active_users_today: int = 0
    paying_users_today: int = 0
    jobs_today: int
    succeeded_today: int
    failed_today: int
    policy_blocked_today: int = 0
    upstream_errors_today: int = 0
    timeout_jobs_today: int = 0
    pipeline_errors_today: int = 0
    pending_jobs: int
    running_jobs: int
    running_over_30m_jobs: int = 0
    candidate_failures_today: int = 0
    pipeline_warnings_today: int = 0
    average_generation_seconds_today: float = 0.0
    p95_generation_seconds_today: float = 0.0
    credits_consumed_today: int
    credits_recharged_today: int
    orders_created_today: int = 0
    orders_paid_today: int
    uploads_today: int
    failure_rate: float


class PerfKpi(BaseModel):
    success_rate: float = 0.0
    running: int = 0
    total: int = 0
    failed: int = 0
    avg_seconds: float = 0.0
    p95_seconds: float = 0.0


class PerfSeriesPoint(BaseModel):
    t: str
    succeeded: int = 0
    failed: int = 0
    total: int = 0


class PerfProvider(BaseModel):
    provider: str
    display_name: str = ""
    enabled: bool = False
    priority: int = 100
    succeeded: int = 0
    failed: int = 0
    total: int = 0
    success_rate: float = 0.0


class PerfFailure(BaseModel):
    code: str
    count: int = 0


class PerfRecentJob(BaseModel):
    id: int
    job_type: str
    status: str
    provider: str = ""
    provider_display_name: str = ""
    failure_code: str = ""
    seconds: float = 0.0
    created_at: str


class PerformanceMetricsResponse(BaseModel):
    range: str
    bucket_seconds: int
    generated_at: str
    kpi: PerfKpi
    series: list[PerfSeriesPoint]
    providers: list[PerfProvider]
    failures: list[PerfFailure]
    recent: list[PerfRecentJob]


class ImageProviderModelPayload(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    provider_model: str = ""
    label: str = ""
    protocol: str = "openai_images"
    operations: list[str] = Field(default_factory=lambda: ["text_to_image", "image_to_image"])
    sizes: list[str] = Field(default_factory=list)
    qualities: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=list)
    edit_mode: str = "multipart"


class ImageProviderCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(default="", max_length=128)
    enabled: bool = True
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = Field(default="", max_length=96)
    priority: int = 100
    discover_models: bool = False
    protocols: list[str] = Field(default_factory=lambda: ["openai_images"])
    models: list[ImageProviderModelPayload] = Field(default_factory=list)
    preset_key: str | None = None


class ImageProviderUpdateRequest(BaseModel):
    display_name: str = ""
    enabled: bool = True
    base_url: str = ""
    api_key: str = ""  # 空=保留原值（写入式更新）
    clear_api_key: bool = False
    api_key_env: str = Field(default="", max_length=96)
    priority: int = 100
    discover_models: bool = False
    protocols: list[str] = Field(default_factory=lambda: ["openai_images"])
    models: list[ImageProviderModelPayload] = Field(default_factory=list)


class ImageProviderResponse(BaseModel):
    id: str
    display_name: str
    enabled: bool
    base_url: str
    has_api_key: bool
    api_key_env: str
    priority: int
    discover_models: bool
    protocols: list[str]
    models: list[ImageProviderModelPayload]
    preset_key: str | None = None


class ImageProviderPresetResponse(BaseModel):
    key: str
    display_name: str
    protocols: list[str]
    base_url: str
    api_key_env: str
    discover_models: bool
    models: list[ImageProviderModelPayload]
    note: str = ""
