"""任务性能监控聚合：成功率、并发、时间序列、provider 与失败分类。

时间分桶在 Python 层完成，避免 SQLite / Postgres 的时间函数差异；按生图站点的任务量级
（日百~千），一次范围查询 + Python 聚合足够，未来量大可换 SQL 分桶或预聚合表。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.models import GenerationJob

# range -> (时间跨度, 分桶秒数)：1h→5min 桶、24h→1h 桶、7d→1天 桶
_RANGES: dict[str, tuple[timedelta, int]] = {
    "1h": (timedelta(hours=1), 300),
    "24h": (timedelta(hours=24), 3600),
    "7d": (timedelta(days=7), 86400),
}
DEFAULT_RANGE = "24h"


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


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
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    return float(ordered[idx])


def task_performance_metrics(db: Session, range_key: str) -> dict[str, Any]:
    if range_key not in _RANGES:
        range_key = DEFAULT_RANGE
    span, bucket_seconds = _RANGES[range_key]
    now = datetime.now(timezone.utc)
    since = now - span

    rows = db.execute(
        select(
            GenerationJob.status,
            GenerationJob.provider,
            GenerationJob.failure_code,
            GenerationJob.created_at,
            GenerationJob.started_at,
            GenerationJob.finished_at,
        ).where(GenerationJob.created_at >= since)
    ).all()

    # 预建连续空桶，保证时间轴不断点
    bucket_count = max(1, int(span.total_seconds() // bucket_seconds))
    series: list[dict[str, Any]] = [
        {
            "t": (since + timedelta(seconds=i * bucket_seconds)).isoformat(),
            "succeeded": 0,
            "failed": 0,
            "total": 0,
        }
        for i in range(bucket_count + 1)
    ]

    providers: dict[str, dict[str, int]] = {}
    failures: dict[str, int] = {}
    durations: list[float] = []
    succeeded = failed = total = 0

    for status, provider, failure_code, created_at, started_at, finished_at in rows:
        total += 1
        idx = int((_ensure_utc(created_at) - since).total_seconds() // bucket_seconds)
        if 0 <= idx < len(series):
            slot = series[idx]
            slot["total"] += 1
            if status == "succeeded":
                slot["succeeded"] += 1
            elif status == "failed":
                slot["failed"] += 1
        if status == "succeeded":
            succeeded += 1
        elif status == "failed":
            failed += 1
        bucket = providers.setdefault(provider or "", {"succeeded": 0, "failed": 0, "total": 0})
        bucket["total"] += 1
        if status == "succeeded":
            bucket["succeeded"] += 1
        elif status == "failed":
            bucket["failed"] += 1
        if status == "failed" and failure_code:
            failures[failure_code] = failures.get(failure_code, 0) + 1
        duration = _duration_seconds(started_at, finished_at)
        if duration is not None:
            durations.append(duration)

    provider_list = [
        {
            "provider": key,
            "succeeded": value["succeeded"],
            "failed": value["failed"],
            "total": value["total"],
            "success_rate": round(value["succeeded"] / (value["succeeded"] + value["failed"]), 4)
            if (value["succeeded"] + value["failed"]) else 0.0,
        }
        for key, value in sorted(providers.items(), key=lambda kv: -kv[1]["total"])
    ]
    failure_list = [
        {"code": code, "count": count}
        for code, count in sorted(failures.items(), key=lambda kv: -kv[1])
    ]

    running = db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.status == "running")
    ) or 0

    recent_jobs = list(
        db.scalars(select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(12))
    )
    recent = [
        {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "provider": job.provider or "",
            "failure_code": job.failure_code or "",
            "seconds": round(_duration_seconds(job.started_at, job.finished_at) or 0.0, 1),
            "created_at": _ensure_utc(job.created_at).isoformat(),
        }
        for job in recent_jobs
    ]

    closed = succeeded + failed
    return {
        "range": range_key,
        "bucket_seconds": bucket_seconds,
        "generated_at": now.isoformat(),
        "kpi": {
            "success_rate": round(succeeded / closed, 4) if closed else 0.0,
            "running": int(running),
            "total": total,
            "failed": failed,
            "avg_seconds": round(sum(durations) / len(durations), 1) if durations else 0.0,
            "p95_seconds": round(_p95(durations), 1),
        },
        "series": series,
        "providers": provider_list,
        "failures": failure_list,
        "recent": recent,
    }
