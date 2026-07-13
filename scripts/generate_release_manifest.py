from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def read_digest(path: Path) -> str:
    digest = path.read_text(encoding="utf-8").strip()
    if not DIGEST_RE.fullmatch(digest):
        raise ValueError(f"invalid digest in {path}")
    return digest


def generate_manifest(args: argparse.Namespace) -> dict:
    if not SEMVER_RE.fullmatch(args.version) or args.tag != f"v{args.version}":
        raise ValueError("tag/version mismatch")
    if not SHA_RE.fullmatch(args.commit):
        raise ValueError("commit must be a full lowercase SHA")
    if not SEMVER_RE.fullmatch(args.minimum_updater_version):
        raise ValueError("invalid minimum updater version")
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "repository": args.repository,
        "version": args.version,
        "tag": args.tag,
        "commit": args.commit,
        "workflow": {
            "name": args.workflow_name,
            "run_id": args.workflow_run_id,
            "run_attempt": args.workflow_run_attempt,
            "repository": args.repository,
            "url": args.workflow_url,
        },
        "images": {
            "backend": {"repository": args.backend_image, "digest": read_digest(args.backend_digest)},
            "frontend": {"repository": args.frontend_image, "digest": read_digest(args.frontend_digest)},
            "updater": {"repository": args.updater_image, "digest": read_digest(args.updater_digest)},
        },
        "alembic_head": args.alembic_head,
        "minimum_updater_version": args.minimum_updater_version,
        "rollback_policy": {
            "supported": True,
            "automatic": True,
            "restore_database_after_migration": True,
        },
        "generated_at": generated_at,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the signed Pix release manifest.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--workflow-url", required=True)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--frontend-image", required=True)
    parser.add_argument("--updater-image", required=True)
    parser.add_argument("--backend-digest", type=Path, required=True)
    parser.add_argument("--frontend-digest", type=Path, required=True)
    parser.add_argument("--updater-digest", type=Path, required=True)
    parser.add_argument("--alembic-head", required=True)
    parser.add_argument("--minimum-updater-version", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = generate_manifest(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
