"""账户作品保留策略。"""

from __future__ import annotations

from pathlib import Path
import shutil

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.models import AssetPackItem, CreditTransaction, GalleryQuota, GenerationJob, GenerationOutput, SharedWork

MAX_RETAINED_PHOTOS_PER_USER = 10
GALLERY_EXPAND_PRICE_CREDITS = 60
GALLERY_EXPAND_SLOTS = 10
ACTIVE_JOB_STATUSES = {"pending", "running", "waiting"}


def retained_photo_count(db: Session, user_id: int) -> int:
    """返回用户当前已成功保留的作品数量。"""
    return len(_successful_jobs_with_outputs(db, user_id))



def get_or_create_gallery_quota(db: Session, user_id: int) -> GalleryQuota:
    quota = db.scalar(select(GalleryQuota).where(GalleryQuota.user_id == user_id))
    if quota is not None:
        return quota
    quota = GalleryQuota(user_id=user_id, retained_limit=MAX_RETAINED_PHOTOS_PER_USER)
    db.add(quota)
    db.flush()
    return quota



def effective_gallery_limit(db: Session, user_id: int) -> int:
    quota = db.scalar(select(GalleryQuota).where(GalleryQuota.user_id == user_id))
    if quota is None:
        return MAX_RETAINED_PHOTOS_PER_USER
    return max(MAX_RETAINED_PHOTOS_PER_USER, quota.retained_limit)



def delete_user_job(db: Session, user_id: int, job_id: int, settings: WebSettings) -> None:
    """手动删除用户单个作品，清理输出文件、素材包引用和流水关联。"""
    delete_user_jobs(db, user_id, [job_id], settings)


def delete_user_jobs(db: Session, user_id: int, job_ids: list[int], settings: WebSettings) -> list[int]:
    """批量删除用户作品；校验失败时整体回滚，不做部分删除。"""
    ordered_ids = _unique_positive_job_ids(job_ids)
    if not ordered_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请选择要删除的作品")

    jobs = list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(GenerationJob.id.in_(ordered_ids), GenerationJob.user_id == user_id)
        ).unique()
    )
    jobs_by_id = {job.id: job for job in jobs}
    missing_ids = [job_id for job_id in ordered_ids if job_id not in jobs_by_id]
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")

    active_ids = [job.id for job in jobs if job.status in ACTIVE_JOB_STATUSES]
    if active_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="生产中的作品暂不能删除")

    run_dirs = [
        output.run_dir
        for job_id in ordered_ids
        for output in jobs_by_id[job_id].outputs
        if output.run_dir
    ]
    db.execute(update(CreditTransaction).where(CreditTransaction.job_id.in_(ordered_ids)).values(job_id=None))
    for item in db.scalars(select(AssetPackItem).where(AssetPackItem.job_id.in_(ordered_ids))):
        db.delete(item)
    for share in db.scalars(select(SharedWork).where(SharedWork.job_id.in_(ordered_ids))):
        share.status = "deleted"
        share.job_id = None
    for job_id in ordered_ids:
        job = jobs_by_id[job_id]
        for output in list(job.outputs):
            db.delete(output)
        db.delete(job)
    db.flush()

    for raw_dir in run_dirs:
        _remove_safe_run_dir(raw_dir, settings.storage_root)
    return ordered_ids


def _unique_positive_job_ids(job_ids: list[int]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for raw_id in job_ids:
        job_id = int(raw_id)
        if job_id <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="作品 ID 必须为正整数")
        if job_id in seen:
            continue
        seen.add(job_id)
        result.append(job_id)
    return result


def prune_user_photos(db: Session, user_id: int, settings: WebSettings, *, keep: int | None = None) -> int:
    """保留用户最新 keep 张成功作品；未显式传入 keep 时使用用户作品库容量。"""
    effective_keep = effective_gallery_limit(db, user_id) if keep is None else keep
    if effective_keep < 1:
        effective_keep = 1
    jobs = _successful_jobs_with_outputs(db, user_id)
    stale_jobs = jobs[effective_keep:]
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
    shared_job_ids = select(SharedWork.job_id).where(
        SharedWork.user_id == user_id,
        SharedWork.status == "active",
        SharedWork.job_id.is_not(None),
    )
    stmt = (
        select(GenerationJob)
        .join(GenerationOutput)
        .options(selectinload(GenerationJob.outputs))
        .where(
            GenerationJob.user_id == user_id,
            GenerationJob.status == "succeeded",
            ~GenerationJob.id.in_(packed_job_ids),
            ~GenerationJob.id.in_(shared_job_ids),
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
