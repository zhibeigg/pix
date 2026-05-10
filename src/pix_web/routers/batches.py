"""素材包 / 批次接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.models import GenerationBatch, GenerationJob, User
from pix_web.schemas import GenerationBatchResponse, JobResponse
from pix_web.security import get_current_user, get_db

router = APIRouter(prefix="/batches", tags=["batches"])


def _batch_response(batch: GenerationBatch) -> GenerationBatchResponse:
    jobs = list(batch.jobs)
    return GenerationBatchResponse(
        id=batch.id,
        name=batch.name,
        mode=batch.mode,
        created_at=batch.created_at,
        job_count=len(jobs),
        succeeded_count=sum(1 for job in jobs if job.status == "succeeded"),
        failed_count=sum(1 for job in jobs if job.status == "failed"),
        running_count=sum(1 for job in jobs if job.status == "running"),
        pending_count=sum(1 for job in jobs if job.status == "pending"),
        total_price_credits=sum(job.price_credits for job in jobs),
    )


@router.get("", response_model=list[GenerationBatchResponse])
def list_batches(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> list[GenerationBatchResponse]:
    stmt = (
        select(GenerationBatch)
        .options(selectinload(GenerationBatch.jobs))
        .where(GenerationBatch.user_id == user.id)
        .order_by(GenerationBatch.created_at.desc())
        .limit(max(1, min(200, limit)))
    )
    return [_batch_response(batch) for batch in db.scalars(stmt)]


@router.get("/{batch_id}/jobs", response_model=list[JobResponse])
def list_batch_jobs(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GenerationJob]:
    batch = db.scalar(select(GenerationBatch).where(GenerationBatch.id == batch_id, GenerationBatch.user_id == user.id))
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材包不存在")
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
        .where(GenerationJob.batch_id == batch.id, GenerationJob.user_id == user.id)
        .order_by(GenerationJob.created_at.desc())
    )
    return list(db.scalars(stmt))
