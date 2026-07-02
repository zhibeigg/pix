"""任务创建与状态机。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix.api.prompt_guard import RAW_IMAGE_PROMPT_MAX_CHARS
from pix.asset import AssetSizePolicyError, resolve_asset_generation_policy
from pix.config import AppConfig, load_config
from pix.prompt_style import STYLE_PROFILE_POLICY_MAX_CHARS, style_profile_policy_text
from pix.sprite_video_bridge import derive_video_bridge_duration_seconds
from pix_web.config import WebSettings, load_web_settings
from pix_web.credits import InsufficientCreditsError, insufficient_credits_http, reserve_credits
from pix_web.file_ownership import resolve_owned_input_path
from pix_web.job_observability import record_policy_event
from pix_web.models import CreditAccount, GenerationBatch, GenerationJob, User
from pix_web.pricing import (
    VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS,
    VIDEO_BRIDGE_IMAGE_PRICE_CREDITS,
    VIDEO_BRIDGE_MODEL_PRICE_CNY,
    VIDEO_BRIDGE_PRICE_MULTIPLIER,
    PricingDisabledError,
    apply_discount,
    get_price,
    normalize_video_bridge_model,
    video_bridge_price_credits,
    video_bridge_price_key,
)
from pix_web.schemas import JobCreateRequest, PixelizeParamsSchema, SpriteParamsSchema
from pix_web.system_settings import (
    PricingDiscount,
    enforce_generation_limits,
    enforce_prompt_policy,
    load_managed_pix_config,
    load_pricing_discount,
    managed_pix_overrides_from_db,
)

AI_JOB_TYPES = {"asset", "text_to_image", "image_to_image", "sprite_sheet"}
IMAGE_JOB_TYPES = {"image_to_image", "local_pixelize", "local_bg_remove", "repixelize"}


def _positive_limit(value: object, fallback: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def _effective_pix_config(db: Session, settings: WebSettings | None = None) -> AppConfig:
    if settings is not None:
        return load_managed_pix_config(db, settings)
    return load_config(overrides=managed_pix_overrides_from_db(db))


def _raw_image_prompt_limit(cfg: AppConfig | None) -> int:
    if cfg is None:
        return RAW_IMAGE_PROMPT_MAX_CHARS
    return _positive_limit(cfg.image_gen.prompt_guard_max_chars, RAW_IMAGE_PROMPT_MAX_CHARS)


def _asset_subject_limit(cfg: AppConfig) -> int:
    return _positive_limit(cfg.asset.subject_max_chars, 160)


def _asset_extra_prompt_limit(cfg: AppConfig) -> int:
    return _positive_limit(cfg.asset.extra_prompt_max_chars, RAW_IMAGE_PROMPT_MAX_CHARS)


def _sprite_subject_limit(cfg: AppConfig) -> int:
    return _positive_limit(cfg.sprite.subject_max_chars, RAW_IMAGE_PROMPT_MAX_CHARS)


def _sprite_row_prompt_limit(cfg: AppConfig) -> int:
    return _positive_limit(cfg.sprite.row_prompt_max_chars, 600)


def _dedupe_prompt_parts(parts: list[str | None]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for part in parts:
        clean = (part or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def _enforce_text_max_chars(label: str, value: str | None, max_chars: int) -> None:
    text = (value or "").strip()
    if len(text) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label}最多支持 {max_chars} 字",
        )


def _asset_name(req: JobCreateRequest) -> str:
    return (req.asset.name or req.prompt or "").strip()


def _job_prompt_for_record(req: JobCreateRequest) -> str | None:
    if req.job_type == "asset":
        return _asset_name(req) or None
    return (req.prompt or "").strip() or None


def _prompt_policy_text(req: JobCreateRequest) -> str | None:
    style_text = style_profile_policy_text(req.style_profile)
    if req.job_type == "asset":
        parts = _dedupe_prompt_parts([
            req.asset.name,
            req.asset.extra_prompt,
            req.prompt or "",
            req.asset.material_a,
            req.asset.material_b,
            style_text,
        ])
        return "\n".join(parts) or None
    if req.job_type == "sprite_sheet":
        parts = _dedupe_prompt_parts([req.prompt or "", *req.sprite.row_prompts, req.sprite.video_action_prompt, style_text])
        return "\n".join(parts) or None
    if req.job_type in {"text_to_image", "image_to_image"}:
        parts = _dedupe_prompt_parts([req.prompt or "", style_text])
        return "\n".join(parts) or None
    return req.prompt


def _prompt_policy_max_chars(req: JobCreateRequest, cfg: AppConfig) -> int | None:
    if req.job_type == "asset":
        return (_asset_subject_limit(cfg) * 4) + _asset_extra_prompt_limit(cfg) + STYLE_PROFILE_POLICY_MAX_CHARS
    if req.job_type == "sprite_sheet":
        rows = max(1, min(8, req.sprite.rows))
        return _sprite_subject_limit(cfg) + (_sprite_row_prompt_limit(cfg) * (rows + 1)) + STYLE_PROFILE_POLICY_MAX_CHARS
    if req.job_type in AI_JOB_TYPES:
        return _raw_image_prompt_limit(cfg) + STYLE_PROFILE_POLICY_MAX_CHARS
    return None


def _enforce_request_prompt_policy(db: Session, user: User, req: JobCreateRequest, cfg: AppConfig) -> None:
    prompt_text = _prompt_policy_text(req)
    try:
        enforce_prompt_policy(
            db,
            prompt_text,
            allow_template_break=req.source_only or req.job_type == "sprite_sheet",
            max_chars=_prompt_policy_max_chars(req, cfg),
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            try:
                record_policy_event(
                    db,
                    user_id=user.id,
                    job_type=req.job_type,
                    reason=str(exc.detail),
                    prompt=prompt_text,
                    source="pre_create",
                )
                db.commit()
            except Exception:  # noqa: BLE001 - 审计失败不能吞掉原始策略错误
                db.rollback()
        raise


def validate_job_request(req: JobCreateRequest, cfg: AppConfig | None = None) -> None:
    prompt = (req.prompt or "").strip()
    if cfg is not None:
        if req.job_type == "asset":
            subject_limit = _asset_subject_limit(cfg)
            extra_prompt_limit = _asset_extra_prompt_limit(cfg)
            _enforce_text_max_chars("素材主体", _asset_name(req), subject_limit)
            _enforce_text_max_chars("额外风格描述", req.asset.extra_prompt, extra_prompt_limit)
            if req.asset.asset_kind == "dual_grid":
                _enforce_text_max_chars("材质 A 描述", req.asset.material_a, subject_limit)
                _enforce_text_max_chars("材质 B 描述", req.asset.material_b, subject_limit)
        elif req.job_type == "sprite_sheet":
            _enforce_text_max_chars("序列帧主体描述", prompt, _sprite_subject_limit(cfg))
            row_limit = _sprite_row_prompt_limit(cfg)
            for index, row_prompt in enumerate(req.sprite.row_prompts, start=1):
                _enforce_text_max_chars(f"第 {index} 行动作描述", row_prompt, row_limit)
            _enforce_text_max_chars("视频补间动作描述", req.sprite.video_action_prompt, row_limit)
        elif req.job_type in {"text_to_image", "image_to_image"}:
            _enforce_text_max_chars("原始生图 prompt", prompt, _raw_image_prompt_limit(cfg))
    try:
        resolve_asset_generation_policy(tuple(req.pixelize.output_size))
    except AssetSizePolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if req.job_type == "asset" and not _asset_name(req):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材直出任务需要主体内容"
        )
    if req.job_type == "asset" and req.input_image_path and not Path(req.input_image_path).exists():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参考图不存在")
    if req.job_type == "text_to_image" and not prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文生图任务需要 prompt"
        )
    raw_prompt_limit = _raw_image_prompt_limit(cfg)
    if (
        req.job_type == "text_to_image"
        and req.source_only
        and len(prompt) > raw_prompt_limit
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"原生生图 prompt 最多支持 {raw_prompt_limit} 字",
        )
    if req.job_type == "image_to_image" and not prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="图生图任务需要 prompt"
        )
    if req.job_type == "sprite_sheet" and not prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧任务需要 prompt"
        )
    if req.job_type == "sprite_sheet":
        sprite = req.sprite
        if sprite.rows < 1 or sprite.rows > 8 or sprite.cols < 1 or sprite.cols > 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧每行/每列最多支持 8"
            )
        total_frames = sprite.rows * sprite.cols
        if total_frames < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="序列帧网格至少需要 1 个单元",
            )
        if sprite.mode == "video_bridge":
            if total_frames < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="首尾帧视频补间至少需要 2 帧",
                )
            if cfg is not None:
                if not getattr(cfg.video_bridge, "enabled", False):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="首尾帧视频补间未启用，请先在后台启用 video_bridge",
                    )
                if not (getattr(cfg.video_bridge, "api_key", None) or "").strip():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="首尾帧视频补间需要配置 Ark API Key",
                    )
        elif sprite.rows >= 2 and len(sprite.row_prompts) < sprite.rows:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="多行序列帧需要为每一行填写动作描述",
            )
        if sprite.reference_image_path and not Path(sprite.reference_image_path).exists():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参考图不存在"
            )
    if req.job_type in IMAGE_JOB_TYPES:
        if not req.input_image_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该任务需要输入图片"
            )
        if not Path(req.input_image_path).exists():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="输入图片不存在"
            )


def params_json_from_request(
    req: JobCreateRequest,
    *,
    billing: dict | None = None,
    size_retry: SizeRetryPlan | None = None,
) -> dict:
    data = {
        "image_size": req.image_size,
        "image_quality": req.image_quality,
        "image_model": req.image_model,
        "vl_model": req.vl_model,
        "skip_vl": req.skip_vl,
        "source_only": req.source_only,
        "size_retry_mode": req.size_retry_mode,
        "size_retry_max_attempts": req.size_retry_max_attempts,
        "size_retry_max_credits": req.size_retry_max_credits,
        "request_fields": sorted(req.model_fields_set),
        "pixelize": req.pixelize.model_dump(mode="json"),
        "pixelize_fields": sorted(req.pixelize.model_fields_set),
        "grid": req.grid.model_dump(mode="json"),
        "style_profile": req.style_profile.model_dump(mode="json"),
        "sprite": req.sprite.model_dump(mode="json"),
        "asset": req.asset.model_dump(mode="json"),
    }
    if size_retry is not None and size_retry.enabled:
        data["size_retry"] = {
            "enabled": True,
            "mode": size_retry.mode,
            "per_attempt": size_retry.per_attempt,
            "max_attempts": size_retry.max_attempts,
            "base_price": size_retry.base_price,
            "expected_size": list(size_retry.expected_size) if size_retry.expected_size else None,
        }
    if billing is not None:
        data["billing"] = billing
    return data


def _existing_job(db: Session, user: User, client_request_id: str) -> GenerationJob | None:
    if not client_request_id:
        return None
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(
            GenerationJob.user_id == user.id,
            GenerationJob.client_request_id == client_request_id,
        )
    )


def _is_sprite_video_bridge(req: JobCreateRequest) -> bool:
    return req.job_type == "sprite_sheet" and req.sprite.mode == "video_bridge"


def _frame_count_for_price(req: JobCreateRequest) -> int:
    if req.job_type != "sprite_sheet":
        return 1
    return max(1, req.sprite.rows * req.sprite.cols)


def _sprite_billing_units(req: JobCreateRequest) -> int:
    """mosaic 序列帧 billing 单位：按 ceil(总帧数 / 9) 计算（最少 1）。"""
    if req.job_type != "sprite_sheet" or _is_sprite_video_bridge(req):
        return 1
    total = max(1, req.sprite.rows * req.sprite.cols)
    return max(1, (total + 8) // 9)


def _video_bridge_duration_seconds_for_price(req: JobCreateRequest) -> int:
    if req.job_type != "sprite_sheet":
        return VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS
    return derive_video_bridge_duration_seconds(_frame_count_for_price(req), req.sprite.duration_ms)


def _base_price_for_request(db: Session, req: JobCreateRequest) -> int:
    if _is_sprite_video_bridge(req):
        price_key = video_bridge_price_key(req.sprite.video_model)
    else:
        price_key = (
            "image_to_image" if req.job_type == "asset" and req.input_image_path else req.job_type
        )
    try:
        return get_price(db, price_key)
    except PricingDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _original_price_for_request(db: Session, req: JobCreateRequest) -> int:
    base_price = _base_price_for_request(db, req)
    if _is_sprite_video_bridge(req):
        return video_bridge_price_credits(
            req.sprite.video_model,
            duration_seconds=_video_bridge_duration_seconds_for_price(req),
            base_duration_price_credits=base_price,
        )
    if req.job_type == "sprite_sheet":
        return base_price * _sprite_billing_units(req)
    return base_price


def _price_for_request(db: Session, req: JobCreateRequest, cfg: AppConfig | None = None) -> int:
    """对外的实扣价（即下单预扣额）：原价经全局折扣后的折后价。

    启用尺寸重试时返回预扣总额（per_attempt × max_attempts），与
    create_job_in_transaction 的冻结逻辑保持一致，确保批量/重试路径的
    余额校验与实际冻结额相符。
    """
    original = _original_price_for_request(db, req)
    discount = load_pricing_discount(db)
    price = apply_discount(original, discount.rate)
    effective_cfg = cfg if cfg is not None else _effective_pix_config(db)
    plan = _size_retry_plan(db, req, effective_cfg, discount)
    if plan.enabled:
        return plan.reserve_total
    return price


# ---- 尺寸重试计费 ----

# 尺寸重试只适用于素材生产：按 perfectPixel + 2 的幂透明填充后的成品像素尺寸判定。
# t2i/i2i 原始生图是 source_only 大图、跳过像素化，无成品像素尺寸可比对，故排除。
SIZE_RETRY_JOB_TYPES = {"asset"}
_UI_COMPONENT_IMAGE_SIZE = "auto"
_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")


@dataclass(frozen=True)
class SizeRetryPlan:
    """尺寸重试的计费与执行计划。

    enabled=False 时其余字段无意义，调用方按普通任务计费。
    enabled=True 时：reserve_total = per_attempt × max_attempts（下单冻结最坏情况），
    worker 成功后按实际尝试次数 settle，退还差额。
    """

    enabled: bool = False
    per_attempt: int = 0
    max_attempts: int = 1
    mode: str = "attempts"
    expected_size: tuple[int, int] | None = None
    base_price: int = 0

    @property
    def reserve_total(self) -> int:
        return max(0, self.per_attempt * self.max_attempts)


def _expected_size_for_request(req: JobCreateRequest, cfg: AppConfig) -> tuple[int, int] | None:
    """目标成品像素尺寸 = 用户在像素尺寸里选的 output_size（尺寸重试要把填充后成品对齐到它）。

    仅对会走 perfectPixel + 透明填充的主体类 asset 任务有意义；尺寸非法时返回 None。
    """
    try:
        w, h = req.pixelize.output_size
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        return None
    if w < 1 or h < 1:
        return None
    return (w, h)


def _multi_candidate_enabled(cfg: AppConfig) -> bool:
    """是否处于多候选模式（此时尺寸重试不适用）。asset 任务运行时强制单图，不在此判断。"""
    try:
        return bool(cfg.image_gen.contact_sheet_enabled) and int(cfg.image_gen.n_sample_count) > 1
    except (TypeError, ValueError):
        return False


def _size_retry_plan(
    db: Session,
    req: JobCreateRequest,
    cfg: AppConfig,
    discount: PricingDiscount,
) -> SizeRetryPlan:
    """计算尺寸重试计费计划；不满足启用条件时返回 disabled 计划。"""
    if not req.size_retry_enabled or not getattr(cfg.image_gen, "size_retry_enabled", True):
        return SizeRetryPlan()
    if req.job_type not in SIZE_RETRY_JOB_TYPES:
        return SizeRetryPlan()
    if req.job_type == "asset" and req.asset.asset_kind in {"tile_texture", "dual_grid"}:
        # 无缝纹理/双瓦片不能透明补边，尺寸重试仅适用于主体透明类素材生产。
        return SizeRetryPlan()
    # source_only 的原生大图、多候选模式不适用（asset 运行时强制单图，故仅对非 asset 判断多候选）。
    if req.job_type != "asset" and _multi_candidate_enabled(cfg):
        return SizeRetryPlan()
    expected = _expected_size_for_request(req, cfg)
    if expected is None:
        return SizeRetryPlan()

    base_price = _base_price_for_request(db, req)
    if base_price <= 0:
        # 免费任务无需重试计费；按普通免费任务处理。
        return SizeRetryPlan()

    retry_rate = float(getattr(cfg.image_gen, "size_retry_discount_rate", 0.6) or 0.6)
    # 取更优价：尺寸重试 6 折与全局促销折扣中更低的单价。
    per_attempt = apply_discount(base_price, retry_rate)
    if discount.active:
        per_attempt = min(per_attempt, apply_discount(base_price, discount.rate))

    limit = max(1, int(getattr(cfg.image_gen, "size_retry_max_attempts_limit", 8) or 8))
    if req.size_retry_mode == "credits":
        budget = max(0, int(req.size_retry_max_credits))
        max_attempts = budget // per_attempt if per_attempt > 0 else 0
        max_attempts = max(1, min(limit, max_attempts))
    else:
        max_attempts = max(1, min(limit, int(req.size_retry_max_attempts)))

    return SizeRetryPlan(
        enabled=True,
        per_attempt=per_attempt,
        max_attempts=max_attempts,
        mode=req.size_retry_mode,
        expected_size=expected,
        base_price=base_price,
    )


def _billing_snapshot_for_request(
    db: Session,
    req: JobCreateRequest,
    *,
    original_total: int,
    discounted_total: int,
    discount: PricingDiscount,
    size_retry: SizeRetryPlan | None = None,
) -> dict | None:
    is_sprite = req.job_type == "sprite_sheet"
    is_video_bridge = _is_sprite_video_bridge(req)
    has_size_retry = size_retry is not None and size_retry.enabled
    if not is_sprite and not discount.active and not has_size_retry:
        return None
    snapshot: dict = {}
    if is_sprite:
        base_price = _base_price_for_request(db, req)
        if is_video_bridge:
            video_model = normalize_video_bridge_model(req.sprite.video_model)
            video_duration_seconds = _video_bridge_duration_seconds_for_price(req)
            video_price_cny = (
                VIDEO_BRIDGE_MODEL_PRICE_CNY[video_model]
                * video_duration_seconds
                / VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS
            )
            snapshot.update(
                {
                    "mode": "video_bridge",
                    "rows": req.sprite.rows,
                    "cols": req.sprite.cols,
                    "frame_count": _frame_count_for_price(req),
                    "billing_units": 1,
                    "video_model": video_model,
                    "video_duration_seconds": video_duration_seconds,
                    "video_price_cny": video_price_cny,
                    "video_base_price_credits": base_price,
                    "image_price_credits": VIDEO_BRIDGE_IMAGE_PRICE_CREDITS,
                    "formula": f"ceil(video_price_cny * {VIDEO_BRIDGE_PRICE_MULTIPLIER} + image_price_credits)",
                    "billing_note": "one keyframe image generation plus one 480p Seedance video bridge; postprocess included",
                }
            )
        else:
            snapshot.update(
                {
                    "mode": "mosaic",
                    "rows": req.sprite.rows,
                    "cols": req.sprite.cols,
                    "frame_base_price": base_price,
                    "frame_count": _frame_count_for_price(req),
                    "billing_units": _sprite_billing_units(req),
                    "max_frame_count": 64,
                    "formula": "ceil(rows*cols/9) * frame_base_price",
                    "billing_note": "one API call per job; postprocess included",
                }
            )
    snapshot["original_total_points"] = original_total
    snapshot["total_points"] = discounted_total
    if discount.active:
        snapshot["discount"] = {"rate": discount.rate, "label": discount.label}
    if has_size_retry:
        assert size_retry is not None
        snapshot["size_retry"] = {
            "enabled": True,
            "mode": size_retry.mode,
            "base_price": size_retry.base_price,
            "per_attempt": size_retry.per_attempt,
            "max_attempts": size_retry.max_attempts,
            "reserved_total": size_retry.reserve_total,
            "expected_size": list(size_retry.expected_size) if size_retry.expected_size else None,
            "billing_note": "reserve per_attempt*max_attempts; settle by actual attempts",
        }
    return snapshot


def _enforce_input_path_ownership(
    db: Session, user: User, req: JobCreateRequest, settings: WebSettings | None
) -> None:
    """校验用户提交的输入图/参考图路径必须归属自己，防止任意文件读取（LFI）。

    合法来源：用户自己的上传目录，或用户自己任务的 run 目录（本地像素化 / 重新像素化 /
    复用源图等链路会把这些产物路径回填到 input_image_path）。指向他人文件或系统任意路径时拒绝。
    """
    effective_settings = settings if settings is not None else load_web_settings()
    for raw_path in (req.input_image_path, req.sprite.reference_image_path):
        if not raw_path:
            continue
        try:
            resolve_owned_input_path(raw_path, user, db, effective_settings)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="输入图片路径不合法",
            ) from exc


def create_job_in_transaction(
    db: Session,
    user: User,
    req: JobCreateRequest,
    *,
    reserve: bool = True,
    batch: GenerationBatch | None = None,
    cfg: AppConfig | None = None,
    settings: WebSettings | None = None,
) -> GenerationJob:
    validate_job_request(req, cfg)
    _enforce_input_path_ownership(db, user, req, settings)
    client_request_id = req.client_request_id.strip()
    existing = _existing_job(db, user, client_request_id)
    if existing is not None:
        return existing

    original_price = _original_price_for_request(db, req)
    discount = load_pricing_discount(db)
    price = apply_discount(original_price, discount.rate)

    effective_cfg = cfg if cfg is not None else _effective_pix_config(db)
    size_retry = _size_retry_plan(db, req, effective_cfg, discount)
    if size_retry.enabled:
        # 下单冻结最坏情况点数（per_attempt × max_attempts）；worker 成功后按实际尝试结算退差额。
        price = size_retry.reserve_total

    billing = _billing_snapshot_for_request(
        db,
        req,
        original_total=original_price,
        discounted_total=price,
        discount=discount,
        size_retry=size_retry,
    )
    job = GenerationJob(
        user_id=user.id,
        batch_id=batch.id if batch is not None else None,
        client_request_id=client_request_id or uuid4().hex,
        job_type=req.job_type,
        status="pending",
        prompt=_job_prompt_for_record(req),
        input_image_path=req.input_image_path,
        params_json=params_json_from_request(req, billing=billing, size_retry=size_retry),
        price_credits=price,
    )
    db.add(job)
    db.flush()
    if reserve:
        reserve_credits(db, user, job, price)
    return job


def create_job(
    db: Session,
    user: User,
    req: JobCreateRequest,
    settings: WebSettings | None = None,
) -> GenerationJob:
    cfg = _effective_pix_config(db, settings)
    request_id = req.client_request_id.strip()
    if _existing_job(db, user, request_id) is None:
        validate_job_request(req, cfg)
        _enforce_request_prompt_policy(db, user, req, cfg)
        enforce_generation_limits(db, user, new_jobs=1)
    try:
        job = create_job_in_transaction(db, user, req, cfg=cfg, settings=settings)
    except InsufficientCreditsError as exc:
        raise insufficient_credits_http() from exc
    db.commit()
    db.refresh(job)
    return (
        db.scalar(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(GenerationJob.id == job.id)
        )
        or job
    )


def _default_batch_name() -> str:
    return f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def create_jobs_batch(
    db: Session,
    user: User,
    reqs: list[JobCreateRequest],
    *,
    batch_name: str = "",
    mode: str = "mixed",
    settings: WebSettings | None = None,
) -> tuple[list[GenerationJob], int, GenerationBatch | None]:
    cfg = _effective_pix_config(db, settings)
    if not reqs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="批量任务不能为空"
        )

    total_price = 0
    prices: list[int] = []
    seen_request_ids: set[str] = set()
    existing_by_index: dict[int, GenerationJob] = {}
    for index, req in enumerate(reqs):
        validate_job_request(req, cfg)
        request_id = req.client_request_id.strip()
        if request_id:
            if request_id in seen_request_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="批量任务中存在重复 client_request_id",
                )
            seen_request_ids.add(request_id)
        existing = _existing_job(db, user, request_id)
        if existing is not None:
            existing_by_index[index] = existing
            prices.append(0)
            continue
        _enforce_request_prompt_policy(db, user, req, cfg)
        price = _price_for_request(db, req, cfg)
        prices.append(price)
        total_price += price

    new_jobs = len(reqs) - len(existing_by_index)
    enforce_generation_limits(db, user, new_jobs=new_jobs)

    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    available = account.available_credits if account is not None else 0
    if available < total_price:
        raise insufficient_credits_http()

    batch: GenerationBatch | None = None
    if new_jobs > 0:
        batch = GenerationBatch(
            user_id=user.id,
            name=batch_name.strip() or _default_batch_name(),
            mode=(mode or "mixed").strip() or "mixed",
        )
        db.add(batch)
        db.flush()

    jobs: list[GenerationJob] = []
    try:
        for index, (req, price) in enumerate(zip(reqs, prices, strict=True)):
            existing = existing_by_index.get(index)
            if existing is not None:
                jobs.append(existing)
                continue
            job = create_job_in_transaction(db, user, req, reserve=False, batch=batch, cfg=cfg, settings=settings)
            reserve_credits(db, user, job, price)
            jobs.append(job)
    except InsufficientCreditsError as exc:
        db.rollback()
        raise insufficient_credits_http() from exc

    db.commit()
    ids = [job.id for job in jobs]
    loaded = list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
            .where(GenerationJob.id.in_(ids))
        )
    )
    by_id = {job.id: job for job in loaded}
    return [by_id.get(job.id, job) for job in jobs], total_price, batch


def _request_from_failed_job(job: GenerationJob) -> JobCreateRequest:
    params = job.params_json or {}
    retry = params.get("size_retry") or {}
    retry_enabled = bool(retry.get("enabled")) if isinstance(retry, dict) else False
    # 重试沿用原任务已折算好的最大尝试次数，统一按 attempts 模式重算计费（避免
    # credits 模式因 max_credits 未持久化而被重算成 1 次）。
    retry_max_attempts = int(retry.get("max_attempts") or 3) if isinstance(retry, dict) else 3
    return JobCreateRequest(
        job_type=job.job_type,
        prompt=job.prompt,
        input_image_path=job.input_image_path,
        client_request_id=f"retry-{job.id}-{uuid4().hex}",
        image_size=params.get("image_size"),
        image_quality=params.get("image_quality"),
        image_model=params.get("image_model"),
        vl_model=params.get("vl_model"),
        skip_vl=bool(params.get("skip_vl", False)),
        source_only=bool(params.get("source_only", False)),
        size_retry_enabled=retry_enabled,
        size_retry_mode="attempts",
        size_retry_max_attempts=max(1, retry_max_attempts),
        pixelize=PixelizeParamsSchema.model_validate(params.get("pixelize") or {}),
        grid=params.get("grid") or {},
        sprite=SpriteParamsSchema.model_validate(params.get("sprite") or {}),
        asset=params.get("asset") or {},
    )


def retry_failed_job(
    db: Session,
    user: User,
    job_id: int,
    settings: WebSettings | None = None,
) -> GenerationJob:
    cfg = _effective_pix_config(db, settings)
    failed_job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.batch))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
    )
    if failed_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if failed_job.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有失败任务可以重试")

    req = _request_from_failed_job(failed_job)
    validate_job_request(req, cfg)
    _enforce_request_prompt_policy(db, user, req, cfg)
    enforce_generation_limits(db, user, new_jobs=1)
    price = _price_for_request(db, req, cfg)

    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    available = account.available_credits if account is not None else 0
    if available < price:
        raise insufficient_credits_http()

    try:
        job = create_job_in_transaction(db, user, req, reserve=False, batch=failed_job.batch, cfg=cfg, settings=settings)
        reserve_credits(db, user, job, price)
    except InsufficientCreditsError as exc:
        db.rollback()
        raise insufficient_credits_http() from exc

    db.commit()
    return (
        db.scalar(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
            .where(GenerationJob.id == job.id)
        )
        or job
    )


def retry_failed_jobs_in_batch(
    db: Session,
    user: User,
    batch_id: int,
    settings: WebSettings | None = None,
) -> tuple[list[GenerationJob], int, GenerationBatch]:
    cfg = _effective_pix_config(db, settings)
    batch = db.scalar(
        select(GenerationBatch)
        .options(selectinload(GenerationBatch.jobs))
        .where(GenerationBatch.id == batch_id, GenerationBatch.user_id == user.id)
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材包不存在")

    failed_jobs = [job for job in batch.jobs if job.status == "failed"]
    if not failed_jobs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="没有可重试的失败任务")

    reqs = [_request_from_failed_job(job) for job in failed_jobs]
    total_price = 0
    prices: list[int] = []
    for req in reqs:
        validate_job_request(req, cfg)
        _enforce_request_prompt_policy(db, user, req, cfg)
        price = _price_for_request(db, req, cfg)
        prices.append(price)
        total_price += price

    enforce_generation_limits(db, user, new_jobs=len(reqs))

    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    available = account.available_credits if account is not None else 0
    if available < total_price:
        raise insufficient_credits_http()

    jobs: list[GenerationJob] = []
    try:
        for req, price in zip(reqs, prices, strict=True):
            job = create_job_in_transaction(db, user, req, reserve=False, batch=batch, cfg=cfg, settings=settings)
            reserve_credits(db, user, job, price)
            jobs.append(job)
    except InsufficientCreditsError as exc:
        db.rollback()
        raise insufficient_credits_http() from exc

    db.commit()
    ids = [job.id for job in jobs]
    loaded = list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
            .where(GenerationJob.id.in_(ids))
        )
    )
    by_id = {job.id: job for job in loaded}
    return [by_id.get(job.id, job) for job in jobs], total_price, batch
