from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pix_updater.api import create_app
from pix_updater.commands import AsyncCommandRunner, CommandRejected
from pix_updater.config import UpdaterSettings
from pix_updater.manifest import validate_manifest
from pix_updater.models import ApplyRequest, Operation, OperationState, ReleaseManifest
from pix_updater.redaction import redact
from pix_updater.service import UpdateService


def make_settings(tmp_path: Path, *, enabled: bool = True) -> UpdaterSettings:
    deployment = tmp_path / "deployment"
    deployment.mkdir()
    compose = deployment / "compose.release.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    app_env = deployment / ".env.production"
    app_env.write_text("POSTGRES_PASSWORD=database-secret\n", encoding="utf-8")
    release_env = deployment / "release.env"
    release_env.write_text("PIX_RELEASE_VERSION=1.0.0\n", encoding="utf-8")
    token = tmp_path / "token"
    token.write_text("t" * 40, encoding="utf-8")
    return UpdaterSettings(
        enabled=enabled,
        compose_file=compose,
        deployment_root=deployment,
        app_env_file=app_env,
        release_env=release_env,
        state_dir=tmp_path / "state",
        backup_dir=tmp_path / "backups",
        log_dir=tmp_path / "logs",
        token_file=token,
        postgres_password="database-secret",
        minimum_free_bytes=0,
    )


def manifest_payload(settings: UpdaterSettings, version: str = "1.2.3") -> bytes:
    manifest = {
        "schema_version": 1,
        "repository": settings.repository,
        "version": version,
        "tag": f"v{version}",
        "commit": "a" * 40,
        "workflow": {
            "name": "Release",
            "run_id": 123,
            "run_attempt": 1,
            "repository": settings.repository,
            "url": "https://github.com/zhibeigg/pix/actions/runs/123",
        },
        "images": {
            name: {"repository": repository, "digest": "sha256:" + char * 64}
            for (name, repository), char in zip(settings.image_allowlist.items(), "123", strict=True)
        },
        "alembic_head": "0025_promo_links",
        "minimum_updater_version": "0.0.0",
        "rollback_policy": {"supported": True, "automatic": True, "restore_database_after_migration": True},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return (json.dumps(manifest, sort_keys=True) + "\n").encode()


def test_config_defaults_to_disabled_and_rejects_missing_files(tmp_path: Path) -> None:
    settings = UpdaterSettings(
        deployment_root=tmp_path,
        compose_file=tmp_path / "missing-compose.yml",
        release_env=tmp_path / "missing-release.env",
        state_dir=tmp_path / "state",
        backup_dir=tmp_path / "backup",
        log_dir=tmp_path / "logs",
        token_file=tmp_path / "missing-token",
    )
    errors = settings.readiness_errors()
    assert "PIX_UPDATER_ENABLED is false" in errors
    assert "PIX_UPDATER_POSTGRES_PASSWORD is missing" in errors
    assert any("compose file" in error for error in errors)
    assert any("release env" in error for error in errors)


def test_config_requires_complete_untagged_ghcr_repository() -> None:
    settings = UpdaterSettings(backend_image="ghcr.io/zhibeigg/pix-backend")
    assert settings.backend_image == "ghcr.io/zhibeigg/pix-backend"
    for value in (
        "https://attacker.example/ghcr.io/zhibeigg/pix-backend",
        "attacker.example/ghcr.io/zhibeigg/pix-backend",
        "ghcr.io/zhibeigg/pix-backend:latest",
        "ghcr.io/zhibeigg/pix-backend@sha256:" + "a" * 64,
    ):
        with pytest.raises(ValidationError):
            UpdaterSettings(backend_image=value)


def test_request_models_forbid_arbitrary_inputs() -> None:
    with pytest.raises(ValidationError):
        ApplyRequest.model_validate(
            {
                "target_version": "1.2.3",
                "expected_manifest_sha256": "a" * 64,
                "idempotency_key": "request-123",
                "command": "docker rm -f postgres",
            }
        )


def test_auth_uses_bearer_token_file(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/v1/status").status_code == 401
        assert client.get("/v1/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.get("/v1/status", headers={"Authorization": f"Bearer {'t' * 40}"})
        assert response.status_code == 200
        assert response.json()["state"] == "ready"
        assert response.json()["can_rollback"] is False


def test_manifest_validation_checks_sha_repo_commit_and_images(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    payload = manifest_payload(settings)
    digest = hashlib.sha256(payload).hexdigest()
    manifest, actual = validate_manifest(
        payload,
        settings=settings,
        target_version="1.2.3",
        expected_sha256=digest,
        tagged_commit="a" * 40,
    )
    assert isinstance(manifest, ReleaseManifest)
    assert actual == digest
    with pytest.raises(ValueError, match="SHA-256"):
        validate_manifest(
            payload,
            settings=settings,
            target_version="1.2.3",
            expected_sha256="0" * 64,
            tagged_commit="a" * 40,
        )


def test_command_runner_allowlist_rejects_shell_and_compose_exec() -> None:
    assert AsyncCommandRunner.validate(("docker", "pull", "ghcr.io/zhibeigg/pix@sha256:" + "a" * 64))
    assert AsyncCommandRunner.validate(("gh", "attestation", "verify", "manifest.json", "--repo", "zhibeigg/pix"))
    with pytest.raises(CommandRejected):
        AsyncCommandRunner.validate(("bash", "-c", "docker ps"))
    with pytest.raises(CommandRejected):
        AsyncCommandRunner.validate(("docker", "compose", "exec", "postgres", "sh"))


def test_state_transition_idempotency_and_rollback(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = make_settings(tmp_path)
        service = UpdateService(settings)
        await service.initialize()
        gate = asyncio.Event()

        async def stalled(_operation_id: str) -> None:
            await gate.wait()

        service._execute = stalled  # type: ignore[method-assign]
        request = ApplyRequest(
            target_version="1.2.3",
            expected_manifest_sha256="a" * 64,
            idempotency_key="request-123",
        )
        first = await service.request_apply(request)
        second = await service.request_apply(request)
        assert first.id == second.id
        assert service.state.active_operation_id == first.id
        gate.set()
        await asyncio.gather(*service._tasks)

        rollback = Operation(id="b" * 32, kind="rollback", idempotency_key="rollback-123")
        service.state.operations[rollback.id] = rollback

        async def deploy(*_args, **_kwargs) -> None:
            return None

        service._deploy_known_good = deploy  # type: ignore[method-assign]
        await service._rollback_to(rollback, b"PIX_RELEASE_VERSION=1.0.0\n", b"", None)
        assert rollback.transitions[-2:] == [OperationState.rolling_back, OperationState.rolled_back]

    asyncio.run(scenario())


def test_redaction_removes_tokens_passwords_and_database_urls() -> None:
    text = "Authorization: Bearer topsecret password=hunter2 postgresql://pix:dbpass@postgres/pix"
    cleaned = redact(text, ("topsecret",))
    assert "topsecret" not in cleaned
    assert "hunter2" not in cleaned
    assert "dbpass" not in cleaned
    assert cleaned.count("[REDACTED]") >= 3
