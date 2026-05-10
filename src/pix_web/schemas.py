"""Web API Pydantic schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

JobType = Literal["text_to_image", "image_to_image", "local_pixelize", "repixelize"]
JobStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


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


class UploadResponse(BaseModel):
    path: str
    filename: str
    content_type: str
    size_bytes: int


class JobOutputResponse(BaseModel):
    run_dir: str
    source_path: str
    pixelized_path: str
    preview_path: str | None
    analysis_json_path: str | None
    meta_json_path: str

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: int
    job_type: str
    status: str
    prompt: str | None
    input_image_path: str | None
    params_json: dict[str, Any]
    price_credits: int
    reserved_credits: int
    error_message: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    outputs: list[JobOutputResponse] = []

    model_config = {"from_attributes": True}


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
