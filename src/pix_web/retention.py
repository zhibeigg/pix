"""账户作品保留策略。"""

from __future__ import annotations

from pathlib import Path
import shutil

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.models import AssetPackItem, CreditTransaction, GenerationJob, GenerationOutput

MAX_RETAINED_PHOTOS_PER_USER = 10
ACTIVE_JOB_STATUSES = {"pending", "running"}


def retained_photo_count(db: Session, user_id: int) -> int:
    """返回用户当前已成功保留的作品数量。"""
    return len(_successful_jobs_with_outputs(db, user_id))


def delete_user_job(db: Session, user_id: int, job_id: int, settings: WebSettings) -> None:
    """手动删除用户作品，清理输出文件、素材包引用和流水关联。"""
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == user_id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if job.status in ACTIVE_JOB_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="生产中的作品暂不能删除")

    run_dirs = [output.run_dir for output in job.outputs if output.run_dir]
    db.execute(update(CreditTransaction).where(CreditTransaction.job_id == job.id).values(job_id=None))
    for item in db.scalars(select(AssetPackItem).where(AssetPackItem.job_id == job.id)):
        db.delete(item)
    for output in list(job.outputs):
        db.delete(output)
    db.delete(job)
    db.flush()

    for raw_dir in run_dirs:
        _remove_safe_run_dir(raw_dir, settings.storage_root)


def prune_user_photos(db: Session, user_id: int, settings: WebSettings, *, keep: int = MAX_RETAINED_PHOTOS_PER_USER) -> int:
    """保留用户最新 keep 张成功作品，删除更旧作品及其输出目录。"""
    if keep < 1:
        keep = 1
    jobs = _successful_jobs_with_outputs(db, user_id)
    stale_jobs = jobs[keep:]
    if not stale_jobs:
        return 0

    stale_job_ids = [job.id for job in stale_jobs]
    run_dirs = [output.run_dir for job in stale_jobs for output in job.outputs if output.run_dir]

    db.execute(
        update(CreditTransaction)
        .where(CreditTransaction.job_id.in_(stale_job_ids))
        .values(job_id=None)
    )
    for job in stale_jobs:
        for output in list(job.outputs):
            db.delete(output)
        db.delete(job)
    db.flush()

    for raw_dir in run_dirs:
        _remove_safe_run_dir(raw_dir, settings.storage_root)
    return len(stale_jobs)


def _successful_jobs_with_outputs(db: Session, user_id: int) -> list[GenerationJob]:
    packed_job_ids = select(AssetPackItem.job_id).where(AssetPackItem.user_id == user_id)
    stmt = (
        select(GenerationJob)
        .join(GenerationOutput)
        .options(selectinload(GenerationJob.outputs))
        .where(
            GenerationJob.user_id == user_id,
            GenerationJob.status == "succeeded",
            ~GenerationJob.id.in_(packed_job_ids),
        )
        .order_by(
            GenerationJob.finished_at.desc(),
            GenerationJob.created_at.desc(),
            GenerationJob.id.desc(),
        )
    )
    return list(db.scalars(stmt).unique())


def _remove_safe_run_dir(raw_dir: str, storage_root: Path) -> None:
    try:
        root = storage_root.resolve()
        target = Path(raw_dir).resolve()
        target.relative_to(root)
    except (OSError, ValueError):
        return
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
