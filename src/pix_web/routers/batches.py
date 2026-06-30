"""素材包 / 批次接口。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.jobs import retry_failed_jobs_in_batch
from pix_web.models import GenerationBatch, GenerationJob, GenerationOutput, User
from pix_web.queue import enqueue_jobs
from pix_web.schemas import BatchUpdateRequest, GenerationBatchResponse, JobBatchCreateResponse, JobResponse
from pix_web.security import get_current_user, get_db, get_settings

router = APIRouter(prefix="/batches", tags=["batches"])


def _safe_zip_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    return cleaned.strip("-")[:80] or "asset-pack"


def _safe_file_prefix(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())
    return cleaned.strip("._")[:80]


def _job_item_prefix(job: GenerationJob) -> str:
    params = job.params_json if isinstance(job.params_json, dict) else {}
    asset = params.get("asset") if isinstance(params, dict) else None
    asset_name = asset.get("name") if isinstance(asset, dict) else None
    if isinstance(asset_name, str) and asset_name.strip():
        base = _safe_file_prefix(asset_name)
    elif job.prompt and job.prompt.strip():
        base = _safe_file_prefix(job.prompt)
    else:
        base = "job"
    return f"{base or 'job'}_{job.id}"


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
            prefix = _job_item_prefix(job)
            item_dir = f"{root}/{prefix}"
            added += int(_add_output_file(zip_file, job.id, output.source_path, f"{item_dir}/{prefix}_01_source.png"))
            added += int(_add_output_file(zip_file, job.id, output.analysis_json_path, f"{item_dir}/{prefix}_02_analysis.json"))
            added += int(_add_output_file(zip_file, job.id, output.pixelized_path, f"{item_dir}/{prefix}_03_pixelized.png"))
            added += int(_add_output_file(zip_file, job.id, output.meta_json_path, f"{item_dir}/{prefix}_meta.json"))
    if added == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="没有可下载的成功任务")
    return buffer.getvalue()


def _batch_response(batch: GenerationBatch) -> GenerationBatchResponse:
    jobs = list(batch.jobs)
    return GenerationBatchResponse(
        id=batch.id,
        name=batch.name,
        mode=batch.mode,
        status=batch.status,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        job_count=len(jobs),
        succeeded_count=sum(1 for job in jobs if job.status == "succeeded"),
        failed_count=sum(1 for job in jobs if job.status == "failed"),
        running_count=sum(1 for job in jobs if job.status in {"running", "waiting"}),
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


def _get_owned_batch(db: Session, user: User, batch_id: int, *, with_jobs: bool = False) -> GenerationBatch:
    stmt = select(GenerationBatch).where(GenerationBatch.id == batch_id, GenerationBatch.user_id == user.id)
    if with_jobs:
        stmt = stmt.options(selectinload(GenerationBatch.jobs))
    batch = db.scalar(stmt)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材包不存在")
    return batch


@router.patch("/{batch_id}", response_model=GenerationBatchResponse)
def update_batch(
    batch_id: int,
    req: BatchUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationBatchResponse:
    batch = _get_owned_batch(db, user, batch_id, with_jobs=True)
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材包名称不能为空")
        batch.name = name
    if req.status is not None:
        if req.status not in {"active", "archived"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材包状态无效")
        batch.status = req.status
    db.commit()
    db.refresh(batch)
    return _batch_response(batch)


@router.delete("/{batch_id}")
def delete_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    batch = _get_owned_batch(db, user, batch_id, with_jobs=True)
    if batch.jobs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能删除空素材包，请先归档")
    db.delete(batch)
    db.commit()
    return {"deleted": True}


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
    settings: WebSettings = Depends(get_settings),
) -> JobBatchCreateResponse:
    jobs, total_price, batch = retry_failed_jobs_in_batch(db, user, batch_id, settings)
    enqueue_jobs(settings, [job.id for job in jobs if job.status == "pending"])
    return JobBatchCreateResponse(jobs=jobs, total_price_credits=total_price, batch_id=batch.id)


@router.get("/{batch_id}/jobs", response_model=list[JobResponse])
def list_batch_jobs(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GenerationJob]:
    batch = _get_owned_batch(db, user, batch_id)
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
        .where(GenerationJob.batch_id == batch.id, GenerationJob.user_id == user.id)
        .order_by(GenerationJob.created_at.desc())
    )
    return list(db.scalars(stmt))
