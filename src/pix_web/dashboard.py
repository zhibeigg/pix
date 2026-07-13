"""管理员运营统计。"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pix_web.models import GenerationJob, GenerationPolicyEvent, PaymentOrder, UploadEvent, User
from pix_web.system_settings import resolve_site_timezone

DASHBOARD_HISTORY_DAYS = 14
DashboardRange = Literal["24h", "7d", "14d", "30d", "90d", "custom"]
DashboardGranularity = Literal["auto", "hour", "day", "week"]
ResolvedGranularity = Literal["hour", "day", "week"]

_RANGE_DAYS: dict[str, int] = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
_VALID_RANGES = {"24h", *_RANGE_DAYS, "custom"}
_VALID_GRANULARITIES = {"auto", "hour", "day", "week"}


class DashboardQueryError(ValueError):
    """仪表盘跨字段查询参数不合法。"""


@dataclass(frozen=True)
class _BucketWindow:
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class _PeriodWindow:
    start_at: datetime
    end_at: datetime
    local_days: int
    buckets: tuple[_BucketWindow, ...]


@dataclass(frozen=True)
class _DashboardWindow:
    range: DashboardRange
    granularity: ResolvedGranularity
    timezone: str
    tz: tzinfo
    generated_at: datetime
    data_cutoff_at: datetime
    current: _PeriodWindow
    previous: _PeriodWindow | None


@dataclass
class _Counters:
    jobs: int = 0
    succeeded: int = 0
    failed: int = 0
    credits_consumed: int = 0
    credits_recharged: int = 0
    orders_created: int = 0
    orders_paid: int = 0
    orders_converted: int = 0
    uploads: int = 0
    new_users: int = 0
    active_user_ids: set[int] = field(default_factory=set)
    paying_user_ids: set[int] = field(default_factory=set)

    def payload(self) -> dict[str, int | float | bool]:
        closed_jobs = self.succeeded + self.failed
        active_users = len(self.active_user_ids)
        paying_users = len(self.paying_user_ids)
        return {
            "jobs": self.jobs,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "credits_consumed": self.credits_consumed,
            "credits_recharged": self.credits_recharged,
            "net_credits": self.credits_recharged - self.credits_consumed,
            "orders_created": self.orders_created,
            "orders_paid": self.orders_paid,
            "orders_converted": self.orders_converted,
            "uploads": self.uploads,
            "new_users": self.new_users,
            "active_users": active_users,
            "paying_users": paying_users,
            "success_rate": self.succeeded / closed_jobs if closed_jobs else 0.0,
            "payment_rate": self.orders_converted / self.orders_created
            if self.orders_created
            else 0.0,
            "active_to_paying_rate": paying_users / active_users if active_users else 0.0,
            "has_data": any(
                (
                    self.jobs,
                    self.credits_recharged,
                    self.orders_created,
                    self.orders_paid,
                    self.uploads,
                    self.new_users,
                    active_users,
                )
            ),
        }


@dataclass
class _PeriodAggregation:
    window: _PeriodWindow
    total: _Counters
    buckets: list[_Counters]
    bucket_starts: list[datetime]

    @classmethod
    def create(cls, window: _PeriodWindow) -> _PeriodAggregation:
        return cls(
            window=window,
            total=_Counters(),
            buckets=[_Counters() for _ in window.buckets],
            bucket_starts=[bucket.start_at for bucket in window.buckets],
        )

    def bucket_for(self, value: datetime) -> _Counters | None:
        value_utc = _as_utc(value)
        index = bisect_right(self.bucket_starts, value_utc) - 1
        if index < 0 or index >= len(self.window.buckets):
            return None
        bucket_window = self.window.buckets[index]
        if value_utc >= bucket_window.end_at:
            return None
        return self.buckets[index]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_now(now: datetime | None) -> datetime:
    return _as_utc(now or datetime.now(timezone.utc))


def _local_date(value: datetime, tz: tzinfo) -> date:
    """保留旧测试与调用方使用的业务时区日期转换辅助函数。"""
    return _as_utc(value).astimezone(tz).date()


def _timezone_name(tz: tzinfo) -> str:
    key = getattr(tz, "key", None)
    return str(key) if key else str(tz)


def _local_midnight(day: date, tz: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)


def _business_day_start(tz: tzinfo, now: datetime | None = None) -> datetime:
    now_utc = _normalize_now(now)
    return _local_midnight(now_utc.astimezone(tz).date(), tz)


def _calendar_buckets(
    *, start_at: datetime, end_at: datetime, local_days: int, size_days: int, tz: tzinfo
) -> tuple[_BucketWindow, ...]:
    start_day = start_at.astimezone(tz).date()
    buckets: list[_BucketWindow] = []
    offset = 0
    while offset < local_days:
        bucket_start = _local_midnight(start_day + timedelta(days=offset), tz)
        bucket_end = _local_midnight(
            start_day + timedelta(days=min(local_days, offset + size_days)), tz
        )
        buckets.append(_BucketWindow(start_at=bucket_start, end_at=min(bucket_end, end_at)))
        offset += size_days
    return tuple(buckets)


def _hour_buckets(start_at: datetime, end_at: datetime) -> tuple[_BucketWindow, ...]:
    buckets: list[_BucketWindow] = []
    cursor = start_at
    while cursor < end_at:
        bucket_end = min(cursor + timedelta(hours=1), end_at)
        buckets.append(_BucketWindow(start_at=cursor, end_at=bucket_end))
        cursor = bucket_end
    return tuple(buckets)


def _period_window(
    *,
    start_at: datetime,
    end_at: datetime,
    local_days: int,
    granularity: ResolvedGranularity,
    tz: tzinfo,
) -> _PeriodWindow:
    if granularity == "hour":
        buckets = _hour_buckets(start_at, end_at)
    elif start_at.astimezone(tz).time() != time.min or end_at.astimezone(tz).time() != time.min:
        buckets = (_BucketWindow(start_at=start_at, end_at=end_at),)
    else:
        buckets = _calendar_buckets(
            start_at=start_at,
            end_at=end_at,
            local_days=local_days,
            size_days=1 if granularity == "day" else 7,
            tz=tz,
        )
    return _PeriodWindow(
        start_at=start_at,
        end_at=end_at,
        local_days=local_days,
        buckets=buckets,
    )


def _resolve_granularity(
    requested: str, *, range_value: str, local_days: int
) -> ResolvedGranularity:
    if requested not in _VALID_GRANULARITIES:
        raise DashboardQueryError("granularity 必须是 auto、hour、day 或 week")
    if requested == "auto":
        if range_value == "24h":
            return "hour"
        return "day" if local_days <= 90 else "week"
    if requested == "hour" and local_days > 7:
        raise DashboardQueryError("hour 粒度最多支持 7 天")
    return requested  # type: ignore[return-value]


def _build_window(
    db: Session,
    *,
    range_value: str,
    granularity: str,
    compare: bool,
    from_date: date | None,
    to_date: date | None,
    now: datetime | None,
) -> _DashboardWindow:
    if range_value not in _VALID_RANGES:
        raise DashboardQueryError("range 必须是 24h、7d、14d、30d、90d 或 custom")
    if range_value == "custom":
        if from_date is None or to_date is None:
            raise DashboardQueryError("custom 范围必须同时提供 from 和 to")
    elif from_date is not None or to_date is not None:
        raise DashboardQueryError("from 和 to 仅可用于 custom 范围")

    now_utc = _normalize_now(now)
    tz = resolve_site_timezone(db)
    local_today = now_utc.astimezone(tz).date()

    if range_value == "24h":
        local_hour = now_utc.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        current_end = local_hour.astimezone(timezone.utc) + timedelta(hours=1)
        current_start = current_end - timedelta(hours=24)
        local_days = 1
        previous_start = current_start - timedelta(hours=24)
        previous_end = current_start
    else:
        if range_value == "custom":
            assert from_date is not None and to_date is not None
            if from_date > to_date:
                raise DashboardQueryError("from 不得晚于 to")
            if to_date > local_today:
                raise DashboardQueryError("to 不得晚于站点今天")
            local_days = (to_date - from_date).days + 1
            if local_days > 365:
                raise DashboardQueryError("custom 范围最长为 365 天")
            start_day = from_date
            end_day = to_date + timedelta(days=1)
        else:
            local_days = _RANGE_DAYS[range_value]
            start_day = local_today - timedelta(days=local_days - 1)
            end_day = local_today + timedelta(days=1)
        current_start = _local_midnight(start_day, tz)
        current_end = _local_midnight(end_day, tz)
        previous_end = current_start
        previous_start = _local_midnight(start_day - timedelta(days=local_days), tz)

    resolved_granularity = _resolve_granularity(
        granularity, range_value=range_value, local_days=local_days
    )
    current = _period_window(
        start_at=current_start,
        end_at=current_end,
        local_days=local_days,
        granularity=resolved_granularity,
        tz=tz,
    )
    previous = (
        _period_window(
            start_at=previous_start,
            end_at=previous_end,
            local_days=local_days,
            granularity=resolved_granularity,
            tz=tz,
        )
        if compare
        else None
    )
    return _DashboardWindow(
        range=range_value,  # type: ignore[arg-type]
        granularity=resolved_granularity,
        timezone=_timezone_name(tz),
        tz=tz,
        generated_at=now_utc,
        data_cutoff_at=min(now_utc, current_end),
        current=current,
        previous=previous,
    )


def _in_period(value: datetime, period: _PeriodWindow) -> bool:
    value_utc = _as_utc(value)
    return period.start_at <= value_utc < period.end_at


def _period_targets(
    current: _PeriodAggregation, previous: _PeriodAggregation | None, value: datetime
) -> tuple[_PeriodAggregation, ...]:
    targets: list[_PeriodAggregation] = []
    if _in_period(value, current.window):
        targets.append(current)
    if previous is not None and _in_period(value, previous.window):
        targets.append(previous)
    return tuple(targets)


def _mark_active(target: _PeriodAggregation, user_id: int, value: datetime) -> None:
    target.total.active_user_ids.add(user_id)
    bucket = target.bucket_for(value)
    if bucket is not None:
        bucket.active_user_ids.add(user_id)


def _aggregate_periods(
    db: Session, window: _DashboardWindow
) -> tuple[_PeriodAggregation, _PeriodAggregation | None]:
    current = _PeriodAggregation.create(window.current)
    previous = _PeriodAggregation.create(window.previous) if window.previous is not None else None
    query_start = window.previous.start_at if window.previous is not None else window.current.start_at
    query_end = window.data_cutoff_at

    user_rows = db.execute(
        select(User.id, User.created_at).where(
            User.created_at >= query_start,
            User.created_at < query_end,
        )
    ).all()
    for user_id, created_at in user_rows:
        for target in _period_targets(current, previous, created_at):
            target.total.new_users += 1
            target.total.active_user_ids.add(user_id)
            bucket = target.bucket_for(created_at)
            if bucket is not None:
                bucket.new_users += 1
                bucket.active_user_ids.add(user_id)

    job_rows = db.execute(
        select(
            GenerationJob.user_id,
            GenerationJob.status,
            GenerationJob.price_credits,
            GenerationJob.created_at,
        ).where(
            GenerationJob.created_at >= query_start,
            GenerationJob.created_at < query_end,
        )
    ).all()
    for user_id, status, price_credits, created_at in job_rows:
        for target in _period_targets(current, previous, created_at):
            target.total.jobs += 1
            _mark_active(target, user_id, created_at)
            bucket = target.bucket_for(created_at)
            if bucket is not None:
                bucket.jobs += 1
            if status == "succeeded":
                target.total.succeeded += 1
                target.total.credits_consumed += int(price_credits or 0)
                if bucket is not None:
                    bucket.succeeded += 1
                    bucket.credits_consumed += int(price_credits or 0)
            elif status == "failed":
                target.total.failed += 1
                if bucket is not None:
                    bucket.failed += 1

    upload_rows = db.execute(
        select(UploadEvent.user_id, UploadEvent.created_at).where(
            UploadEvent.created_at >= query_start,
            UploadEvent.created_at < query_end,
        )
    ).all()
    for user_id, created_at in upload_rows:
        for target in _period_targets(current, previous, created_at):
            target.total.uploads += 1
            _mark_active(target, user_id, created_at)
            bucket = target.bucket_for(created_at)
            if bucket is not None:
                bucket.uploads += 1

    order_rows = db.execute(
        select(
            PaymentOrder.user_id,
            PaymentOrder.status,
            PaymentOrder.credits,
            PaymentOrder.created_at,
            PaymentOrder.paid_at,
        ).where(
            or_(
                (
                    (PaymentOrder.created_at >= query_start)
                    & (PaymentOrder.created_at < query_end)
                ),
                (
                    (PaymentOrder.paid_at >= query_start)
                    & (PaymentOrder.paid_at < query_end)
                ),
            )
        )
    ).all()
    for user_id, status, credits, created_at, paid_at in order_rows:
        for target in _period_targets(current, previous, created_at):
            target.total.orders_created += 1
            _mark_active(target, user_id, created_at)
            created_bucket = target.bucket_for(created_at)
            if created_bucket is not None:
                created_bucket.orders_created += 1
            if (
                status == "paid"
                and paid_at is not None
                and _as_utc(paid_at) < min(target.window.end_at, query_end)
            ):
                target.total.orders_converted += 1
                if created_bucket is not None:
                    created_bucket.orders_converted += 1

        if status != "paid" or paid_at is None:
            continue
        for target in _period_targets(current, previous, paid_at):
            target.total.orders_paid += 1
            target.total.credits_recharged += int(credits or 0)
            target.total.active_user_ids.add(user_id)
            target.total.paying_user_ids.add(user_id)
            paid_bucket = target.bucket_for(paid_at)
            if paid_bucket is not None:
                paid_bucket.orders_paid += 1
                paid_bucket.credits_recharged += int(credits or 0)
                paid_bucket.active_user_ids.add(user_id)
                paid_bucket.paying_user_ids.add(user_id)

    return current, previous


def _series_payload(aggregation: _PeriodAggregation, tz: tzinfo) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for bucket_window, counters in zip(
        aggregation.window.buckets, aggregation.buckets, strict=True
    ):
        result.append(
            {
                "start_at": bucket_window.start_at.astimezone(tz),
                "end_at": bucket_window.end_at.astimezone(tz),
                **counters.payload(),
            }
        )
    return result


def _history_from_series(series: list[dict[str, object]]) -> list[dict[str, int | str]]:
    history: list[dict[str, int | str]] = []
    for point in series:
        start_at = point["start_at"]
        assert isinstance(start_at, datetime)
        history.append(
            {
                "date": start_at.date().isoformat(),
                "jobs": int(point["jobs"]),
                "succeeded": int(point["succeeded"]),
                "failed": int(point["failed"]),
                "credits_consumed": int(point["credits_consumed"]),
                "credits_recharged": int(point["credits_recharged"]),
                "orders_created": int(point["orders_created"]),
                "orders_paid": int(point["orders_paid"]),
                "uploads": int(point["uploads"]),
                "new_users": int(point["new_users"]),
            }
        )
    return history


def _history_buckets(
    db: Session, *, tz: tzinfo, now: datetime, days: int = DASHBOARD_HISTORY_DAYS
) -> list[dict[str, int | str]]:
    local_today = now.astimezone(tz).date()
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
    history_start = _local_midnight(dates[0], tz)
    history_end = min(_local_midnight(local_today + timedelta(days=1), tz), now)

    for created_at, status, price_credits in db.execute(
        select(
            GenerationJob.created_at,
            GenerationJob.status,
            GenerationJob.price_credits,
        ).where(
            GenerationJob.created_at >= history_start,
            GenerationJob.created_at < history_end,
        )
    ).all():
        bucket = buckets.get(_as_utc(created_at).astimezone(tz).date())
        if bucket is None:
            continue
        bucket["jobs"] = int(bucket["jobs"]) + 1
        if status == "succeeded":
            bucket["succeeded"] = int(bucket["succeeded"]) + 1
            bucket["credits_consumed"] = int(bucket["credits_consumed"]) + int(
                price_credits or 0
            )
        elif status == "failed":
            bucket["failed"] = int(bucket["failed"]) + 1

    for created_at, status, paid_at, credits in db.execute(
        select(
            PaymentOrder.created_at,
            PaymentOrder.status,
            PaymentOrder.paid_at,
            PaymentOrder.credits,
        ).where(
            or_(
                (
                    (PaymentOrder.created_at >= history_start)
                    & (PaymentOrder.created_at < history_end)
                ),
                (
                    (PaymentOrder.paid_at >= history_start)
                    & (PaymentOrder.paid_at < history_end)
                ),
            )
        )
    ).all():
        created_bucket = buckets.get(_as_utc(created_at).astimezone(tz).date())
        if created_bucket is not None:
            created_bucket["orders_created"] = int(created_bucket["orders_created"]) + 1
        if status == "paid" and paid_at is not None:
            paid_bucket = buckets.get(_as_utc(paid_at).astimezone(tz).date())
            if paid_bucket is not None:
                paid_bucket["orders_paid"] = int(paid_bucket["orders_paid"]) + 1
                paid_bucket["credits_recharged"] = int(
                    paid_bucket["credits_recharged"]
                ) + int(credits or 0)

    for (created_at,) in db.execute(
        select(UploadEvent.created_at).where(
            UploadEvent.created_at >= history_start,
            UploadEvent.created_at < history_end,
        )
    ).all():
        bucket = buckets.get(_as_utc(created_at).astimezone(tz).date())
        if bucket is not None:
            bucket["uploads"] = int(bucket["uploads"]) + 1

    for (created_at,) in db.execute(
        select(User.created_at).where(
            User.created_at >= history_start,
            User.created_at < history_end,
        )
    ).all():
        bucket = buckets.get(_as_utc(created_at).astimezone(tz).date())
        if bucket is not None:
            bucket["new_users"] = int(bucket["new_users"]) + 1

    return list(buckets.values())


def _count_jobs(
    db: Session,
    *,
    status: str | None = None,
    since: datetime | None = None,
    before: datetime | None = None,
) -> int:
    stmt = select(func.count()).select_from(GenerationJob)
    if status is not None:
        stmt = stmt.where(GenerationJob.status == status)
    if since is not None:
        stmt = stmt.where(GenerationJob.created_at >= since)
    if before is not None:
        stmt = stmt.where(GenerationJob.created_at < before)
    return db.scalar(stmt) or 0


def _count_jobs_by_failure(
    db: Session, failure_type: str, *, since: datetime, before: datetime
) -> int:
    return db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.failure_type == failure_type,
            GenerationJob.finished_at >= since,
            GenerationJob.finished_at < before,
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


def _today_and_totals(
    db: Session, *, tz: tzinfo, now: datetime
) -> dict[str, int | float]:
    today = _business_day_start(tz, now)
    jobs_today = _count_jobs(db, since=today, before=now)
    failed_today = _count_jobs(db, status="failed", since=today, before=now)
    succeeded_today = _count_jobs(db, status="succeeded", since=today, before=now)
    pending_jobs = _count_jobs(db, status="pending")
    running_jobs = _count_jobs(db, status="running") + _count_jobs(db, status="waiting")
    new_users_today = db.scalar(
        select(func.count()).select_from(User).where(
            User.created_at >= today,
            User.created_at < now,
        )
    ) or 0
    policy_blocked_today = db.scalar(
        select(func.count()).select_from(GenerationPolicyEvent).where(
            GenerationPolicyEvent.created_at >= today,
            GenerationPolicyEvent.created_at < now,
        )
    ) or 0
    upstream_errors_today = _count_jobs_by_failure(
        db, "upstream_error", since=today, before=now
    )
    timeout_jobs_today = _count_jobs_by_failure(db, "timeout", since=today, before=now)
    pipeline_errors_today = _count_jobs_by_failure(
        db, "pipeline_error", since=today, before=now
    )
    running_over_30m_jobs = db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.status == "running",
            GenerationJob.started_at.is_not(None),
            GenerationJob.finished_at.is_(None),
            GenerationJob.started_at <= now - timedelta(minutes=30),
        )
    ) or 0
    candidate_failures_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.candidate_failure_count), 0)).where(
            GenerationJob.finished_at >= today,
            GenerationJob.finished_at < now,
        )
    ) or 0
    pipeline_warnings_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.pipeline_warning_count), 0)).where(
            GenerationJob.finished_at >= today,
            GenerationJob.finished_at < now,
        )
    ) or 0
    duration_rows = db.execute(
        select(GenerationJob.started_at, GenerationJob.finished_at).where(
            GenerationJob.finished_at >= today,
            GenerationJob.finished_at < now,
            GenerationJob.started_at.is_not(None),
            GenerationJob.finished_at.is_not(None),
        )
    ).all()
    durations = [
        duration
        for duration in (
            _duration_seconds(started_at, finished_at)
            for started_at, finished_at in duration_rows
        )
        if duration is not None
    ]
    average_generation_seconds_today = sum(durations) / len(durations) if durations else 0.0
    p95_generation_seconds_today = _p95(durations)
    credits_recharged_today = db.scalar(
        select(func.coalesce(func.sum(PaymentOrder.credits), 0)).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
            PaymentOrder.paid_at < now,
        )
    ) or 0
    credits_consumed_today = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.price_credits), 0)).where(
            GenerationJob.status == "succeeded",
            GenerationJob.finished_at >= today,
            GenerationJob.finished_at < now,
        )
    ) or 0
    orders_created_today = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.created_at >= today,
            PaymentOrder.created_at < now,
        )
    ) or 0
    orders_paid_today = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
            PaymentOrder.paid_at < now,
        )
    ) or 0
    paying_users_today = db.scalar(
        select(func.count(func.distinct(PaymentOrder.user_id))).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today,
            PaymentOrder.paid_at < now,
        )
    ) or 0
    uploads_today = db.scalar(
        select(func.count()).select_from(UploadEvent).where(
            UploadEvent.created_at >= today,
            UploadEvent.created_at < now,
        )
    ) or 0
    active_user_ids = set(
        db.scalars(select(User.id).where(User.created_at >= today, User.created_at < now))
    )
    active_user_ids.update(
        db.scalars(
            select(GenerationJob.user_id)
            .where(GenerationJob.created_at >= today, GenerationJob.created_at < now)
            .distinct()
        )
    )
    active_user_ids.update(
        db.scalars(
            select(UploadEvent.user_id)
            .where(UploadEvent.created_at >= today, UploadEvent.created_at < now)
            .distinct()
        )
    )
    active_user_ids.update(
        db.scalars(
            select(PaymentOrder.user_id)
            .where(PaymentOrder.created_at >= today, PaymentOrder.created_at < now)
            .distinct()
        )
    )
    active_user_ids.update(
        db.scalars(
            select(PaymentOrder.user_id)
            .where(
                PaymentOrder.status == "paid",
                PaymentOrder.paid_at >= today,
                PaymentOrder.paid_at < now,
            )
            .distinct()
        )
    )

    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_jobs = _count_jobs(db)
    total_succeeded = _count_jobs(db, status="succeeded")
    total_failed = _count_jobs(db, status="failed")
    total_credits_consumed = db.scalar(
        select(func.coalesce(func.sum(GenerationJob.price_credits), 0)).where(
            GenerationJob.status == "succeeded"
        )
    ) or 0
    total_orders_created = db.scalar(select(func.count()).select_from(PaymentOrder)) or 0
    total_orders_paid = db.scalar(
        select(func.count()).select_from(PaymentOrder).where(PaymentOrder.status == "paid")
    ) or 0
    total_credits_recharged = db.scalar(
        select(func.coalesce(func.sum(PaymentOrder.credits), 0)).where(
            PaymentOrder.status == "paid"
        )
    ) or 0
    total_uploads = db.scalar(select(func.count()).select_from(UploadEvent)) or 0
    failure_rate = failed_today / jobs_today if jobs_today else 0.0

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
        "new_users_today": int(new_users_today),
        "active_users_today": len(active_user_ids),
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


def admin_dashboard(
    db: Session,
    *,
    range: DashboardRange = "14d",
    granularity: DashboardGranularity = "auto",
    compare: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """返回兼容旧字段的管理员运营总览，并附带可筛选周期聚合。"""
    window = _build_window(
        db,
        range_value=range,
        granularity=granularity,
        compare=compare,
        from_date=from_date,
        to_date=to_date,
        now=now,
    )
    current, previous = _aggregate_periods(db, window)
    series = _series_payload(current, window.tz)
    previous_series = _series_payload(previous, window.tz) if previous is not None else []
    if range == "14d" and window.granularity == "day":
        history = _history_from_series(series)
    else:
        history = _history_buckets(
            db,
            tz=window.tz,
            now=window.generated_at,
        )

    response: dict[str, object] = {
        **_today_and_totals(db, tz=window.tz, now=window.generated_at),
        "history_days": DASHBOARD_HISTORY_DAYS,
        "history": history,
        "window": {
            "range": window.range,
            "granularity": window.granularity,
            "timezone": window.timezone,
            "start_at": window.current.start_at.astimezone(window.tz),
            "end_at": window.current.end_at.astimezone(window.tz),
            "generated_at": window.generated_at.astimezone(window.tz),
            "data_cutoff_at": window.data_cutoff_at.astimezone(window.tz),
            "compare_enabled": previous is not None,
            "comparison_start_at": previous.window.start_at.astimezone(window.tz)
            if previous is not None
            else None,
            "comparison_end_at": previous.window.end_at.astimezone(window.tz)
            if previous is not None
            else None,
        },
        "current_period": current.total.payload(),
        "previous_period": previous.total.payload() if previous is not None else None,
        "series": series,
        "previous_series": previous_series,
    }
    return response
