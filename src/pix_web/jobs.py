"""任务创建与状态机。"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.credits import InsufficientCreditsError, insufficient_credits_http, reserve_credits
from pix_web.models import CreditAccount, GenerationBatch, GenerationJob, User
from pix_web.pricing import PricingDisabledError, get_price
from pix_web.schemas import JobCreateRequest, PixelizeParamsSchema
from pix_web.system_settings import enforce_generation_limits, enforce_prompt_policy

AI_JOB_TYPES = {"text_to_image", "image_to_image"}
IMAGE_JOB_TYPES = {"image_to_image", "local_pixelize", "repixelize"}


def validate_job_request(req: JobCreateRequest) -> None:
    prompt = (req.prompt or "").strip()
    if req.job_type == "text_to_image" and not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文生图任务需要 prompt")
    if req.job_type == "image_to_image" and not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="图生图任务需要 prompt")
    if req.job_type in IMAGE_JOB_TYPES:
        if not req.input_image_path:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该任务需要输入图片")
        if not Path(req.input_image_path).exists():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="输入图片不存在")


def params_json_from_request(req: JobCreateRequest) -> dict:
    return {
        "image_size": req.image_size,
        "image_quality": req.image_quality,
        "image_model": req.image_model,
        "vl_model": req.vl_model,
        "skip_vl": req.skip_vl,
        "pixelize": req.pixelize.model_dump(mode="json"),
    }


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


def _price_for_request(db: Session, req: JobCreateRequest) -> int:
    try:
        return get_price(db, req.job_type)
    except PricingDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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
    job = GenerationJob(
        user_id=user.id,
        batch_id=batch.id if batch is not None else None,
        client_request_id=client_request_id or uuid4().hex,
        job_type=req.job_type,
        status="pending",
        prompt=(req.prompt or "").strip() or None,
        input_image_path=req.input_image_path,
        params_json=params_json_from_request(req),
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
        enforce_prompt_policy(db, req.prompt)
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
        enforce_prompt_policy(db, req.prompt)
        price = _price_for_request(db, req)
        prices.append(price)
        total_price += price

    new_jobs = len(reqs) - len(existing_by_index)
    enforce_generation_limits(db, user, new_jobs=new_jobs)

    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    available = account.available_credits if account is not None else 0
    if available < total_price:
        raise insufficient_credits_http()

    batch = GenerationBatch(user_id=user.id, name=batch_name.strip() or _default_batch_name(), mode=mode.strip() or "mixed")
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
        pixelize=PixelizeParamsSchema.model_validate(params.get("pixelize") or {}),
    )


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
        enforce_prompt_policy(db, req.prompt)
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
