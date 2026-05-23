"""生成任务接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.jobs import create_job, create_jobs_batch, retry_failed_job
from pix_web.models import GenerationJob, User
from pix_web.queue import enqueue_jobs
from pix_web.retention import delete_user_job, prune_user_photos
from pix_web.schemas import JobBatchCreateRequest, JobBatchCreateResponse, JobCreateRequest, JobResponse
from pix_web.security import get_current_user, get_db, get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
def create(
    req: JobCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> GenerationJob:
    job = create_job(db, user, req)
    enqueue_jobs(settings, [job.id])
    return job


@router.post("/batch", response_model=JobBatchCreateResponse)
def create_batch(
    req: JobBatchCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> JobBatchCreateResponse:
    jobs, total_price, batch = create_jobs_batch(db, user, req.jobs, batch_name=req.batch_name, mode=req.mode)
    enqueue_jobs(settings, [job.id for job in jobs if job.status == "pending"])
    return JobBatchCreateResponse(jobs=jobs, total_price_credits=total_price, batch_id=batch.id if batch else None)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
    limit: int = 50,
) -> list[GenerationJob]:
    if prune_user_photos(db, user.id, settings):
        db.commit()
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.user_id == user.id)
        .order_by(GenerationJob.created_at.desc())
        .limit(max(1, min(200, limit)))
    )
    return list(db.scalars(stmt))


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> GenerationJob:
    job = retry_failed_job(db, user, job_id)
    enqueue_jobs(settings, [job.id])
    return job


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> dict[str, bool]:
    delete_user_job(db, user.id, job_id, settings)
    db.commit()
    return {"deleted": True}


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationJob:
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job
