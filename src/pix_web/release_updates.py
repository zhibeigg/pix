"""GitHub release discovery and trusted Pix release manifest validation."""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx

from pix_web.config import WebSettings

_MANIFEST_ASSET_NAME = "pix-release-manifest.json"
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_ALEMBIC_HEAD_RE = re.compile(r"^[A-Za-z0-9_]+$")
_IMAGE_COMPONENTS = frozenset({"backend", "frontend", "updater"})
_ROLLBACK_ALLOWED = frozenset({"allowed", "automatic", "safe", "supported"})
_ROLLBACK_BLOCKED = frozenset({"forbidden", "manual", "none", "unsupported"})
_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_NOTES_CHARS = 1200
_GITHUB_ASSET_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_GITHUB_ASSET_REDIRECTS = 3


@dataclass(frozen=True)
class TrustedRelease:
    version: str
    tag: str
    commit: str
    notes: str
    manifest_sha256: str
    alembic_head: str
    rollback_supported: bool
    trusted: bool = True


@dataclass(frozen=True)
class ReleaseCheckResult:
    release: TrustedRelease | None = None
    error: str | None = None
    checked_at: str = ""
    from_cache: bool = False
    stale: bool = False


@dataclass
class _CacheEntry:
    result: ReleaseCheckResult
    etag: str | None
    stored_at: float


class ManifestValidationError(ValueError):
    """Release manifest cannot be trusted."""


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse an exact A.B.C version without accepting suffixes or omitted components."""
    match = _VERSION_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("版本号必须严格符合 A.B.C")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _parse_tag(value: str) -> tuple[int, int, int]:
    match = _TAG_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("发布标签必须严格符合 A.B.C 或 vA.B.C")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer_version(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trusted_github_asset_url(value: str) -> bool:
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        return False
    return bool(
        parts.scheme == "https"
        and parts.username is None
        and parts.password is None
        and port in {None, 443}
        and (
            host == "github.com"
            or host.endswith(".github.com")
            or host.endswith(".githubusercontent.com")
        )
    )


def _plain_notes(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[`*_>#~|]", " ", text)
    text = " ".join(text.split())
    return text[:_MAX_NOTES_CHARS]


def _strict_dict(value: Any, *, name: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ManifestValidationError(f"{name} 必须为对象")
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(allowed):
        raise ManifestValidationError(f"{name} 字段不符合发布清单 schema")
    return value


def _normalize_digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str):
        raise ManifestValidationError(f"{name} digest 缺失")
    digest = value.strip().lower()
    if digest.startswith("sha256:"):
        digest = digest[7:]
    if _SHA256_RE.fullmatch(digest) is None:
        raise ManifestValidationError(f"{name} digest 非法")
    return digest


def _allowed_image_repositories(repository: str, component: str) -> set[str]:
    owner, project = repository.lower().split("/", 1)
    names = {component}
    if component == "frontend":
        names.add("web")
    return {
        image
        for name in names
        for image in (
            f"ghcr.io/{owner}/{project}-{name}",
            f"ghcr.io/{owner}/{project}/{name}",
            f"docker.io/{owner}/{project}-{name}",
            f"{owner}/{project}-{name}",
        )
    }


def _validate_image(component: str, value: Any, repository: str) -> None:
    if isinstance(value, str):
        image_ref = value.strip().lower()
        if "@sha256:" not in image_ref:
            raise ManifestValidationError(f"{component} 镜像必须固定 sha256 digest")
        image_repository, digest = image_ref.rsplit("@sha256:", 1)
    else:
        item = _strict_dict(
            value,
            name=f"images.{component}",
            allowed={"image", "repository", "digest"},
            required={"digest"},
        )
        image_value = item.get("image", item.get("repository"))
        if not isinstance(image_value, str) or not image_value.strip():
            raise ManifestValidationError(f"images.{component} 镜像名缺失")
        image_repository = image_value.strip().lower()
        digest = _normalize_digest(item["digest"], name=f"images.{component}")
        if "@sha256:" in image_repository:
            embedded_repository, embedded_digest = image_repository.rsplit("@sha256:", 1)
            if _normalize_digest(embedded_digest, name=f"images.{component}") != digest:
                raise ManifestValidationError(f"images.{component} digest 不一致")
            image_repository = embedded_repository
    if image_repository not in _allowed_image_repositories(repository, component):
        raise ManifestValidationError(f"images.{component} 不在镜像 allowlist")
    _normalize_digest(digest, name=f"images.{component}")


def _validate_workflow(value: Any, repository: str) -> None:
    item = _strict_dict(
        value,
        name="workflow",
        allowed={"name", "run_id", "run_attempt", "repository", "url"},
        required={"name", "run_id", "run_attempt", "repository", "url"},
    )
    if item["repository"] != repository:
        raise ManifestValidationError("workflow repository 不匹配")
    if not isinstance(item["name"], str) or not item["name"].strip():
        raise ManifestValidationError("workflow name 非法")
    if type(item["run_id"]) is not int or item["run_id"] <= 0:
        raise ManifestValidationError("workflow run_id 非法")
    if type(item["run_attempt"]) is not int or item["run_attempt"] <= 0:
        raise ManifestValidationError("workflow run_attempt 非法")
    if not isinstance(item["url"], str) or not item["url"].startswith(
        f"https://github.com/{repository}/actions/runs/"
    ):
        raise ManifestValidationError("workflow url 非法")


def _validate_rollback_policy(value: Any) -> bool:
    item = _strict_dict(
        value,
        name="rollback_policy",
        allowed={"supported", "automatic", "restore_database_after_migration"},
        required={"supported", "automatic", "restore_database_after_migration"},
    )
    if any(type(item[key]) is not bool for key in item):
        raise ManifestValidationError("rollback_policy 字段必须为布尔值")
    return bool(item["supported"])


def validate_release_manifest(
    payload: Any,
    *,
    repository: str,
    tag: str,
    version: str,
    commit: str,
) -> tuple[str, bool]:
    """Validate the signed release manifest shared by the API and update agent."""
    item = _strict_dict(
        payload,
        name="manifest",
        allowed={
            "schema_version",
            "repository",
            "version",
            "tag",
            "commit",
            "workflow",
            "images",
            "alembic_head",
            "minimum_updater_version",
            "rollback_policy",
            "generated_at",
        },
        required={
            "schema_version",
            "repository",
            "version",
            "tag",
            "commit",
            "workflow",
            "images",
            "alembic_head",
            "minimum_updater_version",
            "rollback_policy",
            "generated_at",
        },
    )
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise ManifestValidationError("不支持的发布清单 schema_version")
    if item["repository"] != repository:
        raise ManifestValidationError("发布清单 repository 不匹配")
    if not isinstance(item["tag"], str) or item["tag"] != tag:
        raise ManifestValidationError("发布清单 tag 不匹配")
    if not isinstance(item["version"], str) or item["version"] != version:
        raise ManifestValidationError("发布清单 version 不匹配")
    parse_version(item["version"])
    minimum_updater_version = item["minimum_updater_version"]
    if not isinstance(minimum_updater_version, str):
        raise ManifestValidationError("minimum_updater_version 非法")
    parse_version(minimum_updater_version)
    manifest_commit = item["commit"]
    if not isinstance(manifest_commit, str) or manifest_commit.lower() != commit.lower():
        raise ManifestValidationError("发布清单 commit 不匹配")
    if _COMMIT_RE.fullmatch(manifest_commit.lower()) is None:
        raise ManifestValidationError("发布清单 commit 非法")
    _validate_workflow(item["workflow"], repository)
    images = _strict_dict(
        item["images"],
        name="images",
        allowed=set(_IMAGE_COMPONENTS),
        required=set(_IMAGE_COMPONENTS),
    )
    for component in sorted(_IMAGE_COMPONENTS):
        _validate_image(component, images[component], repository)
    alembic_head = item["alembic_head"]
    if not isinstance(alembic_head, str) or _ALEMBIC_HEAD_RE.fullmatch(alembic_head) is None:
        raise ManifestValidationError("Alembic head 非法")
    generated_at = item["generated_at"]
    if not isinstance(generated_at, str):
        raise ManifestValidationError("generated_at 非法")
    try:
        parsed_generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestValidationError("generated_at 非法") from exc
    if parsed_generated_at.tzinfo is None:
        raise ManifestValidationError("generated_at 必须包含时区")
    return alembic_head, _validate_rollback_policy(item["rollback_policy"])


class ReleaseUpdateChecker:
    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self._cache: _CacheEntry | None = None
        self._lock = asyncio.Lock()

    def _releases_path(self) -> str:
        repository = quote(self.settings.update_repository, safe="/")
        return f"{self.settings.update_github_api_base}/repos/{repository}/releases?per_page=30"

    def _asset_path(self, asset_id: int) -> str:
        repository = quote(self.settings.update_repository, safe="/")
        return f"{self.settings.update_github_api_base}/repos/{repository}/releases/assets/{asset_id}"

    def _commit_path(self, tag: str) -> str:
        repository = quote(self.settings.update_repository, safe="/")
        return f"{self.settings.update_github_api_base}/repos/{repository}/commits/{quote(tag, safe='')}"

    def _fresh_cache(self) -> ReleaseCheckResult | None:
        cache = self._cache
        if cache is None:
            return None
        if time.monotonic() - cache.stored_at > self.settings.update_cache_ttl_seconds:
            return None
        return replace(cache.result, from_cache=True)

    def _failure(self, error: str) -> ReleaseCheckResult:
        if self._cache is not None and self._cache.result.release is not None:
            return replace(
                self._cache.result,
                error=error,
                from_cache=True,
                stale=True,
                checked_at=_utc_now_text(),
            )
        return ReleaseCheckResult(error=error, checked_at=_utc_now_text())

    async def check(self, *, force: bool = False) -> ReleaseCheckResult:
        if not self.settings.update_check_enabled:
            return ReleaseCheckResult(error="version_check_disabled", checked_at=_utc_now_text())
        if not force and (cached := self._fresh_cache()) is not None:
            return cached
        async with self._lock:
            if not force and (cached := self._fresh_cache()) is not None:
                return cached
            return await self._request_release()

    async def _request_release(self) -> ReleaseCheckResult:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "pix-forge-update-checker",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._cache is not None and self._cache.etag:
            headers["If-None-Match"] = self._cache.etag
        timeout = httpx.Timeout(self.settings.update_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.get(self._releases_path(), headers=headers)
                if response.status_code == 304 and self._cache is not None:
                    self._cache.stored_at = time.monotonic()
                    refreshed = replace(
                        self._cache.result,
                        checked_at=_utc_now_text(),
                        from_cache=True,
                        stale=False,
                        error=None,
                    )
                    self._cache.result = refreshed
                    return refreshed
                if response.status_code in {403, 429}:
                    return self._failure("github_rate_limited")
                response.raise_for_status()
                releases = response.json()
                selected = self._select_release(releases)
                if selected is None:
                    result = ReleaseCheckResult(checked_at=_utc_now_text())
                else:
                    result = await self._trusted_release(client, selected)
                self._cache = _CacheEntry(
                    result=result,
                    etag=response.headers.get("etag"),
                    stored_at=time.monotonic(),
                )
                return result
        except (httpx.TimeoutException, httpx.NetworkError):
            return self._failure("github_unavailable")
        except (httpx.HTTPStatusError, ValueError, TypeError):
            return self._failure("invalid_github_response")

    def _select_release(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, list):
            raise ValueError("GitHub releases response must be a list")
        candidates: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
        for release in value:
            if not isinstance(release, dict):
                raise ValueError("GitHub release entry must be an object")
            if release.get("draft") is not False:
                continue
            prerelease = release.get("prerelease")
            if not isinstance(prerelease, bool):
                raise ValueError("GitHub prerelease flag must be boolean")
            if self.settings.update_channel == "stable" and prerelease:
                continue
            tag = release.get("tag_name")
            if not isinstance(tag, str):
                raise ValueError("GitHub release tag missing")
            try:
                parsed = _parse_tag(tag)
            except ValueError:
                continue
            candidates.append((parsed, release))
        return max(candidates, key=lambda entry: entry[0])[1] if candidates else None

    async def _resolve_commit(self, client: httpx.AsyncClient, release: dict[str, Any], tag: str) -> str:
        target = release.get("target_commitish")
        if isinstance(target, str) and _COMMIT_RE.fullmatch(target.lower()):
            return target.lower()
        response = await client.get(
            self._commit_path(tag),
            headers={"Accept": "application/vnd.github+json", "User-Agent": "pix-forge-update-checker"},
        )
        response.raise_for_status()
        payload = response.json()
        commit = payload.get("sha") if isinstance(payload, dict) else None
        if not isinstance(commit, str) or _COMMIT_RE.fullmatch(commit.lower()) is None:
            raise ValueError("GitHub commit response invalid")
        return commit.lower()

    async def _download_manifest_asset(
        self, client: httpx.AsyncClient, asset_id: int
    ) -> httpx.Response:
        url = self._asset_path(asset_id)
        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": "pix-forge-update-checker",
        }
        for redirect_count in range(_MAX_GITHUB_ASSET_REDIRECTS + 1):
            response = await client.get(url, headers=headers)
            if response.status_code not in _GITHUB_ASSET_REDIRECT_CODES:
                response.raise_for_status()
                return response
            if redirect_count >= _MAX_GITHUB_ASSET_REDIRECTS:
                raise ValueError("GitHub release asset redirected too many times")
            location = response.headers.get("location")
            if not location:
                raise ValueError("GitHub release asset redirect missing location")
            target = urljoin(url, location)
            if not _trusted_github_asset_url(target):
                raise ValueError("GitHub release asset redirected to an untrusted host")
            url = target
        raise ValueError("GitHub release asset download failed")

    async def _trusted_release(
        self, client: httpx.AsyncClient, release: dict[str, Any]
    ) -> ReleaseCheckResult:
        tag = release["tag_name"]
        version = ".".join(str(part) for part in _parse_tag(tag))
        commit = await self._resolve_commit(client, release, tag)
        assets = release.get("assets")
        if not isinstance(assets, list):
            raise ValueError("GitHub release assets missing")
        manifest_assets = [
            asset
            for asset in assets
            if isinstance(asset, dict) and asset.get("name") == _MANIFEST_ASSET_NAME
        ]
        if len(manifest_assets) != 1:
            return ReleaseCheckResult(error="manifest_asset_missing", checked_at=_utc_now_text())
        asset = manifest_assets[0]
        asset_id = asset.get("id")
        if type(asset_id) is not int or asset_id <= 0:
            return ReleaseCheckResult(error="manifest_asset_invalid", checked_at=_utc_now_text())
        expected_digest = asset.get("digest")
        try:
            expected_sha256 = _normalize_digest(expected_digest, name="manifest")
        except ManifestValidationError:
            return ReleaseCheckResult(error="manifest_digest_missing", checked_at=_utc_now_text())
        response = await self._download_manifest_asset(client, asset_id)
        content = response.content
        if not content or len(content) > _MAX_MANIFEST_BYTES:
            return ReleaseCheckResult(error="manifest_invalid", checked_at=_utc_now_text())
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != expected_sha256:
            return ReleaseCheckResult(error="manifest_sha256_mismatch", checked_at=_utc_now_text())
        try:
            payload = response.json()
            alembic_head, rollback_supported = validate_release_manifest(
                payload,
                repository=self.settings.update_repository,
                tag=tag,
                version=version,
                commit=commit,
            )
        except (ValueError, TypeError):
            return ReleaseCheckResult(error="manifest_invalid", checked_at=_utc_now_text())
        trusted = TrustedRelease(
            version=version,
            tag=tag,
            commit=commit,
            notes=_plain_notes(release.get("body")),
            manifest_sha256=actual_sha256,
            alembic_head=alembic_head,
            rollback_supported=rollback_supported,
        )
        return ReleaseCheckResult(release=trusted, checked_at=_utc_now_text())
