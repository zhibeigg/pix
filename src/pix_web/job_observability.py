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
GENERIC_UPSTREAM_USER_MESSAGE = "生成服务暂时不可用，系统已尝试所有可用上游并自动退款。请稍后重试。"
GENERIC_PIPELINE_USER_MESSAGE = "后台处理任务时出现异常，系统已自动退款。请稍后重试。"
POLICY_USER_MESSAGE = "素材描述未通过安全检查，请调整描述后重试。"
_DIAGNOSTIC_STRING_LIMIT = 1000
_DIAGNOSTIC_TRACEBACK_LIMIT = 6000
_DIAGNOSTIC_LIST_LIMIT = 20
_SENSITIVE_KEY_MARKERS = ("authorization", "api_key", "apikey", "token", "secret", "password", "bearer")


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


def _shorten(value: str, limit: int = _DIAGNOSTIC_STRING_LIMIT) -> str:
    text = value.replace("\r\n", "\n").strip()
    return text if len(text) <= limit else f"{text[:limit]}…"


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key or "").lower()
    return any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS)


def sanitize_diagnostic_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "<truncated>"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:_DIAGNOSTIC_LIST_LIMIT]:
            clean_key = str(key)
            result[clean_key] = "<redacted>" if _is_sensitive_key(clean_key) else sanitize_diagnostic_value(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [sanitize_diagnostic_value(item, depth=depth + 1) for item in value[:_DIAGNOSTIC_LIST_LIMIT]]
    if isinstance(value, tuple):
        return [sanitize_diagnostic_value(item, depth=depth + 1) for item in list(value)[:_DIAGNOSTIC_LIST_LIMIT]]
    if isinstance(value, str):
        return _shorten(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _shorten(str(value))


def user_message_for_failure(info: FailureInfo) -> str:
    if info.failure_type == "policy_blocked":
        return POLICY_USER_MESSAGE
    if info.failure_type in {"upstream_error", "timeout"}:
        return GENERIC_UPSTREAM_USER_MESSAGE
    return GENERIC_PIPELINE_USER_MESSAGE


def build_error_diagnostics(
    exc: BaseException,
    *,
    failure: FailureInfo,
    provider_history: list[dict[str, Any]],
    traceback_text: str,
) -> dict[str, Any]:
    provider_attempts: list[dict[str, Any]] = []
    for event in provider_history[:_DIAGNOSTIC_LIST_LIMIT]:
        attempts = event.get("attempts") if isinstance(event, dict) else None
        if isinstance(attempts, list):
            provider_attempts.extend(
                sanitize_diagnostic_value(item) for item in attempts[:_DIAGNOSTIC_LIST_LIMIT]
                if isinstance(item, dict)
            )
    raw: dict[str, Any] = {
        "failure": {
            "type": failure.failure_type,
            "source": failure.failure_source,
            "code": failure.failure_code,
        },
        "exception": {
            "type": exc.__class__.__name__,
            "message": _shorten(str(exc), 2000),
        },
        "provider_history": sanitize_diagnostic_value(provider_history),
        "provider_attempts": provider_attempts[:_DIAGNOSTIC_LIST_LIMIT],
        "traceback": _shorten(traceback_text, _DIAGNOSTIC_TRACEBACK_LIMIT),
    }
    if isinstance(exc, ProviderError):
        raw["provider_error"] = {
            "provider_id": exc.provider_id,
            "category": exc.category,
            "status_code": exc.status_code,
            "retryable": exc.retryable,
            "body": _shorten(exc.body or "", 2000) if exc.body else "",
        }
    return sanitize_diagnostic_value(raw)


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
    user_message: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> GenerationJob:
    job.status = status
    job.error_message = message[:8000]
    job.user_error_message = user_message or user_message_for_failure(info)
    job.error_diagnostics_json = diagnostics or {}
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
