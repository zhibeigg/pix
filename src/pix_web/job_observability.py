"""任务失败分类、策略审计与运行中任务维护。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix.api.http_client import ProviderError
from pix.api.packy_client import PackyError
from pix_web.credits import refund_reserved
from pix_web.models import GenerationJob, GenerationPolicyEvent, utcnow

POLICY_BLOCKED_MESSAGE = "该请求涉及直接复刻参考图，请改为“参考风格/构图，重新设计原创素材”。"
RUNNING_JOB_TIMEOUT_MESSAGE = "任务运行超时，系统自动清理"


@dataclass(frozen=True)
class FailureInfo:
    failure_type: str
    failure_source: str
    failure_code: str


@dataclass(frozen=True)
class PipelineDiagnostics:
    candidate_failure_count: int = 0
    pipeline_warning_count: int = 0


FAILURE_PIPELINE_ERROR = FailureInfo("pipeline_error", "pipeline", "unhandled_exception")


_TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}
_POLICY_TEXT_MARKERS = (
    "prompt_guard_rejected",
    "policy_blocked",
    "direct copy",
    "directly copy",
    "copy the reference",
    "replicate reference",
    "clone reference",
    "素材描述审核",
    "素材描述包含",
    "直接复刻参考图",
    "直接抄袭",
    "复刻参考图",
    "抄袭参考图",
    POLICY_BLOCKED_MESSAGE,
)
_UPSTREAM_TEXT_MARKERS = (
    "connection reset",
    "remoteprotocolerror",
    "readtimeout",
    "connecttimeout",
    "pooltimeout",
    "write timeout",
    "read timeout",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "service unavailable",
)
_WARNING_KEYS = {
    "external_backend_error",
    "analysis_failed",
    "candidate_ranking_failed",
    "model_error",
}
_WARNING_VALUES = {
    "grid_detection_failed",
    "size_mismatch",
    "model_failed_local",
    "model_unavailable_local",
}
_CANDIDATE_FAILURE_KEYS = {"pixelized_error"}
_CANDIDATE_FAILURE_REASONS = {"error", "failed", "grid_detection_failed", "size_mismatch"}


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _http_code_from_text(text: str) -> int | None:
    lowered = text.lower()
    for code in sorted(_TRANSIENT_HTTP_CODES):
        if f"http {code}" in lowered or f"http_{code}" in lowered:
            return code
    return None


def classify_failure(exc: BaseException) -> FailureInfo:
    """把 worker 捕获到的异常转为结构化失败字段。"""
    if isinstance(exc, ProviderError):
        source = f"{exc.provider_id or 'image'}_api"
        if exc.status_code in _TRANSIENT_HTTP_CODES:
            return FailureInfo("upstream_error", source, f"http_{exc.status_code}")
        if exc.status_code is not None:
            return FailureInfo("upstream_error", source, f"http_{exc.status_code}")
        if exc.category in {"content_policy", "invalid_request"}:
            return FailureInfo("policy_blocked", source, exc.category)
        return FailureInfo("upstream_error", source, exc.category or "provider_error")

    if isinstance(exc, PackyError):
        if exc.status_code in _TRANSIENT_HTTP_CODES:
            return FailureInfo("upstream_error", "packy_api", f"http_{exc.status_code}")
        if exc.status_code is not None:
            return FailureInfo("upstream_error", "packy_api", f"http_{exc.status_code}")
        return FailureInfo("upstream_error", "packy_api", "packy_error")

    if isinstance(exc, httpx.TimeoutException):
        return FailureInfo("upstream_error", "provider_api", "network_timeout")
    if isinstance(exc, httpx.HTTPError):
        return FailureInfo("upstream_error", "provider_api", "network_error")

    text = _safe_text(exc)
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in _POLICY_TEXT_MARKERS):
        return FailureInfo("policy_blocked", "prompt_guard", "policy_blocked")
    http_code = _http_code_from_text(text)
    if http_code is not None:
        return FailureInfo("upstream_error", "packy_api", f"http_{http_code}")
    if any(marker in lowered for marker in _UPSTREAM_TEXT_MARKERS):
        code = "network_timeout" if "timeout" in lowered or "timed out" in lowered else "network_error"
        return FailureInfo("upstream_error", "packy_api", code)
    return FAILURE_PIPELINE_ERROR


def apply_failure_info(job: GenerationJob, info: FailureInfo) -> None:
    job.failure_type = info.failure_type
    job.failure_source = info.failure_source
    job.failure_code = info.failure_code


def record_policy_event(
    db: Session,
    *,
    user_id: int,
    job_type: str,
    reason: str,
    prompt: str | None,
    source: str = "pre_create",
    job_id: int | None = None,
) -> GenerationPolicyEvent:
    event = GenerationPolicyEvent(
        user_id=user_id,
        job_id=job_id,
        job_type=(job_type or "")[:32],
        source=(source or "pre_create")[:64],
        reason=reason[:4000],
        prompt_excerpt=(prompt or "").strip()[:1000],
    )
    db.add(event)
    db.flush()
    return event


def mark_job_failed_and_refund(
    db: Session,
    job: GenerationJob,
    *,
    info: FailureInfo,
    message: str,
    refund_note: str,
    status: str = "failed",
) -> GenerationJob:
    job.status = status
    job.error_message = message[:8000]
    job.finished_at = utcnow()
    apply_failure_info(job, info)
    refund_reserved(db, job, note=refund_note)
    return job


def cleanup_timed_out_running_jobs(db: Session, *, timeout_minutes: int, limit: int = 100) -> int:
    timeout = max(1, int(timeout_minutes))
    cutoff = utcnow() - timedelta(minutes=timeout)
    jobs = list(
        db.scalars(
            select(GenerationJob)
            .where(
                GenerationJob.status == "running",
                GenerationJob.started_at.is_not(None),
                GenerationJob.finished_at.is_(None),
                GenerationJob.started_at <= cutoff,
            )
            .order_by(GenerationJob.started_at.asc())
            .limit(max(1, int(limit)))
        )
    )
    for job in jobs:
        mark_job_failed_and_refund(
            db,
            job,
            info=FailureInfo("timeout", "worker", "running_job_timeout"),
            message=RUNNING_JOB_TIMEOUT_MESSAGE,
            refund_note="任务运行超时自动退款",
        )
    if jobs:
        db.commit()
    return len(jobs)


def cancel_job_and_refund(db: Session, job: GenerationJob, *, note: str = "管理员取消任务并退款") -> GenerationJob:
    if job.status not in {"pending", "running"}:
        raise ValueError("只有排队中或运行中的任务可以取消")
    return mark_job_failed_and_refund(
        db,
        job,
        info=FailureInfo("cancelled", "admin", "admin_cancelled"),
        message=note,
        refund_note=note,
        status="cancelled",
    )


def admin_fail_job_and_refund(db: Session, job: GenerationJob, *, note: str = "管理员标记失败并退款") -> GenerationJob:
    if job.status not in {"pending", "running", "failed"}:
        raise ValueError("只有排队中、运行中或失败任务可以标记失败并退款")
    return mark_job_failed_and_refund(
        db,
        job,
        info=FailureInfo("pipeline_error", "admin", "admin_mark_failed_refund"),
        message=note if not job.error_message else job.error_message,
        refund_note=note,
        status="failed",
    )


def _count_diagnostic_markers(value: Any) -> tuple[int, int]:
    candidate_failures = 0
    pipeline_warnings = 0
    if isinstance(value, dict):
        if any(key in value for key in _CANDIDATE_FAILURE_KEYS):
            candidate_failures += 1
        preprocess = value.get("preprocess")
        if isinstance(preprocess, dict):
            reason = _safe_text(preprocess.get("reason")).lower()
            applied = bool(preprocess.get("applied"))
            if not applied and reason in _CANDIDATE_FAILURE_REASONS:
                pipeline_warnings += 1
        ranking = value.get("ranking")
        if isinstance(ranking, dict) and ranking.get("mode") == "fallback" and ranking.get("error"):
            pipeline_warnings += 1
        for key, item in value.items():
            if key in _WARNING_KEYS and item:
                pipeline_warnings += 1
            if isinstance(item, str) and item.lower() in _WARNING_VALUES:
                pipeline_warnings += 1
            child_candidate, child_warning = _count_diagnostic_markers(item)
            candidate_failures += child_candidate
            pipeline_warnings += child_warning
    elif isinstance(value, list):
        for item in value:
            child_candidate, child_warning = _count_diagnostic_markers(item)
            candidate_failures += child_candidate
            pipeline_warnings += child_warning
    elif isinstance(value, str) and value.lower() in _WARNING_VALUES:
        pipeline_warnings += 1
    return candidate_failures, pipeline_warnings


def collect_pipeline_diagnostics(meta: dict[str, Any] | None) -> PipelineDiagnostics:
    if not isinstance(meta, dict):
        return PipelineDiagnostics()
    candidate_failures, pipeline_warnings = _count_diagnostic_markers(meta)
    return PipelineDiagnostics(
        candidate_failure_count=max(0, int(candidate_failures)),
        pipeline_warning_count=max(0, int(pipeline_warnings)),
    )


def update_job_diagnostics(job: GenerationJob, meta: dict[str, Any] | None) -> PipelineDiagnostics:
    diagnostics = collect_pipeline_diagnostics(meta)
    job.candidate_failure_count = diagnostics.candidate_failure_count
    job.pipeline_warning_count = diagnostics.pipeline_warning_count
    return diagnostics


def load_job_with_outputs(db: Session, job_id: int) -> GenerationJob | None:
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
        .where(GenerationJob.id == job_id)
    )
