from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _absolute(path: Path) -> Path:
    # Windows treats container-style /deployment as drive-relative (anchor="\\").
    # Accept a rooted anchor so the same secure container defaults can be imported in tests.
    if not path.is_absolute() and path.anchor not in {"/", "\\"}:
        raise ValueError("path must be absolute")
    return path


AbsolutePath = Annotated[Path, AfterValidator(_absolute)]


class UpdaterSettings(BaseSettings):
    """Environment-only updater configuration; apply is disabled by default."""

    model_config = SettingsConfigDict(env_prefix="PIX_UPDATER_", extra="ignore")

    enabled: bool = False
    repository: str = "zhibeigg/pix"
    backend_image: str = "ghcr.io/zhibeigg/pix-backend"
    frontend_image: str = "ghcr.io/zhibeigg/pix-web"
    updater_image: str = "ghcr.io/zhibeigg/pix-updater"
    compose_file: AbsolutePath = Path("/deployment/compose.release.yml")
    compose_project: str = "pix"
    deployment_root: AbsolutePath = Path("/deployment")
    app_env_file: AbsolutePath = Path("/deployment/.env.production")
    release_env: AbsolutePath = Path("/deployment/release.env")
    state_dir: AbsolutePath = Path("/var/lib/pix-updater/state")
    backup_dir: AbsolutePath = Path("/var/lib/pix-updater/backups")
    log_dir: AbsolutePath = Path("/var/lib/pix-updater/logs")
    token_file: AbsolutePath = Path("/run/secrets/pix_updater_token")
    health_url: str = "http://api:8000/health"
    backup_retention: int = Field(default=5, ge=1, le=30)
    log_retention: int = Field(default=20, ge=1, le=200)
    health_attempts: int = Field(default=60, ge=1, le=300)
    health_interval_seconds: float = Field(default=2.0, ge=0.1, le=30)
    minimum_free_bytes: int = Field(default=2_147_483_648, ge=0)
    postgres_host: str = "postgres"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_user: str = "pix"
    postgres_db: str = "pix"
    postgres_password: str = ""

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        parts = value.split("/")
        if len(parts) != 2 or not all(part.replace("-", "").isalnum() for part in parts):
            raise ValueError("repository must be owner/name")
        return value

    @field_validator("backend_image", "frontend_image", "updater_image")
    @classmethod
    def validate_image(cls, value: str) -> str:
        if not value.startswith("ghcr.io/") or "@" in value or ":" in value:
            raise ValueError("allowlisted image must be an untagged GHCR repository")
        return value

    @field_validator("compose_project")
    @classmethod
    def validate_project(cls, value: str) -> str:
        if not value or not all(char.isalnum() or char in "_-" for char in value):
            raise ValueError("invalid compose project")
        return value

    @field_validator("health_url")
    @classmethod
    def validate_health_url(cls, value: str) -> str:
        if value != "http://api:8000/health":
            raise ValueError("health URL must use the internal API service")
        return value

    @property
    def image_allowlist(self) -> dict[str, str]:
        return {
            "backend": self.backend_image,
            "frontend": self.frontend_image,
            "updater": self.updater_image,
        }

    def readiness_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.enabled:
            errors.append("PIX_UPDATER_ENABLED is false")
        if not self.postgres_password:
            errors.append("PIX_UPDATER_POSTGRES_PASSWORD is missing")
        for path, label in (
            (self.deployment_root, "deployment root"),
            (self.compose_file, "compose file"),
            (self.app_env_file, "application env"),
            (self.release_env, "release env"),
            (self.token_file, "token file"),
        ):
            if not path.exists():
                errors.append(f"{label} is missing")
        try:
            self.compose_file.relative_to(self.deployment_root)
            self.app_env_file.relative_to(self.deployment_root)
            self.release_env.relative_to(self.deployment_root)
        except ValueError:
            errors.append("compose file and env files must be under deployment root")
        return errors
