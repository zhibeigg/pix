from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class OperationState(str, Enum):
    requested = "requested"
    preflight = "preflight"
    verifying = "verifying"
    pulling = "pulling"
    backing_up = "backing_up"
    stopping = "stopping"
    migrating = "migrating"
    deploying = "deploying"
    health_check = "health_check"
    succeeded = "succeeded"
    failed = "failed"
    rolling_back = "rolling_back"
    rolled_back = "rolled_back"
    rollback_failed = "rollback_failed"


TERMINAL_STATES = {
    OperationState.succeeded,
    OperationState.failed,
    OperationState.rolled_back,
    OperationState.rollback_failed,
}


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_version: str
    expected_manifest_sha256: str
    idempotency_key: str
    requested_by: str | None = Field(default=None, max_length=128)

    @field_validator("target_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("target_version must be A.B.C")
        return value

    @field_validator("expected_manifest_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        value = value.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("expected_manifest_sha256 must be lowercase hex")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency(cls, value: str) -> str:
        if not IDEMPOTENCY_RE.fullmatch(value):
            raise ValueError("invalid idempotency key")
        return value


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    requested_by: str | None = Field(default=None, max_length=128)

    _validate_key = field_validator("idempotency_key")(ApplyRequest.validate_idempotency.__func__)


class WorkflowMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    run_id: int = Field(gt=0)
    run_attempt: int = Field(gt=0)
    repository: str
    url: str


class ImageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    digest: str

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not DIGEST_RE.fullmatch(value):
            raise ValueError("image digest must be sha256:<64 lowercase hex>")
        return value


class RollbackPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported: bool = True
    automatic: bool = True
    restore_database_after_migration: bool = True


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    repository: str
    version: str
    tag: str
    commit: str
    workflow: WorkflowMetadata
    images: dict[Literal["backend", "frontend", "updater"], ImageManifest]
    alembic_head: str = Field(min_length=1, max_length=128)
    minimum_updater_version: str
    rollback_policy: RollbackPolicy
    generated_at: datetime

    @model_validator(mode="after")
    def validate_consistency(self) -> "ReleaseManifest":
        if not SEMVER_RE.fullmatch(self.version):
            raise ValueError("manifest version must be A.B.C")
        if self.tag != f"v{self.version}":
            raise ValueError("tag does not match version")
        if not SHA_RE.fullmatch(self.commit):
            raise ValueError("commit must be a lowercase 40-character SHA")
        if not SEMVER_RE.fullmatch(self.minimum_updater_version):
            raise ValueError("minimum_updater_version must be A.B.C")
        if set(self.images) != {"backend", "frontend", "updater"}:
            raise ValueError("manifest must contain exactly three images")
        if self.workflow.repository != self.repository:
            raise ValueError("workflow repository mismatch")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must include timezone")
        return self


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["apply", "rollback"]
    idempotency_key: str
    requested_by: str | None = None
    target_version: str | None = None
    expected_manifest_sha256: str | None = None
    state: OperationState = OperationState.requested
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    backup_file: str | None = None
    backup_sha256: str | None = None
    manifest_sha256: str | None = None
    transitions: list[OperationState] = Field(default_factory=lambda: [OperationState.requested])


class AgentStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    updater_version: str = ""
    current_version: str = ""
    can_rollback: bool = False
    active_operation_id: str | None = None


class AgentOperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    action: Literal["apply", "rollback"]
    state: str
    target_version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    transitions: list[str] = Field(default_factory=list)
    message: str = ""
    error: str | None = None

    @classmethod
    def from_operation(cls, operation: Operation) -> "AgentOperationResponse":
        return cls(
            operation_id=operation.id,
            action=operation.kind,
            state=operation.state.value,
            target_version=operation.target_version,
            created_at=operation.created_at,
            updated_at=operation.updated_at,
            transitions=[state.value for state in operation.transitions],
            error=operation.error,
        )


class PersistedState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: dict[str, Operation] = Field(default_factory=dict)
    idempotency: dict[str, str] = Field(default_factory=dict)
    active_operation_id: str | None = None
    current_version: str | None = None
    current_manifest_sha256: str | None = None
