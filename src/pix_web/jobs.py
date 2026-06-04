"""任务创建与状态机。"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix.api.prompt_guard import RAW_IMAGE_PROMPT_MAX_CHARS
from pix.asset import AssetSizePolicyError, resolve_asset_generation_policy
from pix_web.credits import InsufficientCreditsError, insufficient_credits_http, reserve_credits
from pix_web.job_observability import record_policy_event
from pix_web.models import CreditAccount, GenerationBatch, GenerationJob, User
from pix_web.pricing import PricingDisabledError, get_price
from pix_web.schemas import JobCreateRequest, PixelizeParamsSchema, SpriteParamsSchema
from pix_web.system_settings import enforce_generation_limits, enforce_prompt_policy

AI_JOB_TYPES = {"asset", "text_to_image", "image_to_image", "sprite_sheet"}
IMAGE_JOB_TYPES = {"image_to_image", "local_pixelize", "repixelize"}
RAW_IMAGE_PROMPT_MAX_LENGTH = RAW_IMAGE_PROMPT_MAX_CHARS


def _asset_name(req: JobCreateRequest) -> str:
    return (req.asset.name or req.prompt or "").strip()


def _job_prompt_for_record(req: JobCreateRequest) -> str | None:
    if req.job_type == "asset":
        return _asset_name(req) or None
    return (req.prompt or "").strip() or None


def _prompt_policy_text(req: JobCreateRequest) -> str | None:
    if req.job_type == "asset":
        parts = [req.asset.name, req.asset.extra_prompt, req.prompt or ""]
        text = "\n".join(part.strip() for part in parts if part and part.strip())
        return text or None
    return req.prompt


def _prompt_policy_max_chars(req: JobCreateRequest) -> int | None:
    if req.job_type in AI_JOB_TYPES:
        return RAW_IMAGE_PROMPT_MAX_LENGTH
    return None


def _enforce_request_prompt_policy(db: Session, user: User, req: JobCreateRequest) -> None:
    prompt_text = _prompt_policy_text(req)
    try:
        enforce_prompt_policy(
            db,
            prompt_text,
            allow_template_break=req.source_only or req.job_type == "sprite_sheet",
            max_chars=_prompt_policy_max_chars(req),
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


def validate_job_request(req: JobCreateRequest) -> None:
    prompt = (req.prompt or "").strip()
    try:
        resolve_asset_generation_policy(tuple(req.pixelize.output_size))
    except AssetSizePolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if req.job_type == "asset" and not _asset_name(req):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材直出任务需要主体内容")
    if req.job_type == "asset" and req.input_image_path and not Path(req.input_image_path).exists():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参考图不存在")
    if req.job_type == "text_to_image" and not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文生图任务需要 prompt")
    if req.job_type == "text_to_image" and req.source_only and len(prompt) > RAW_IMAGE_PROMPT_MAX_LENGTH:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"原生生图 prompt 最多支持 {RAW_IMAGE_PROMPT_MAX_LENGTH} 字")
    if req.job_type == "image_to_image" and not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="图生图任务需要 prompt")
    if req.job_type == "sprite_sheet" and not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧任务需要 prompt")
    if req.job_type == "sprite_sheet":
        sprite = req.sprite
        if sprite.rows < 1 or sprite.rows > 8 or sprite.cols < 1 or sprite.cols > 8:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧每行/每列最多支持 8")
        if sprite.rows * sprite.cols < 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="序列帧网格至少需要 1 个单元")
        if sprite.rows >= 2 and len(sprite.row_prompts) < sprite.rows:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="多行序列帧需要为每一行填写动作描述")
        if sprite.reference_image_path and not Path(sprite.reference_image_path).exists():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参考图不存在")
    if req.job_type in IMAGE_JOB_TYPES:
        if not req.input_image_path:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该任务需要输入图片")
        if not Path(req.input_image_path).exists():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="输入图片不存在")


def params_json_from_request(req: JobCreateRequest, *, billing: dict | None = None) -> dict:
    data = {
        "image_size": req.image_size,
        "image_quality": req.image_quality,
        "image_model": req.image_model,
        "vl_model": req.vl_model,
        "skip_vl": req.skip_vl,
        "source_only": req.source_only,
        "request_fields": sorted(req.model_fields_set),
        "pixelize": req.pixelize.model_dump(mode="json"),
        "pixelize_fields": sorted(req.pixelize.model_fields_set),
        "grid": req.grid.model_dump(mode="json"),
        "sprite": req.sprite.model_dump(mode="json"),
        "asset": req.asset.model_dump(mode="json"),
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


def _frame_count_for_price(req: JobCreateRequest) -> int:
    if req.job_type != "sprite_sheet":
        return 1
    return max(1, req.sprite.rows * req.sprite.cols)


def _sprite_billing_units(req: JobCreateRequest) -> int:
    """序列帧 billing 单位：按 ceil(总帧数 / 9) 计算（最少 1）。"""
    if req.job_type != "sprite_sheet":
        return 1
    total = max(1, req.sprite.rows * req.sprite.cols)
    return max(1, (total + 8) // 9)


def _base_price_for_request(db: Session, req: JobCreateRequest) -> int:
    price_key = "image_to_image" if req.job_type == "asset" and req.input_image_path else req.job_type
    try:
        return get_price(db, price_key)
    except PricingDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _price_for_request(db: Session, req: JobCreateRequest) -> int:
    base_price = _base_price_for_request(db, req)
    if req.job_type == "sprite_sheet":
        return base_price * _sprite_billing_units(req)
    return base_price


def _billing_snapshot_for_request(db: Session, req: JobCreateRequest, *, total_price: int | None = None) -> dict | None:
    if req.job_type != "sprite_sheet":
        return None
    base_price = _base_price_for_request(db, req)
    frame_count = _frame_count_for_price(req)
    units = _sprite_billing_units(req)
    total = base_price * units if total_price is None else int(total_price)
    return {
        "rows": req.sprite.rows,
        "cols": req.sprite.cols,
        "frame_base_price": base_price,
        "frame_count": frame_count,
        "billing_units": units,
        "max_frame_count": 64,
        "total_points": total,
        "formula": "ceil(rows*cols/9) * frame_base_price",
        "billing_note": "one API call per job; postprocess included",
    }


def create_job_in_transaction(
    db: Session,
    user: User,
    req: JobCreateRequest,
    *,
    reserve: bool = True,
    batch: GenerationBatch | None = None,
) -> GenerationJob:
    validate_job_request(req)
    client_request_id = req.client_request_id.strip()
    existing = _existing_job(db, user, client_request_id)
    if existing is not None:
        return existing

    price = _price_for_request(db, req)
    billing = _billing_snapshot_for_request(db, req, total_price=price)
    job = GenerationJob(
        user_id=user.id,
        batch_id=batch.id if batch is not None else None,
        client_request_id=client_request_id or uuid4().hex,
        job_type=req.job_type,
        status="pending",
        prompt=_job_prompt_for_record(req),
        input_image_path=req.input_image_path,
        params_json=params_json_from_request(req, billing=billing),
        price_credits=price,
    )
    db.add(job)
    db.flush()
    if reserve:
        reserve_credits(db, user, job, price)
    return job


def create_job(db: Session, user: User, req: JobCreateRequest) -> GenerationJob:
    request_id = req.client_request_id.strip()
    if _existing_job(db, user, request_id) is None:
        _enforce_request_prompt_policy(db, user, req)
        enforce_generation_limits(db, user, new_jobs=1)
    try:
        job = create_job_in_transaction(db, user, req)
    except InsufficientCreditsError as exc:
        raise insufficient_credits_http() from exc
    db.commit()
    db.refresh(job)
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job.id)
    ) or job


def _default_batch_name() -> str:
    return f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def create_jobs_batch(
    db: Session,
    user: User,
    reqs: list[JobCreateRequest],
    *,
    batch_name: str = "",
    mode: str = "mixed",
) -> tuple[list[GenerationJob], int, GenerationBatch | None]:
    if not reqs:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="批量任务不能为空")

    total_price = 0
    prices: list[int] = []
    seen_request_ids: set[str] = set()
    existing_by_index: dict[int, GenerationJob] = {}
    for index, req in enumerate(reqs):
        validate_job_request(req)
        request_id = req.client_request_id.strip()
        if request_id:
            if request_id in seen_request_ids:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="批量任务中存在重复 client_request_id")
            seen_request_ids.add(request_id)
        existing = _existing_job(db, user, request_id)
        if existing is not None:
            existing_by_index[index] = existing
            prices.append(0)
            continue
        _enforce_request_prompt_policy(db, user, req)
        price = _price_for_request(db, req)
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
            job = create_job_in_transaction(db, user, req, reserve=False, batch=batch)
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
        pixelize=PixelizeParamsSchema.model_validate(params.get("pixelize") or {}),
        grid=params.get("grid") or {},
        sprite=SpriteParamsSchema.model_validate(params.get("sprite") or {}),
        asset=params.get("asset") or {},
    )


def retry_failed_job(db: Session, user: User, job_id: int) -> GenerationJob:
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
    validate_job_request(req)
    _enforce_request_prompt_policy(db, user, req)
    enforce_generation_limits(db, user, new_jobs=1)
    price = _price_for_request(db, req)

    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    available = account.available_credits if account is not None else 0
    if available < price:
        raise insufficient_credits_http()

    try:
        job = create_job_in_transaction(db, user, req, reserve=False, batch=failed_job.batch)
        reserve_credits(db, user, job, price)
    except InsufficientCreditsError as exc:
        db.rollback()
        raise insufficient_credits_http() from exc

    db.commit()
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
        .where(GenerationJob.id == job.id)
    ) or job


def retry_failed_jobs_in_batch(db: Session, user: User, batch_id: int) -> tuple[list[GenerationJob], int, GenerationBatch]:
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
        validate_job_request(req)
        _enforce_request_prompt_policy(db, user, req)
        price = _price_for_request(db, req)
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
            job = create_job_in_transaction(db, user, req, reserve=False, batch=batch)
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
