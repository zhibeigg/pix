"""管理员运营统计。"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.models import CreditTransaction, GenerationJob, GenerationPolicyEvent, PaymentOrder, UploadEvent, User, utcnow


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


def _count_jobs_by_failure(db: Session, failure_type: str, *, since: datetime) -> int:
    return db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.failure_type == failure_type,
            GenerationJob.finished_at >= since,
        )
    ) or 0


def _duration_seconds(started_at: datetime | None, finished_at: datetime | None) -> float | None:
    if started_at is None or finished_at is None:
        return None
    try:
        value = (finished_at - started_at).total_seconds()
    except TypeError:
        value = (finished_at.replace(tzinfo=None) - started_at.replace(tzinfo=None)).total_seconds()
    return max(0.0, float(value))


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    return float(ordered[index])


def admin_dashboard(db: Session) -> dict[str, int | float]:
    today = _utc_day_start()
    jobs_today = _count_jobs(db, since=today)
    failed_today = _count_jobs(db, status="failed", since=today)
    succeeded_today = _count_jobs(db, status="succeeded", since=today)
    pending_jobs = _count_jobs(db, status="pending")
    running_jobs = _count_jobs(db, status="running")
    policy_blocked_today = db.scalar(
        select(func.count()).select_from(GenerationPolicyEvent).where(GenerationPolicyEvent.created_at >= today)
    ) or 0
    upstream_errors_today = _count_jobs_by_failure(db, "upstream_error", since=today)
    timeout_jobs_today = _count_jobs_by_failure(db, "timeout", since=today)
    pipeline_errors_today = _count_jobs_by_failure(db, "pipeline_error", since=today)
    running_over_30m_jobs = db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.status == "running",
            GenerationJob.started_at.is_not(None),
            GenerationJob.finished_at.is_(None),
            GenerationJob.started_at <= utcnow() - timedelta(minutes=30),
        )
    ) or 0
    candidate_failures_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.candidate_failure_count), 0)).where(
            GenerationJob.finished_at >= today,
        )
    ) or 0
    pipeline_warnings_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.pipeline_warning_count), 0)).where(
            GenerationJob.finished_at >= today,
        )
    ) or 0
    duration_jobs = list(
        db.scalars(
            select(GenerationJob).where(
                GenerationJob.finished_at >= today,
                GenerationJob.started_at.is_not(None),
                GenerationJob.finished_at.is_not(None),
            )
        )
    )
    durations = [
        duration
        for duration in (_duration_seconds(job.started_at, job.finished_at) for job in duration_jobs)
        if duration is not None
    ]
    average_generation_seconds_today = sum(durations) / len(durations) if durations else 0.0
    p95_generation_seconds_today = _p95(durations)
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
        "policy_blocked_today": int(policy_blocked_today),
        "upstream_errors_today": int(upstream_errors_today),
        "timeout_jobs_today": int(timeout_jobs_today),
        "pipeline_errors_today": int(pipeline_errors_today),
        "pending_jobs": int(pending_jobs),
        "running_jobs": int(running_jobs),
        "running_over_30m_jobs": int(running_over_30m_jobs),
        "candidate_failures_today": int(candidate_failures_today),
        "pipeline_warnings_today": int(pipeline_warnings_today),
        "average_generation_seconds_today": float(round(average_generation_seconds_today, 3)),
        "p95_generation_seconds_today": float(round(p95_generation_seconds_today, 3)),
        "credits_consumed_today": int(credits_consumed_today),
        "credits_recharged_today": int(credits_recharged_today),
        "orders_paid_today": int(orders_paid_today),
        "uploads_today": int(uploads_today),
        "failure_rate": float(failure_rate),
    }
