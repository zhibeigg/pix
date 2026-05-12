"""Web API Pydantic schema。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, computed_field

from pix_web.storage import file_url

JobType = Literal["text_to_image", "image_to_image", "local_pixelize", "repixelize"]


def _load_meta_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


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


def _resolve_meta_relative_path(meta_json_path: str | None, value: str | None) -> str | None:
    if not meta_json_path or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(Path(meta_json_path).with_name(value) if "/" not in value and "\\" not in value else Path(meta_json_path).parent / value)


JobStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class EmailCodeRequest(BaseModel):
    email: EmailStr


class EmailCodeResponse(BaseModel):
    ok: bool = True
    retry_after_seconds: int
    expires_in_seconds: int
    debug_code: str | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)
    verification_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


class CreditTransactionResponse(BaseModel):
    id: int
    type: str
    amount: int
    balance_after: int
    job_id: int | None
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
    edge_style: str = "hard"
    auto_crop: bool = False
    crop_padding: float = Field(default=0.12, ge=0.0, le=1.0)
    crop_square: bool = True


class GridDesignSchema(BaseModel):
    mode: Literal["off", "extract", "ai"] = "off"
    review: bool = False
    retries: int = Field(default=1, ge=0, le=3)
    instruction: str = Field(default="", max_length=800)
    fallback: Literal["extract", "pixelize", "fail"] = "extract"


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
    pixelize: PixelizeParamsSchema = Field(default_factory=PixelizeParamsSchema)
    grid: GridDesignSchema = Field(default_factory=GridDesignSchema)


class JobBatchCreateRequest(BaseModel):
    jobs: list[JobCreateRequest] = Field(min_length=1, max_length=50)
    batch_name: str = Field(default="", max_length=160)
    mode: str = Field(default="mixed", max_length=32)


class UploadResponse(BaseModel):
    path: str
    filename: str
    content_type: str
    size_bytes: int
    url: str | None = None


class JobOutputResponse(BaseModel):
    run_dir: str
    source_path: str
    pixelized_path: str
    preview_path: str | None
    analysis_json_path: str | None
    meta_json_path: str

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
        keys = (
            "mode",
            "review",
            "fallback",
            "used_fallback",
            "fallback_reason",
            "failed",
            "error",
            "attempts",
            "max_attempts",
            "repaired",
            "source_prompt_used",
            "draft",
        )
        return {key: grid[key] for key in keys if key in grid}

    @computed_field
    @property
    def grid_readability(self) -> dict[str, Any] | None:
        readability = _grid_meta_from_output_meta(self.meta_json_path).get("readability")
        return readability if isinstance(readability, dict) else None

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
        contact_sheet = _contact_sheet_meta(self.meta_json_path)
        raw_candidates = contact_sheet.get("candidates")
        if not isinstance(raw_candidates, list):
            return []
        result: list[dict[str, Any]] = []
        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            path = _resolve_meta_relative_path(self.meta_json_path, str(item.get("path") or ""))
            if not path:
                continue
            result.append({
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
            })
        return result

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


class JobResponse(BaseModel):
    id: int
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
    def batch_name(self) -> str | None:
        batch = getattr(self, "batch", None)
        return getattr(batch, "name", None)

    params_json: dict[str, Any]
    price_credits: int
    reserved_credits: int
    error_message: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    outputs: list[JobOutputResponse] = []

    model_config = {"from_attributes": True}


class JobBatchCreateResponse(BaseModel):
    jobs: list[JobResponse]
    total_price_credits: int
    batch_id: int | None = None


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


class AdminAdjustCreditsRequest(BaseModel):
    amount: int
    note: str = ""


class PricingRuleResponse(BaseModel):
    key: str
    price_credits: int
    enabled: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingRuleUpdateRequest(BaseModel):
    price_credits: int = Field(ge=0)
    enabled: bool = True


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


class PaymentOrderCreateRequest(BaseModel):
    package_key: str = Field(max_length=64)


class PaymentCheckoutRequest(BaseModel):
    package_key: str = Field(max_length=64)
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


class MockWebhookRequest(BaseModel):
    order_id: int
    event_id: str = Field(max_length=160)


class AdminDashboardResponse(BaseModel):
    total_users: int
    jobs_today: int
    succeeded_today: int
    failed_today: int
    pending_jobs: int
    running_jobs: int
    credits_consumed_today: int
    credits_recharged_today: int
    orders_paid_today: int
    uploads_today: int
    failure_rate: float
