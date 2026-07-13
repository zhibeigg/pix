"""管理员运营统计。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pix_web.models import GenerationJob, GenerationPolicyEvent, PaymentOrder, UploadEvent, User, utcnow
from pix_web.system_settings import resolve_site_timezone


DASHBOARD_HISTORY_DAYS = 14


def _business_day_start(tz: tzinfo, now: datetime | None = None) -> datetime:
    """按业务时区返回「今天 0 点」对应的 UTC 时间，用于和 UTC 存储的时间戳比较。

    例：tz=UTC+8、现在 07:00 UTC（15:00 SGT）→ 今天 0 点是 2026-06-17 00:00 +08
    = 2026-06-16 16:00 UTC。这样早上（00:00–08:00 SGT）支付的订单不会被算到「昨天」。
    """
    now_utc = now or datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    local_midnight = datetime.combine(now_local.date(), time.min, tzinfo=tz)
    return local_midnight.astimezone(timezone.utc)


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


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_date(value: datetime, tz: tzinfo) -> date:
    return _as_utc(value).astimezone(tz).date()


def _history_buckets(
    db: Session,
    *,
    tz: tzinfo,
    today: datetime,
    days: int = DASHBOARD_HISTORY_DAYS,
) -> list[dict[str, int | str]]:
    local_today = today.astimezone(tz).date()
    dates = [local_today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    buckets: dict[date, dict[str, int | str]] = {
        day: {
            "date": day.isoformat(),
            "jobs": 0,
            "succeeded": 0,
            "failed": 0,
            "credits_consumed": 0,
            "credits_recharged": 0,
            "orders_created": 0,
            "orders_paid": 0,
            "uploads": 0,
            "new_users": 0,
        }
        for day in dates
    }
    history_start = datetime.combine(dates[0], time.min, tzinfo=tz).astimezone(timezone.utc)

    job_rows = db.execute(
        select(
            GenerationJob.created_at,
            GenerationJob.status,
            GenerationJob.finished_at,
            GenerationJob.price_credits,
        ).where(
            or_(
                GenerationJob.created_at >= history_start,
                GenerationJob.finished_at >= history_start,
            )
        )
    ).all()
    for created_at, status, finished_at, price_credits in job_rows:
        created_bucket = buckets.get(_local_date(created_at, tz))
        if created_bucket is not None:
            created_bucket["jobs"] = int(created_bucket["jobs"]) + 1
            if status == "succeeded":
                created_bucket["succeeded"] = int(created_bucket["succeeded"]) + 1
            elif status == "failed":
                created_bucket["failed"] = int(created_bucket["failed"]) + 1
        if status == "succeeded" and finished_at is not None:
            finished_bucket = buckets.get(_local_date(finished_at, tz))
            if finished_bucket is not None:
                finished_bucket["credits_consumed"] = (
                    int(finished_bucket["credits_consumed"]) + int(price_credits or 0)
                )

    order_rows = db.execute(
        select(
            PaymentOrder.created_at,
            PaymentOrder.status,
            PaymentOrder.paid_at,
            PaymentOrder.credits,
        ).where(
            or_(
                PaymentOrder.created_at >= history_start,
                PaymentOrder.paid_at >= history_start,
            )
        )
    ).all()
    for created_at, status, paid_at, credits in order_rows:
        created_bucket = buckets.get(_local_date(created_at, tz))
        if created_bucket is not None:
            created_bucket["orders_created"] = int(created_bucket["orders_created"]) + 1
        if status == "paid" and paid_at is not None:
            paid_bucket = buckets.get(_local_date(paid_at, tz))
            if paid_bucket is not None:
                paid_bucket["orders_paid"] = int(paid_bucket["orders_paid"]) + 1
                paid_bucket["credits_recharged"] = (
                    int(paid_bucket["credits_recharged"]) + int(credits or 0)
                )

    for (created_at,) in db.execute(
        select(UploadEvent.created_at).where(UploadEvent.created_at >= history_start)
    ).all():
        bucket = buckets.get(_local_date(created_at, tz))
        if bucket is not None:
            bucket["uploads"] = int(bucket["uploads"]) + 1

    for (created_at,) in db.execute(
        select(User.created_at).where(User.created_at >= history_start)
    ).all():
        bucket = buckets.get(_local_date(created_at, tz))
        if bucket is not None:
            bucket["new_users"] = int(bucket["new_users"]) + 1

    return list(buckets.values())


def admin_dashboard(db: Session) -> dict[str, int | float | list[dict[str, int | str]]]:
    tz = resolve_site_timezone(db)
    today = _business_day_start(tz)
    jobs_today = _count_jobs(db, since=today)
    failed_today = _count_jobs(db, status="failed", since=today)
    succeeded_today = _count_jobs(db, status="succeeded", since=today)
    pending_jobs = _count_jobs(db, status="pending")
    running_jobs = _count_jobs(db, status="running") + _count_jobs(db, status="waiting")
    new_users_today = db.scalar(select(func.count()).select_from(User).where(User.created_at >= today)) or 0
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
        select(func.coalesce(func.sum(PaymentOrder.credits), 0)).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
        )
    ) or 0
    credits_consumed_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.price_credits), 0)).where(
            GenerationJob.status == "succeeded",
            GenerationJob.finished_at >= today,
        )
    ) or 0
    orders_created_today = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.created_at >= today,
        )
    ) or 0
    orders_paid_today = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
        )
    ) or 0
    paying_users_today = db.scalar(
        select(func.count(func.distinct(PaymentOrder.user_id))).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
        )
    ) or 0
    uploads_today = db.scalar(
        select(func.count()).select_from(UploadEvent).where(UploadEvent.created_at >= today)
    ) or 0
    active_user_ids = set(db.scalars(select(User.id).where(User.created_at >= today)))
    active_user_ids.update(db.scalars(select(GenerationJob.user_id).where(GenerationJob.created_at >= today).distinct()))
    active_user_ids.update(db.scalars(select(UploadEvent.user_id).where(UploadEvent.created_at >= today).distinct()))
    active_user_ids.update(db.scalars(select(PaymentOrder.user_id).where(PaymentOrder.created_at >= today).distinct()))
    active_user_ids.update(db.scalars(select(PaymentOrder.user_id).where(PaymentOrder.paid_at >= today).distinct()))
    active_users_today = len(active_user_ids)
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_jobs = _count_jobs(db)
    total_succeeded = _count_jobs(db, status="succeeded")
    total_failed = _count_jobs(db, status="failed")
    total_credits_consumed = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.price_credits), 0)).where(
            GenerationJob.status == "succeeded",
        )
    ) or 0
    total_orders_created = db.scalar(select(func.count()).select_from(PaymentOrder)) or 0
    total_orders_paid = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(PaymentOrder.status == "paid")
    ) or 0
    total_credits_recharged = db.scalar(
        select(func.coalesce(func.sum(PaymentOrder.credits), 0)).where(
            PaymentOrder.status == "paid",
        )
    ) or 0
    total_uploads = db.scalar(select(func.count()).select_from(UploadEvent)) or 0
    history = _history_buckets(db, tz=tz, today=today)
    failure_rate = (failed_today / jobs_today) if jobs_today else 0.0
    return {
        "total_users": int(total_users),
        "total_jobs": int(total_jobs),
        "total_succeeded": int(total_succeeded),
        "total_failed": int(total_failed),
        "total_credits_consumed": int(total_credits_consumed),
        "total_credits_recharged": int(total_credits_recharged),
        "total_orders_created": int(total_orders_created),
        "total_orders_paid": int(total_orders_paid),
        "total_uploads": int(total_uploads),
        "history_days": DASHBOARD_HISTORY_DAYS,
        "history": history,
        "new_users_today": int(new_users_today),
        "active_users_today": int(active_users_today),
        "paying_users_today": int(paying_users_today),
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
        "orders_created_today": int(orders_created_today),
        "orders_paid_today": int(orders_paid_today),
        "uploads_today": int(uploads_today),
        "failure_rate": float(failure_rate),
    }
