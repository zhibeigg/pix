from __future__ import annotations

from pix.api.http_client import ProviderError
from pix_web.job_observability import FailureInfo, build_error_diagnostics
from pix_web.models import GenerationJob, utcnow
from pix_web.schemas import AdminJobResponse, public_job_response


def failed_job() -> GenerationJob:
    return GenerationJob(
        id=1,
        user_id=10,
        job_type="asset",
        status="failed",
        prompt="test prompt",
        params_json={},
        price_credits=5,
        reserved_credits=0,
        error_message="upstream exploded\n\nTraceback (most recent call last): secret stack",
        user_error_message="生成服务暂时不可用，请稍后重试。",
        error_diagnostics_json={"provider_attempts": [{"provider": "p1", "category": "auth"}]},
        failure_type="upstream_error",
        failure_source="p1_api",
        failure_code="auth",
        provider="p1",
        candidate_failure_count=0,
        pipeline_warning_count=0,
        created_at=utcnow(),
        started_at=utcnow(),
        finished_at=utcnow(),
    )


def test_public_job_response_uses_safe_error_message() -> None:
    data = public_job_response(failed_job())

    assert data["error_message"] == "生成服务暂时不可用，请稍后重试。"
    assert "Traceback" not in data["error_message"]
    assert "error_diagnostics_json" not in data


def test_admin_job_response_keeps_detailed_error_and_diagnostics() -> None:
    data = AdminJobResponse.model_validate(failed_job()).model_dump(mode="python")

    assert "Traceback" in data["error_message"]
    assert data["user_error_message"] == "生成服务暂时不可用，请稍后重试。"
    assert data["error_diagnostics_json"]["provider_attempts"][0]["provider"] == "p1"


def test_error_diagnostics_are_redacted_and_truncated() -> None:
    exc = ProviderError(
        "boom",
        category="auth",
        status_code=403,
        body="x" * 3000,
        provider_id="p1",
    )
    diagnostics = build_error_diagnostics(
        exc,
        failure=FailureInfo("upstream_error", "p1_api", "auth"),
        provider_history=[{
            "provider": "p1",
            "authorization": "Bearer should-not-leak",
            "attempts": [{
                "provider": "p1",
                "category": "auth",
                "message": "m" * 1500,
                "api_key": "sk-secret",
            }],
        }],
        traceback_text="trace" * 2000,
    )

    serialized = str(diagnostics)
    assert "should-not-leak" not in serialized
    assert "sk-secret" not in serialized
    assert "<redacted>" in serialized
    assert len(diagnostics["traceback"]) < 6100
    assert len(diagnostics["provider_error"]["body"]) < 1100
