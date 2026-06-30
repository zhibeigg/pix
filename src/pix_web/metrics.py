"""任务性能监控聚合：成功率、并发、时间序列、提供商成功率与失败分类。

时间分桶在 Python 层完成，避免 SQLite / Postgres 的时间函数差异；按生图站点的任务量级
（日百~千），一次范围查询 + Python 聚合足够，未来量大可换 SQL 分桶或预聚合表。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pix_web.models import GenerationJob, ImageProvider

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


def _safe_provider_text(value: object) -> str:
    return str(value or "").strip()


def _provider_aliases(rows: list[ImageProvider]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for row in rows:
        provider_id = _safe_provider_text(row.id)
        if not provider_id:
            continue
        aliases[provider_id.lower()] = provider_id
        display_name = _safe_provider_text(row.display_name)
        if display_name:
            aliases[display_name.lower()] = provider_id
    return aliases


def _match_provider_id(value: object, aliases: dict[str, str]) -> str:
    text = _safe_provider_text(value)
    if not text:
        return ""
    candidates = [text]
    lowered = text.lower()
    if lowered.endswith("_api"):
        candidates.append(text[:-4])
    if lowered.endswith("-api"):
        candidates.append(text[:-4])
    for candidate in candidates:
        matched = aliases.get(candidate.lower())
        if matched:
            return matched
    return text[:64]


def _attempt_status(value: object) -> str:
    text = _safe_provider_text(value).lower()
    if text in {"success", "succeeded", "ok"}:
        return "succeeded"
    if text in {"failed", "failure", "error", "timeout", "cancelled"}:
        return "failed"
    return ""


def _attempt_from_mapping(data: object, aliases: dict[str, str]) -> dict[str, str] | None:
    if not isinstance(data, dict):
        return None
    provider = _match_provider_id(data.get("provider") or data.get("provider_id"), aliases)
    status = _attempt_status(data.get("status"))
    if provider and status:
        return {"provider": provider, "status": status}
    return None


def _attempts_from_history(value: object, aliases: dict[str, str]) -> list[dict[str, str]]:
    attempts: list[dict[str, str]] = []
    if not isinstance(value, list):
        return attempts
    for event in value:
        if not isinstance(event, dict):
            continue
        nested = event.get("attempts")
        if isinstance(nested, list):
            for item in nested:
                attempt = _attempt_from_mapping(item, aliases)
                if attempt:
                    attempts.append(attempt)
        attempt = _attempt_from_mapping(event, aliases)
        if attempt:
            attempts.append(attempt)
    return attempts


def _read_output_meta(job: GenerationJob) -> dict[str, Any]:
    if not job.outputs:
        return {}
    meta_path = _safe_provider_text(job.outputs[0].meta_json_path)
    if not meta_path:
        return {}
    try:
        data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _provider_attempts_for_job(job: GenerationJob, aliases: dict[str, str]) -> list[dict[str, str]]:
    diagnostics = job.error_diagnostics_json if isinstance(job.error_diagnostics_json, dict) else {}
    attempts = _attempts_from_history(diagnostics.get("provider_attempts"), aliases)
    attempts.extend(_attempts_from_history(diagnostics.get("provider_history"), aliases))

    meta = _read_output_meta(job)
    image_gen = meta.get("image_gen") if isinstance(meta, dict) else None
    if isinstance(image_gen, dict):
        attempts.extend(_attempts_from_history(image_gen.get("provider_history"), aliases))
    sprite = meta.get("sprite") if isinstance(meta, dict) else None
    if isinstance(sprite, dict):
        attempts.extend(_attempts_from_history(sprite.get("provider_history"), aliases))

    if attempts:
        return attempts

    provider = _match_provider_id(job.provider or job.failure_source, aliases)
    status = "succeeded" if job.status == "succeeded" else "failed" if job.status == "failed" else ""
    return [{"provider": provider, "status": status}] if provider and status else []


def task_performance_metrics(db: Session, range_key: str) -> dict[str, Any]:
    if range_key not in _RANGES:
        range_key = DEFAULT_RANGE
    span, bucket_seconds = _RANGES[range_key]
    now = datetime.now(timezone.utc)
    since = now - span

    jobs = list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(GenerationJob.created_at >= since)
        )
    )
    provider_rows = list(db.scalars(select(ImageProvider).order_by(ImageProvider.priority.asc(), ImageProvider.id.asc())))
    provider_aliases = _provider_aliases(provider_rows)

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

    providers: dict[str, dict[str, Any]] = {
        row.id: {
            "provider": row.id,
            "display_name": row.display_name or row.id,
            "enabled": bool(row.enabled),
            "priority": int(row.priority or 100),
            "succeeded": 0,
            "failed": 0,
            "total": 0,
        }
        for row in provider_rows
        if row.id
    }
    failures: dict[str, int] = {}
    durations: list[float] = []
    succeeded = failed = total = 0

    for job in jobs:
        total += 1
        idx = int((_ensure_utc(job.created_at) - since).total_seconds() // bucket_seconds)
        if 0 <= idx < len(series):
            slot = series[idx]
            slot["total"] += 1
            if job.status == "succeeded":
                slot["succeeded"] += 1
            elif job.status == "failed":
                slot["failed"] += 1
        if job.status == "succeeded":
            succeeded += 1
        elif job.status == "failed":
            failed += 1
        for attempt in _provider_attempts_for_job(job, provider_aliases):
            provider_id = attempt["provider"]
            bucket = providers.setdefault(
                provider_id,
                {
                    "provider": provider_id,
                    "display_name": provider_id,
                    "enabled": False,
                    "priority": 9999,
                    "succeeded": 0,
                    "failed": 0,
                    "total": 0,
                },
            )
            bucket["total"] += 1
            if attempt["status"] == "succeeded":
                bucket["succeeded"] += 1
            elif attempt["status"] == "failed":
                bucket["failed"] += 1
        if job.status == "failed" and job.failure_code:
            failures[job.failure_code] = failures.get(job.failure_code, 0) + 1
        duration = _duration_seconds(job.started_at, job.finished_at)
        if duration is not None:
            durations.append(duration)

    provider_list = [
        {
            "provider": str(value["provider"]),
            "display_name": str(value["display_name"]),
            "enabled": bool(value["enabled"]),
            "priority": int(value["priority"]),
            "succeeded": int(value["succeeded"]),
            "failed": int(value["failed"]),
            "total": int(value["total"]),
            "success_rate": round(value["succeeded"] / (value["succeeded"] + value["failed"]), 4)
            if (value["succeeded"] + value["failed"]) else 0.0,
        }
        for value in sorted(
            providers.values(),
            key=lambda item: (int(item["priority"]), -int(item["total"]), str(item["provider"])),
        )
    ]
    failure_list = [
        {"code": code, "count": count}
        for code, count in sorted(failures.items(), key=lambda kv: -kv[1])
    ]

    running = db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.status.in_(["running", "waiting"]))
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
            "provider_display_name": providers.get(job.provider or "", {}).get("display_name", job.provider or ""),
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
