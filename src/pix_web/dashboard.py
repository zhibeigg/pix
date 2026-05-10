"""管理员运营统计。"""

from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.models import CreditTransaction, GenerationJob, PaymentOrder, UploadEvent, User


def _utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def _count_jobs(db: Session, *, status: str | None = None, since: datetime | None = None) -> int:
    stmt = select(func.count()).select_from(GenerationJob)
    if status is not None:
        stmt = stmt.where(GenerationJob.status == status)
    if since is not None:
        stmt = stmt.where(GenerationJob.created_at >= since)
    return db.scalar(stmt) or 0


def admin_dashboard(db: Session) -> dict[str, int | float]:
    today = _utc_day_start()
    jobs_today = _count_jobs(db, since=today)
    failed_today = _count_jobs(db, status="failed", since=today)
    succeeded_today = _count_jobs(db, status="succeeded", since=today)
    pending_jobs = _count_jobs(db, status="pending")
    running_jobs = _count_jobs(db, status="running")
    credits_recharged_today = db.scalar(
        select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
            CreditTransaction.type == "recharge",
            CreditTransaction.created_at >= today,
        )
    ) or 0
    credits_consumed_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.price_credits), 0)).where(
            GenerationJob.status == "succeeded",
            GenerationJob.finished_at >= today,
        )
    ) or 0
    orders_paid_today = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
        )
    ) or 0
    uploads_today = db.scalar(
        select(func.count()).select_from(UploadEvent).where(UploadEvent.created_at >= today)
    ) or 0
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    failure_rate = (failed_today / jobs_today) if jobs_today else 0.0
    return {
        "total_users": int(total_users),
        "jobs_today": int(jobs_today),
        "succeeded_today": int(succeeded_today),
        "failed_today": int(failed_today),
        "pending_jobs": int(pending_jobs),
        "running_jobs": int(running_jobs),
        "credits_consumed_today": int(credits_consumed_today),
        "credits_recharged_today": int(credits_recharged_today),
        "orders_paid_today": int(orders_paid_today),
        "uploads_today": int(uploads_today),
        "failure_rate": float(failure_rate),
    }
