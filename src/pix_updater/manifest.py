from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import httpx
from pix_updater import __version__
from pix_updater.config import UpdaterSettings
from pix_updater.models import ReleaseManifest


class ReleaseClient:
    def __init__(self, settings: UpdaterSettings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def fetch(self, version: str) -> tuple[bytes, dict, str]:
        repo = self.settings.repository
        tag = f"v{version}"
        encoded_tag = quote(tag, safe="")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers)
        try:
            release_response, commit_response, manifest_response = await __import__("asyncio").gather(
                client.get(f"https://api.github.com/repos/{repo}/releases/tags/{encoded_tag}"),
                client.get(f"https://api.github.com/repos/{repo}/commits/{encoded_tag}"),
                client.get(f"https://github.com/{repo}/releases/download/{encoded_tag}/pix-release-manifest.json"),
            )
            release_response.raise_for_status()
            commit_response.raise_for_status()
            manifest_response.raise_for_status()
            release = release_response.json()
            commit = commit_response.json()
            if release.get("tag_name") != tag or release.get("draft") or release.get("prerelease"):
                raise ValueError("release metadata is not a final matching release")
            return manifest_response.content, release, str(commit.get("sha", ""))
        finally:
            if owns_client:
                await client.aclose()


def validate_manifest(
    payload: bytes,
    *,
    settings: UpdaterSettings,
    target_version: str,
    expected_sha256: str,
    tagged_commit: str,
) -> tuple[ReleaseManifest, str]:
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("manifest SHA-256 does not match the caller expectation")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("manifest is not valid JSON") from exc
    manifest = ReleaseManifest.model_validate(raw)
    if manifest.repository != settings.repository:
        raise ValueError("manifest repository is not allowlisted")
    if manifest.version != target_version:
        raise ValueError("manifest target version mismatch")
    if manifest.commit != tagged_commit:
        raise ValueError("manifest commit does not match the release tag")
    for name, repository in settings.image_allowlist.items():
        if manifest.images[name].repository != repository:
            raise ValueError(f"manifest {name} image is not allowlisted")
    installed = tuple(int(part) for part in __version__.split("."))
    minimum = tuple(int(part) for part in manifest.minimum_updater_version.split("."))
    if installed < minimum:
        raise ValueError("installed updater is older than the manifest minimum")
    return manifest, actual_sha256


def manifest_file_name(state_dir: Path, operation_id: str) -> Path:
    return state_dir / "manifests" / f"{operation_id}.json"
