"""素材包 / 批次接口。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.jobs import retry_failed_jobs_in_batch
from pix_web.models import GenerationBatch, GenerationJob, GenerationOutput, User
from pix_web.schemas import GenerationBatchResponse, JobBatchCreateResponse, JobResponse
from pix_web.security import get_current_user, get_db

router = APIRouter(prefix="/batches", tags=["batches"])


def _safe_zip_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    return cleaned.strip("-")[:80] or "asset-pack"


def _add_output_file(zip_file: ZipFile, job_id: int, path_value: str | None, archive_name: str) -> bool:
    if not path_value:
        return False
    path = Path(path_value)
    if not path.is_file():
        return False
    zip_file.write(path, archive_name)
    return True


def _build_batch_zip(batch: GenerationBatch) -> bytes:
    buffer = BytesIO()
    added = 0
    root = f"batch-{batch.id}-{_safe_zip_name(batch.name)}"
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zip_file:
        for job in batch.jobs:
            if job.status != "succeeded" or not job.outputs:
                continue
            output: GenerationOutput = job.outputs[0]
            added += int(_add_output_file(zip_file, job.id, output.source_path, f"{root}/job-{job.id}/01_source.png"))
            added += int(_add_output_file(zip_file, job.id, output.analysis_json_path, f"{root}/job-{job.id}/02_analysis.json"))
            added += int(_add_output_file(zip_file, job.id, output.pixelized_path, f"{root}/job-{job.id}/03_pixelized.png"))
            added += int(_add_output_file(zip_file, job.id, output.preview_path, f"{root}/job-{job.id}/04_preview.png"))
            added += int(_add_output_file(zip_file, job.id, output.meta_json_path, f"{root}/job-{job.id}/meta.json"))
    if added == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="没有可下载的成功任务")
    return buffer.getvalue()


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


@router.get("/{batch_id}/download")
def download_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    batch = db.scalar(
        select(GenerationBatch)
        .options(selectinload(GenerationBatch.jobs).selectinload(GenerationJob.outputs))
        .where(GenerationBatch.id == batch_id, GenerationBatch.user_id == user.id)
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材包不存在")
    data = _build_batch_zip(batch)
    filename = f"pix-batch-{batch.id}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{batch_id}/retry-failed", response_model=JobBatchCreateResponse)
def retry_failed_jobs(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobBatchCreateResponse:
    jobs, total_price, batch = retry_failed_jobs_in_batch(db, user, batch_id)
    return JobBatchCreateResponse(jobs=jobs, total_price_credits=total_price, batch_id=batch.id)


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
