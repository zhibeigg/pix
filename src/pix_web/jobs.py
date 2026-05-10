"""任务创建与状态机。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.credits import InsufficientCreditsError, insufficient_credits_http, reserve_credits
from pix_web.models import GenerationJob, User
from pix_web.pricing import PricingDisabledError, get_price
from pix_web.schemas import JobCreateRequest


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


def create_job(db: Session, user: User, req: JobCreateRequest) -> GenerationJob:
    validate_job_request(req)
    client_request_id = req.client_request_id.strip()
    if client_request_id:
        existing = db.scalar(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(
                GenerationJob.user_id == user.id,
                GenerationJob.client_request_id == client_request_id,
            )
        )
        if existing is not None:
            return existing

    try:
        price = get_price(db, req.job_type)
    except PricingDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    job = GenerationJob(
        user_id=user.id,
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

    try:
        reserve_credits(db, user, job, price)
    except InsufficientCreditsError as exc:
        raise insufficient_credits_http() from exc

    db.commit()
    db.refresh(job)
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job.id)
    ) or job
