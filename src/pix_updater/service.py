from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from pix_updater import __version__
from pix_updater.commands import AsyncCommandRunner
from pix_updater.config import UpdaterSettings
from pix_updater.manifest import ReleaseClient, manifest_file_name, validate_manifest
from pix_updater.models import (
    ApplyRequest,
    Operation,
    OperationState,
    PersistedState,
    ReleaseManifest,
    RollbackRequest,
    TERMINAL_STATES,
)
from pix_updater.redaction import redact
from pix_updater.storage import StateStore


class BusyError(RuntimeError):
    pass


class NotReadyError(RuntimeError):
    pass


class UpdateService:
    def __init__(
        self,
        settings: UpdaterSettings,
        *,
        runner: AsyncCommandRunner | None = None,
        release_client: ReleaseClient | None = None,
        health_client: httpx.AsyncClient | None = None,
        store: StateStore | None = None,
    ) -> None:
        self.settings = settings
        self.runner = runner or AsyncCommandRunner()
        self.release_client = release_client or ReleaseClient(settings)
        self.health_client = health_client
        self.store = store or StateStore(settings.state_dir)
        self.state = PersistedState()
        self._state_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    async def initialize(self) -> None:
        await self.store.initialize()
        self.state = await self.store.load()
        if self.state.current_version is None:
            try:
                release_env = (await self.store.read_bytes(self.settings.release_env)).decode("utf-8")
            except (OSError, UnicodeError):
                release_env = ""
            for line in release_env.splitlines():
                if line.startswith("PIX_RELEASE_VERSION="):
                    self.state.current_version = line.partition("=")[2].strip() or None
                elif line.startswith("PIX_RELEASE_MANIFEST_SHA256="):
                    self.state.current_manifest_sha256 = line.partition("=")[2].strip() or None
        if self.state.active_operation_id:
            operation = self.state.operations.get(self.state.active_operation_id)
            if operation and operation.state not in TERMINAL_STATES:
                operation.state = OperationState.failed
                operation.error = "agent restarted during operation; manual inspection required"
                operation.updated_at = datetime.now(timezone.utc)
                operation.transitions.append(OperationState.failed)
            self.state.active_operation_id = None
        await self.store.save(self.state)

    async def status(self) -> dict:
        readiness = self.settings.readiness_errors()
        active = self.state.operations.get(self.state.active_operation_id or "")
        state = active.state.value if active else (
            "ready" if not readiness else "disabled" if not self.settings.enabled else "not_ready"
        )
        return {
            "state": state,
            "updater_version": __version__,
            "current_version": self.state.current_version or "",
            "can_rollback": await self.store.has_previous_good(),
            "active_operation_id": active.id if active else None,
        }

    def get_operation(self, operation_id: str) -> Operation | None:
        return self.state.operations.get(operation_id)

    async def request_apply(self, request: ApplyRequest) -> Operation:
        return await self._request_operation(
            kind="apply",
            idempotency_key=request.idempotency_key,
            requested_by=request.requested_by,
            target_version=request.target_version,
            expected_manifest_sha256=request.expected_manifest_sha256,
        )

    async def request_rollback(self, request: RollbackRequest) -> Operation:
        if not await self.store.has_previous_good():
            raise NotReadyError("no previous known-good release is available")
        return await self._request_operation(
            kind="rollback",
            idempotency_key=request.idempotency_key,
            requested_by=request.requested_by,
        )

    async def _request_operation(
        self,
        *,
        kind: str,
        idempotency_key: str,
        requested_by: str | None,
        target_version: str | None = None,
        expected_manifest_sha256: str | None = None,
    ) -> Operation:
        errors = self.settings.readiness_errors()
        if errors:
            raise NotReadyError("; ".join(errors))
        async with self._state_lock:
            existing_id = self.state.idempotency.get(idempotency_key)
            if existing_id:
                existing = self.state.operations[existing_id]
                if (
                    existing.kind != kind
                    or existing.target_version != target_version
                    or existing.expected_manifest_sha256 != expected_manifest_sha256
                ):
                    raise ValueError("idempotency key was already used for different parameters")
                return existing
            active = self.state.operations.get(self.state.active_operation_id or "")
            if active and active.state not in TERMINAL_STATES:
                raise BusyError("another update operation is active")
            operation = Operation(
                id=uuid.uuid4().hex,
                kind=kind,
                idempotency_key=idempotency_key,
                requested_by=requested_by,
                target_version=target_version,
                expected_manifest_sha256=expected_manifest_sha256,
            )
            self.state.operations[operation.id] = operation
            self.state.idempotency[idempotency_key] = operation.id
            self.state.active_operation_id = operation.id
            await self.store.save(self.state)
        task = asyncio.create_task(self._execute(operation.id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return operation

    async def _execute(self, operation_id: str) -> None:
        async with self._operation_lock:
            operation = self.state.operations[operation_id]
            try:
                if operation.kind == "apply":
                    await self._apply(operation)
                else:
                    await self._manual_rollback(operation)
            except Exception as exc:
                await self._fail(operation, exc)
            finally:
                async with self._state_lock:
                    if self.state.active_operation_id == operation.id:
                        self.state.active_operation_id = None
                    await self.store.save(self.state)
                await self.store.prune(self.settings.backup_dir, "*.dump", self.settings.backup_retention)
                await self.store.prune(self.settings.log_dir, "*.jsonl", self.settings.log_retention)

    async def _transition(self, operation: Operation, state: OperationState, **updates: str | None) -> None:
        async with self._state_lock:
            operation.state = state
            operation.updated_at = datetime.now(timezone.utc)
            operation.transitions.append(state)
            for key, value in updates.items():
                setattr(operation, key, value)
            await self.store.save(self.state)
        await self.store.append_json_log(
            self.settings.log_dir,
            operation.id,
            {"time": operation.updated_at.isoformat(), "state": state.value},
        )

    def _compose(self, *args: str) -> tuple[str, ...]:
        return (
            "docker",
            "compose",
            "--project-name",
            self.settings.compose_project,
            "--file",
            str(self.settings.compose_file),
            "--env-file",
            str(self.settings.app_env_file),
            "--env-file",
            str(self.settings.release_env),
            *args,
        )

    async def _run(self, args: tuple[str, ...], *, timeout: float = 600, env: dict[str, str] | None = None):
        return await self.runner.run(
            args,
            cwd=self.settings.deployment_root,
            timeout=timeout,
            env=env,
            secrets=(self.settings.postgres_password,),
        )

    async def _apply(self, operation: Operation) -> None:
        assert operation.target_version and operation.expected_manifest_sha256
        old_env = await self.store.read_bytes(self.settings.release_env)
        old_manifest_path = self.store.last_good_dir / "manifest.json"
        old_manifest = await self.store.read_bytes(old_manifest_path) if old_manifest_path.exists() else b""
        backup_path: Path | None = None
        deployment_started = False
        migration_started = False
        manifest: ReleaseManifest | None = None
        manifest_payload = b""
        try:
            await self._transition(operation, OperationState.preflight)
            await self._preflight()

            await self._transition(operation, OperationState.verifying)
            manifest_payload, _release, tagged_commit = await self.release_client.fetch(operation.target_version)
            manifest_path = manifest_file_name(self.settings.state_dir, operation.id)
            await self.store.write_bytes(manifest_path, manifest_payload)
            await self._run(("gh", "attestation", "verify", str(manifest_path), "--repo", self.settings.repository))
            manifest, manifest_sha = validate_manifest(
                manifest_payload,
                settings=self.settings,
                target_version=operation.target_version,
                expected_sha256=operation.expected_manifest_sha256,
                tagged_commit=tagged_commit,
            )
            await self._transition(operation, OperationState.verifying, manifest_sha256=manifest_sha)
            for image in manifest.images.values():
                await self._run(("gh", "attestation", "verify", f"oci://{image.repository}@{image.digest}", "--repo", self.settings.repository))

            await self._transition(operation, OperationState.pulling)
            for image in manifest.images.values():
                await self._run(("docker", "pull", f"{image.repository}@{image.digest}"), timeout=1200)

            await self._transition(operation, OperationState.backing_up)
            backup_path = self.settings.backup_dir / f"pix-{operation.id}.dump"
            await asyncio.to_thread(self.settings.backup_dir.mkdir, parents=True, exist_ok=True)
            command_env = dict(os.environ)
            command_env["PGPASSWORD"] = self.settings.postgres_password
            await self._run(
                (
                    "pg_dump",
                    "--format=custom",
                    "--file",
                    str(backup_path),
                    "--host",
                    self.settings.postgres_host,
                    "--port",
                    str(self.settings.postgres_port),
                    "--username",
                    self.settings.postgres_user,
                    self.settings.postgres_db,
                ),
                timeout=1800,
                env=command_env,
            )
            backup_sha = await asyncio.to_thread(lambda: hashlib.sha256(backup_path.read_bytes()).hexdigest())
            await self._transition(operation, OperationState.backing_up, backup_file=str(backup_path), backup_sha256=backup_sha)

            new_env = self._release_env(manifest, manifest_sha)
            await self.store.write_bytes(self.settings.state_dir / "operations" / operation.id / "previous-release.env", old_env)
            if old_manifest:
                await self.store.write_bytes(self.settings.state_dir / "operations" / operation.id / "previous-manifest.json", old_manifest)
            await self.store.write_bytes(self.settings.release_env, new_env)
            deployment_started = True

            await self._transition(operation, OperationState.stopping)
            await self._run(self._compose("stop", "worker", "api", "web"))

            await self._transition(operation, OperationState.migrating)
            migration_started = True
            await self._run(self._compose("run", "--rm", "migrate"), timeout=1800)

            await self._transition(operation, OperationState.deploying)
            await self._run(self._compose("up", "--detach", "api"), timeout=1200)

            await self._transition(operation, OperationState.health_check)
            await self._wait_for_health(manifest.version)

            await self._transition(operation, OperationState.deploying)
            await self._run(self._compose("up", "--detach", "web", "worker"), timeout=1200)
            await self._verify_compose_services()

            await self.store.snapshot_good(new_env, manifest_payload)
            self.state.current_version = manifest.version
            self.state.current_manifest_sha256 = manifest_sha
            await self._transition(operation, OperationState.succeeded)
        except Exception as exc:
            if deployment_started and manifest and manifest.rollback_policy.automatic:
                await self._transition(
                    operation,
                    OperationState.failed,
                    error=redact(str(exc), (self.settings.postgres_password,))[:2000],
                )
                await self._rollback_to(
                    operation,
                    old_env,
                    old_manifest,
                    backup_path if migration_started and manifest.rollback_policy.restore_database_after_migration else None,
                )
                return
            raise

    async def _preflight(self) -> None:
        free = await asyncio.to_thread(lambda: shutil.disk_usage(self.settings.backup_dir.parent).free)
        if free < self.settings.minimum_free_bytes:
            raise RuntimeError("insufficient free disk space")
        await self._run(("docker", "info", "--format", "{{json .ServerVersion}}"), timeout=60)
        await self._run(("docker", "compose", "version"), timeout=60)
        await self._run(self._compose("config", "--quiet"), timeout=60)

    def _release_env(self, manifest: ReleaseManifest, manifest_sha: str) -> bytes:
        values = {
            "PIX_BACKEND_IMAGE": f"{manifest.images['backend'].repository}@{manifest.images['backend'].digest}",
            "PIX_FRONTEND_IMAGE": f"{manifest.images['frontend'].repository}@{manifest.images['frontend'].digest}",
            "PIX_UPDATER_IMAGE": f"{manifest.images['updater'].repository}@{manifest.images['updater'].digest}",
            "PIX_RELEASE_VERSION": manifest.version,
            "PIX_RELEASE_COMMIT": manifest.commit,
            "PIX_RELEASE_MANIFEST_SHA256": manifest_sha,
        }
        return ("\n".join(f"{key}={value}" for key, value in values.items()) + "\n").encode()

    async def _wait_for_health(self, version: str) -> None:
        owns_client = self.health_client is None
        client = self.health_client or httpx.AsyncClient(timeout=5)
        try:
            for attempt in range(self.settings.health_attempts):
                try:
                    response = await client.get(self.settings.health_url)
                    data = response.json()
                    if response.is_success and data.get("ok") == "true" and data.get("version") == version:
                        return
                except (httpx.HTTPError, ValueError):
                    pass
                if attempt + 1 < self.settings.health_attempts:
                    await asyncio.sleep(self.settings.health_interval_seconds)
        finally:
            if owns_client:
                await client.aclose()
        raise RuntimeError("API health check did not report the target version")

    async def _verify_compose_services(self) -> None:
        result = await self._run(self._compose("ps", "--format", "json", "api", "web", "worker", "postgres", "redis"))
        text = result.stdout.strip()
        if not text:
            raise RuntimeError("docker compose ps returned no services")
        records = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines()]
        expected = {"api", "web", "worker", "postgres", "redis"}
        healthy: set[str] = set()
        for record in records:
            service = str(record.get("Service", ""))
            state = str(record.get("State", "")).lower()
            health = str(record.get("Health", "")).lower()
            if service in expected and state == "running" and health not in {"unhealthy", "starting"}:
                healthy.add(service)
        if healthy != expected:
            raise RuntimeError(f"compose services not healthy: {sorted(expected - healthy)}")

    async def _manual_rollback(self, operation: Operation) -> None:
        env_payload, manifest_payload = await self.store.previous_good()
        manifest = ReleaseManifest.model_validate_json(manifest_payload)
        await self._transition(operation, OperationState.rolling_back)
        await self._deploy_known_good(env_payload, restore_path=None, expected_version=manifest.version)
        await self.store.snapshot_good(env_payload, manifest_payload)
        self.state.current_version = manifest.version
        self.state.current_manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
        await self._transition(operation, OperationState.rolled_back)

    async def _rollback_to(
        self,
        operation: Operation,
        env_payload: bytes,
        manifest_payload: bytes,
        restore_path: Path | None,
    ) -> None:
        try:
            await self._transition(operation, OperationState.rolling_back)
            expected_version = ReleaseManifest.model_validate_json(manifest_payload).version if manifest_payload else None
            await self._deploy_known_good(env_payload, restore_path=restore_path, expected_version=expected_version)
            await self._transition(operation, OperationState.rolled_back)
        except Exception as exc:
            await self._transition(operation, OperationState.rollback_failed, error=redact(str(exc), (self.settings.postgres_password,)))

    async def _deploy_known_good(self, env_payload: bytes, *, restore_path: Path | None, expected_version: str | None) -> None:
        await self.store.write_bytes(self.settings.release_env, env_payload)
        await self._run(self._compose("stop", "worker", "api", "web"))
        if restore_path:
            command_env = dict(os.environ)
            command_env["PGPASSWORD"] = self.settings.postgres_password
            await self._run(
                (
                    "pg_restore",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-privileges",
                    "--host",
                    self.settings.postgres_host,
                    "--port",
                    str(self.settings.postgres_port),
                    "--username",
                    self.settings.postgres_user,
                    "--dbname",
                    self.settings.postgres_db,
                    str(restore_path),
                ),
                timeout=1800,
                env=command_env,
            )
        await self._run(self._compose("up", "--detach", "api"), timeout=1200)
        if expected_version:
            await self._wait_for_health(expected_version)
        await self._run(self._compose("up", "--detach", "web", "worker"), timeout=1200)
        await self._verify_compose_services()

    async def _fail(self, operation: Operation, exc: Exception) -> None:
        if operation.state in {OperationState.rolled_back, OperationState.rollback_failed}:
            return
        message = redact(str(exc), (self.settings.postgres_password,))[:2000]
        await self._transition(operation, OperationState.failed, error=message)
