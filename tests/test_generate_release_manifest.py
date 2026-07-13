from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_release_manifest.py"
SPEC = importlib.util.spec_from_file_location("generate_release_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_args(tmp_path: Path) -> argparse.Namespace:
    digest_paths = {}
    for name, char in zip(("backend", "frontend", "updater"), "123", strict=True):
        path = tmp_path / f"{name}.digest"
        path.write_text("sha256:" + char * 64 + "\n", encoding="utf-8")
        digest_paths[name] = path
    return argparse.Namespace(
        repository="zhibeigg/pix",
        version="1.2.3",
        tag="v1.2.3",
        commit="a" * 40,
        workflow_name="Release",
        workflow_run_id=123,
        workflow_run_attempt=1,
        workflow_url="https://github.com/zhibeigg/pix/actions/runs/123",
        backend_image="ghcr.io/zhibeigg/pix-backend",
        frontend_image="ghcr.io/zhibeigg/pix-web",
        updater_image="ghcr.io/zhibeigg/pix-updater",
        backend_digest=digest_paths["backend"],
        frontend_digest=digest_paths["frontend"],
        updater_digest=digest_paths["updater"],
        alembic_head="0025_promo_links",
        minimum_updater_version="1.2.3",
        generated_at="2026-07-11T00:00:00Z",
        output=tmp_path / "manifest.json",
    )


def test_generate_manifest_is_complete_and_deterministic(tmp_path: Path) -> None:
    manifest = MODULE.generate_manifest(make_args(tmp_path))
    assert manifest["schema_version"] == 1
    assert manifest["tag"] == "v1.2.3"
    assert set(manifest["images"]) == {"backend", "frontend", "updater"}
    assert manifest["rollback_policy"]["supported"] is True
    assert manifest["rollback_policy"]["restore_database_after_migration"] is True
    assert manifest["generated_at"] == "2026-07-11T00:00:00Z"


def test_generate_manifest_rejects_bad_digest_and_tag(tmp_path: Path) -> None:
    args = make_args(tmp_path)
    args.backend_digest.write_text("latest\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid digest"):
        MODULE.generate_manifest(args)
    args = make_args(tmp_path)
    args.tag = "v9.9.9"
    with pytest.raises(ValueError, match="tag/version"):
        MODULE.generate_manifest(args)
