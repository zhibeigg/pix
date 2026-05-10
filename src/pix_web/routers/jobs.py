"""生成任务接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.jobs import create_job
from pix_web.models import GenerationJob, User
from pix_web.schemas import JobCreateRequest, JobResponse
from pix_web.security import get_current_user, get_db

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
def create(
    req: JobCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationJob:
    return create_job(db, user, req)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> list[GenerationJob]:
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.user_id == user.id)
        .order_by(GenerationJob.created_at.desc())
        .limit(max(1, min(200, limit)))
    )
    return list(db.scalars(stmt))


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
