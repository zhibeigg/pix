"""生成任务接口。"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.credits import InsufficientCreditsError, insufficient_credits_http, spend_credits
from pix_web.jobs import create_job, create_jobs_batch, retry_failed_job
from pix_web.models import GenerationJob, User
from pix_web.queue import enqueue_jobs
from pix_web.retention import GALLERY_EXPAND_PRICE_CREDITS, GALLERY_EXPAND_SLOTS, delete_user_job, effective_gallery_limit, get_or_create_gallery_quota, prune_user_photos, retained_photo_count
from pix_web.schemas import GalleryQuotaResponse, JobBatchCreateRequest, JobBatchCreateResponse, JobCreateRequest, JobResponse, SequenceAlignmentRequest
from pix_web.sequence_alignment import apply_sequence_alignment
from pix_web.routers.files import _file_user
from pix_web.security import get_current_user, get_db, get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _safe_file_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (value or "").strip())
    return cleaned.strip("._")[:80]


def _job_file_prefix(job: GenerationJob) -> str:
    """作品文件名前缀：asset.name > prompt > job-id（与素材包命名同口径）。"""
    params = job.params_json if isinstance(job.params_json, dict) else {}
    asset = params.get("asset") if isinstance(params, dict) else None
    asset_name = asset.get("name") if isinstance(asset, dict) else None
    if isinstance(asset_name, str) and asset_name.strip():
        base = _safe_file_part(asset_name)
    elif job.prompt and job.prompt.strip():
        base = _safe_file_part(job.prompt)
    else:
        base = "job"
    return f"{base or 'job'}_{job.id}"


def _sprite_action_rows(meta_json_path: str | None) -> list[dict[str, object]]:
    """读 meta 的 sprite.rows_outputs，返回每个动作（行）的 {row_index, action_phase, sheet_abs}。"""
    if not meta_json_path:
        return []
    path = Path(meta_json_path)
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    sprite = meta.get("sprite") if isinstance(meta, dict) else None
    rows = sprite.get("rows_outputs") if isinstance(sprite, dict) else None
    if not isinstance(rows, list):
        return []
    result: list[dict[str, object]] = []
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        sheet_rel = entry.get("sheet")
        if not sheet_rel:
            continue
        row_index = entry.get("row_index")
        result.append({
            "row_index": int(row_index) if isinstance(row_index, int) else len(result),
            "action_phase": str(entry.get("action_phase") or ""),
            "sheet_abs": str(path.parent / str(sheet_rel)),
        })
    return result


@router.get("/{job_id}/sprite-actions.zip")
def download_sprite_actions(
    job_id: int,
    user: User = Depends(_file_user),
    db: Session = Depends(get_db),
) -> Response:
    """把序列帧作品每个动作（行）的横向 sheet 打包成 zip；query token 鉴权，支持浏览器直接下载。"""
    job = db.scalar(
        select(GenerationJob).options(selectinload(GenerationJob.outputs)).where(GenerationJob.id == job_id)
    )
    if job is None or (job.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if not job.outputs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品没有输出")
    rows = _sprite_action_rows(job.outputs[0].meta_json_path)
    if not rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该作品不是多动作序列帧")
    prefix = _job_file_prefix(job)
    buffer = BytesIO()
    added = 0
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zip_file:
        for row in rows:
            sheet = str(row["sheet_abs"])
            if not sheet or not Path(sheet).is_file():
                continue
            number = int(row["row_index"]) + 1
            phase = _safe_file_part(str(row["action_phase"]))
            name = f"{prefix}_action{number:02d}_{phase}.png" if phase else f"{prefix}_action{number:02d}.png"
            zip_file.write(sheet, name)
            added += 1
    if added == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="没有可打包的动作图")
    filename = f"{prefix}_sprite_actions.zip"
    # 作品名可能含中文，HTTP header 只能 latin-1：ASCII 兜底 + RFC 5987 filename* 带 UTF-8 原名。
    ascii_name = filename.encode("ascii", "ignore").decode().strip("_") or "sprite_actions.zip"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )


def _gallery_quota_response(db: Session, user: User) -> GalleryQuotaResponse:
    retained_limit = effective_gallery_limit(db, user.id)
    retained_count = retained_photo_count(db, user.id)
    return GalleryQuotaResponse(
        retained_count=retained_count,
        retained_limit=retained_limit,
        remaining_slots=max(0, retained_limit - retained_count),
        expand_price_credits=GALLERY_EXPAND_PRICE_CREDITS,
        expand_slots=GALLERY_EXPAND_SLOTS,
    )


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


@router.get("/gallery-quota", response_model=GalleryQuotaResponse)
def get_gallery_quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GalleryQuotaResponse:
    get_or_create_gallery_quota(db, user.id)
    response = _gallery_quota_response(db, user)
    db.commit()
    return response


@router.post("/gallery-quota/expand", response_model=GalleryQuotaResponse)
def expand_gallery_quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GalleryQuotaResponse:
    quota = get_or_create_gallery_quota(db, user.id)
    current_limit = effective_gallery_limit(db, user.id)
    try:
        spend_credits(db, user, GALLERY_EXPAND_PRICE_CREDITS, note=f"作品库容量 +{GALLERY_EXPAND_SLOTS}")
    except InsufficientCreditsError as exc:
        raise insufficient_credits_http() from exc
    quota.retained_limit = current_limit + GALLERY_EXPAND_SLOTS
    db.commit()
    return _gallery_quota_response(db, user)


@router.post("/{job_id}/sequence-alignment", response_model=JobResponse)
def save_sequence_alignment(
    job_id: int,
    req: SequenceAlignmentRequest,
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
    output = job.outputs[0] if job.outputs else None
    if output is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="任务没有可调整的输出")
    apply_sequence_alignment(job, output, req)
    db.commit()
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
    ) or job


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
