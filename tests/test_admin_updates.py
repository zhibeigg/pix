from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import jwt
from fastapi.testclient import TestClient

from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.models import User
from pix_web.release_updates import (
    ReleaseCheckResult,
    ReleaseUpdateChecker,
    TrustedRelease,
    parse_version,
    validate_release_manifest,
)
from pix_web.schemas import UpdaterAgentOperation, UpdaterAgentStatus
from pix_web.security import (
    UPDATE_STEP_UP_COOKIE_NAME,
    create_access_token,
    hash_password,
)
from pix_web.update_agent_client import UpdateAgentError

_COMMIT = "a" * 40
_DIGEST = "b" * 64


def _manifest(*, repository: str = "zhibeigg/pix", image_repository: str = "ghcr.io/zhibeigg/pix") -> dict:
    return {
        "schema_version": 1,
        "repository": repository,
        "tag": "v9.0.0",
        "version": "9.0.0",
        "commit": _COMMIT,
        "workflow": {
            "name": "Release",
            "run_id": 123,
            "run_attempt": 1,
            "repository": repository,
            "url": f"https://github.com/{repository}/actions/runs/123",
        },
        "images": {
            component: {"repository": f"{image_repository}-{component}", "digest": f"sha256:{_DIGEST}"}
            for component in ("backend", "frontend", "updater")
        },
        "alembic_head": "0025_promo_links",
        "minimum_updater_version": "1.131.2",
        "rollback_policy": {
            "supported": True,
            "automatic": True,
            "restore_database_after_migration": True,
        },
        "generated_at": "2026-07-11T00:00:00Z",
    }


def _trusted_release() -> TrustedRelease:
    return TrustedRelease(
        version="9.0.0",
        tag="v9.0.0",
        commit=_COMMIT,
        notes="Safe notes",
        manifest_sha256="c" * 64,
        alembic_head="0025_promo_links",
        rollback_supported=True,
    )


class _FakeGitHubClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url: str, *, headers: dict):
        self.calls.append((url, headers))
        return self.responses.pop(0)


def _response(status_code: int, *, json_data=None, content: bytes | None = None, headers=None):
    request = httpx.Request("GET", "https://api.github.test/value")
    if json_data is not None:
        return httpx.Response(status_code, json=json_data, headers=headers, request=request)
    return httpx.Response(status_code, content=content or b"", headers=headers, request=request)


def test_strict_version_and_manifest_validation() -> None:
    assert parse_version("1.20.3") == (1, 20, 3)
    for invalid in ("v1.2.3", "1.2", "1.2.3-rc1", "01.2.3.4"):
        try:
            parse_version(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid version: {invalid}")

    head, rollback = validate_release_manifest(
        _manifest(),
        repository="zhibeigg/pix",
        tag="v9.0.0",
        version="9.0.0",
        commit=_COMMIT,
    )
    assert head == "0025_promo_links"
    assert rollback is True

    invalid_repo = _manifest(repository="attacker/pix")
    invalid_image = _manifest(image_repository="ghcr.io/attacker/pix")
    for payload in (invalid_repo, invalid_image, {**_manifest(), "unexpected": True}):
        try:
            validate_release_manifest(
                payload,
                repository="zhibeigg/pix",
                tag="v9.0.0",
                version="9.0.0",
                commit=_COMMIT,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid manifest was trusted")


def test_release_selection_manifest_sha_and_ttl_cache() -> None:
    manifest_bytes = json.dumps(_manifest(), separators=(",", ":")).encode()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    releases = [
        {
            "tag_name": "v10.0.0",
            "draft": False,
            "prerelease": True,
            "target_commitish": _COMMIT,
            "assets": [],
        },
        {
            "tag_name": "v9.0.0",
            "draft": False,
            "prerelease": False,
            "target_commitish": _COMMIT,
            "body": "# Notes [link](https://example.invalid) <b>safe</b>",
            "assets": [
                {
                    "id": 41,
                    "name": "pix-release-manifest.json",
                    "digest": f"sha256:{manifest_sha}",
                }
            ],
        },
    ]
    fake = _FakeGitHubClient(
        [
            _response(200, json_data=releases, headers={"etag": '"release-etag"'}),
            _response(200, content=manifest_bytes),
        ]
    )
    settings = WebSettings(
        update_github_api_base="https://api.github.test",
        update_cache_ttl_seconds=300,
    )
    checker = ReleaseUpdateChecker(settings)
    with patch("pix_web.release_updates.httpx.AsyncClient", return_value=fake):
        first = asyncio.run(checker.check())
        second = asyncio.run(checker.check())

    assert first.release is not None
    assert first.release.version == "9.0.0"
    assert first.release.manifest_sha256 == manifest_sha
    assert "https://" not in first.release.notes
    assert second.from_cache is True
    assert len(fake.calls) == 2
    assert fake.calls[0][0].endswith("/repos/zhibeigg/pix/releases?per_page=30")
    assert fake.calls[1][0].endswith("/repos/zhibeigg/pix/releases/assets/41")


def test_release_uses_etag_and_degrades_rate_limit_without_500() -> None:
    cached = ReleaseCheckResult(release=_trusted_release(), checked_at="old")
    checker = ReleaseUpdateChecker(WebSettings(update_github_api_base="https://api.github.test"))
    checker._cache = type("Cache", (), {  # noqa: SLF001 - explicit cache regression coverage
        "result": cached,
        "etag": '"etag"',
        "stored_at": time.monotonic(),
    })()
    fake = _FakeGitHubClient([_response(429)])
    with patch("pix_web.release_updates.httpx.AsyncClient", return_value=fake):
        result = asyncio.run(checker.check(force=True))

    assert result.release is not None
    assert result.error == "github_rate_limited"
    assert result.stale is True
    assert fake.calls[0][1]["If-None-Match"] == '"etag"'


def test_manifest_sha_mismatch_is_untrusted() -> None:
    manifest_bytes = json.dumps(_manifest()).encode()
    releases = [
        {
            "tag_name": "v9.0.0",
            "draft": False,
            "prerelease": False,
            "target_commitish": _COMMIT,
            "assets": [
                {
                    "id": 42,
                    "name": "pix-release-manifest.json",
                    "digest": f"sha256:{'0' * 64}",
                }
            ],
        }
    ]
    fake = _FakeGitHubClient(
        [_response(200, json_data=releases), _response(200, content=manifest_bytes)]
    )
    checker = ReleaseUpdateChecker(
        WebSettings(update_github_api_base="https://api.github.test")
    )
    with patch("pix_web.release_updates.httpx.AsyncClient", return_value=fake):
        result = asyncio.run(checker.check(force=True))
    assert result.release is None
    assert result.error == "manifest_sha256_mismatch"


class _FakeChecker:
    def __init__(self, result: ReleaseCheckResult) -> None:
        self.result = result
        self.forces: list[bool] = []

    async def check(self, *, force: bool = False) -> ReleaseCheckResult:
        self.forces.append(force)
        return self.result


class _FakeAgent:
    configured = True

    def __init__(self) -> None:
        self.apply_payload: dict | None = None
        self.rollback_key: str | None = None
        self.offline = False

    async def get_status(self) -> UpdaterAgentStatus:
        if self.offline:
            raise UpdateAgentError("agent_offline")
        return UpdaterAgentStatus(
            state="idle", current_version="1.0.0", can_rollback=True
        )

    async def apply(self, **payload) -> UpdaterAgentOperation:
        self.apply_payload = payload
        return UpdaterAgentOperation(
            operation_id="op-apply-1",
            action="apply",
            state="queued",
            target_version=payload["target_version"],
        )

    async def rollback(self, *, idempotency_key: str) -> UpdaterAgentOperation:
        self.rollback_key = idempotency_key
        return UpdaterAgentOperation(
            operation_id="op-rollback-1", action="rollback", state="queued"
        )

    async def get_operation(self, operation_id: str) -> UpdaterAgentOperation:
        return UpdaterAgentOperation(
            operation_id=operation_id, action="apply", state="running", target_version="9.0.0"
        )


class TestAdminUpdateApi:
    def setup_method(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'updates.db'}",
            storage_root=root / "outputs",
            auto_create_db=True,
            jwt_secret="update-control-test-secret-32-chars!!",
            public_base_url="https://testserver",
            update_apply_enabled=True,
            update_step_up_ttl_seconds=120,
            update_agent_url="http://updater.internal",
            update_agent_token_file=root / "agent.token",
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app, base_url="https://testserver")
        self.db = self.app.state.SessionLocal()
        self.admin = User(
            email="admin-update@example.com",
            password_hash=hash_password("correct-password"),
            display_name="Admin",
            role="admin",
            status="active",
        )
        self.user = User(
            email="user-update@example.com",
            password_hash=hash_password("correct-password"),
            display_name="User",
            role="user",
            status="active",
        )
        self.db.add_all([self.admin, self.user])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.user)
        self.release = _trusted_release()
        self.checker = _FakeChecker(ReleaseCheckResult(release=self.release))
        self.agent = _FakeAgent()
        self.app.state.release_update_checker = self.checker
        self.app.state.update_agent_client = self.agent

    def teardown_method(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    def _bearer(self, user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user, self.settings)}"}

    def _login_admin_cookie(self, *, origin: str = "https://testserver"):
        return self.client.post(
            "/auth/session/login",
            headers={"Origin": origin},
            json={"email": self.admin.email, "password": "correct-password"},
        )

    def _step_up(self, password: str = "correct-password", *, origin: str = "https://testserver"):
        return self.client.post(
            "/auth/session/step-up-update",
            headers={"Origin": origin},
            json={"password": password},
        )

    def _apply_payload(self) -> dict:
        return {
            "target_version": self.release.version,
            "expected_manifest_sha256": self.release.manifest_sha256,
            "idempotency_key": "update-request-001",
        }

    def test_status_requires_admin_and_read_only_survives_agent_offline(self) -> None:
        assert self.client.get("/admin/updates/status").status_code == 401
        assert (
            self.client.get("/admin/updates/status", headers=self._bearer(self.user)).status_code
            == 403
        )
        self.agent.offline = True
        response = self.client.get(
            "/admin/updates/status", headers=self._bearer(self.admin)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["latest_release"]["version"] == "9.0.0"
        assert body["update_available"] is True
        assert body["agent"]["available"] is False
        assert body["can_apply"] is False

    def test_step_up_requires_cookie_origin_admin_and_correct_password(self) -> None:
        bearer = self.client.post(
            "/auth/session/step-up-update",
            headers={**self._bearer(self.admin), "Origin": "https://testserver"},
            json={"password": "correct-password"},
        )
        assert bearer.status_code == 403

        assert self._login_admin_cookie().status_code == 200
        assert self._step_up(origin="https://evil.example").status_code == 403
        assert self._step_up(password="wrong-password").status_code == 401
        response = self._step_up()
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "pix_web_update_step_up=" in cookie
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=strict" in cookie
        assert "path=/" in cookie

    def test_apply_rejects_missing_expired_and_wrong_scope_step_up(self) -> None:
        assert self._login_admin_cookie().status_code == 200
        missing = self.client.post(
            "/admin/updates/apply",
            headers={"Origin": "https://testserver"},
            json=self._apply_payload(),
        )
        assert missing.status_code == 428

        now = datetime.now(timezone.utc)
        for scope, expires in (("update", now - timedelta(seconds=1)), ("file", now + timedelta(minutes=5))):
            token = jwt.encode(
                {
                    "sub": str(self.admin.id),
                    "scope": scope,
                    "token_type": "step_up",
                    "iat": int((now - timedelta(minutes=10)).timestamp()),
                    "exp": int(expires.timestamp()),
                },
                self.settings.jwt_secret,
                algorithm=self.settings.jwt_algorithm,
            )
            self.client.cookies.set(
                UPDATE_STEP_UP_COOKIE_NAME,
                token,
                domain="testserver.local",
                path="/",
            )
            response = self.client.post(
                "/admin/updates/apply",
                headers={"Origin": "https://testserver"},
                json=self._apply_payload(),
            )
            assert response.status_code == 403

    def test_apply_contract_matches_trusted_release_and_forwards_only_safe_fields(self) -> None:
        assert self._login_admin_cookie().status_code == 200
        assert self._step_up().status_code == 200
        extra = self.client.post(
            "/admin/updates/apply",
            headers={"Origin": "https://testserver"},
            json={**self._apply_payload(), "image": "attacker/image", "url": "https://evil"},
        )
        assert extra.status_code == 422

        mismatch = self.client.post(
            "/admin/updates/apply",
            headers={"Origin": "https://testserver"},
            json={**self._apply_payload(), "expected_manifest_sha256": "d" * 64},
        )
        assert mismatch.status_code == 409

        response = self.client.post(
            "/admin/updates/apply",
            headers={"Origin": "https://testserver"},
            json=self._apply_payload(),
        )
        assert response.status_code == 202, response.text
        assert response.json()["operation"]["operation_id"] == "op-apply-1"
        assert self.agent.apply_payload == {
            "target_version": "9.0.0",
            "expected_manifest_sha256": "c" * 64,
            "idempotency_key": "update-request-001",
        }

    def test_check_operation_and_rollback_contracts(self) -> None:
        admin_headers = self._bearer(self.admin)
        checked = self.client.post("/admin/updates/check", headers=admin_headers)
        assert checked.status_code == 200
        assert self.checker.forces[-1] is True
        operation = self.client.get(
            "/admin/updates/operations/op-1", headers=admin_headers
        )
        assert operation.status_code == 200
        assert operation.json()["state"] == "running"

        assert self._login_admin_cookie().status_code == 200
        assert self._step_up().status_code == 200
        rollback = self.client.post(
            "/admin/updates/rollback",
            headers={"Origin": "https://testserver"},
            json={"idempotency_key": "rollback-request-001"},
        )
        assert rollback.status_code == 202, rollback.text
        assert rollback.json()["operation"]["action"] == "rollback"
        assert self.agent.rollback_key == "rollback-request-001"
