from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix_web.metrics import task_performance_metrics
from pix_web.models import Base, GenerationJob, GenerationOutput, ImageProvider, User


class PerformanceMetricsProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        self.db: Session = self.Session()
        self.user = User(email="metric@example.com", password_hash="x", role="admin", status="active")
        self.db.add(self.user)
        self.db.add_all([
            ImageProvider(
                id="packy-primary",
                display_name="Packy #1",
                enabled=True,
                base_url="https://packy.example",
                priority=10,
                protocols=["openai_images"],
                models=[],
            ),
            ImageProvider(
                id="packy-backup",
                display_name="Packy #2",
                enabled=True,
                base_url="https://packy.example",
                priority=20,
                protocols=["openai_images"],
                models=[],
            ),
            ImageProvider(
                id="disabled-provider",
                display_name="停用供应商",
                enabled=False,
                base_url="https://disabled.example",
                priority=30,
                protocols=["openai_images"],
                models=[],
            ),
        ])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.tmp.cleanup()

    def _job(self, *, status: str, provider: str = "", diagnostics: dict | None = None) -> GenerationJob:
        now = datetime.now(timezone.utc) - timedelta(minutes=2)
        job = GenerationJob(
            user_id=self.user.id,
            client_request_id=f"job-{status}-{provider}-{len(list(self.db.scalars(select(GenerationJob))))}",
            job_type="asset",
            status=status,
            prompt="test",
            params_json={},
            provider=provider,
            error_diagnostics_json=diagnostics or {},
            created_at=now,
            started_at=now,
            finished_at=now + timedelta(seconds=10),
        )
        self.db.add(job)
        self.db.flush()
        return job

    def test_provider_success_rate_uses_added_provider_attempts(self) -> None:
        succeeded = self._job(status="succeeded", provider="packy-backup")
        run_dir = Path(self.tmp.name) / "job-1"
        run_dir.mkdir()
        meta_path = run_dir / "meta.json"
        meta_path.write_text(json.dumps({
            "image_gen": {
                "provider_history": [{
                    "attempts": [
                        {"provider": "packy-primary", "status": "failed"},
                        {"provider": "packy-backup", "status": "success"},
                    ]
                }]
            }
        }), encoding="utf-8")
        self.db.add(GenerationOutput(job_id=succeeded.id, run_dir=str(run_dir), meta_json_path=str(meta_path)))
        self._job(
            status="failed",
            provider="packy-primary",
            diagnostics={
                "provider_attempts": [
                    {"provider": "packy-primary", "status": "failed"},
                ]
            },
        )
        self.db.commit()

        metrics = task_performance_metrics(self.db, "24h")
        providers = {item["provider"]: item for item in metrics["providers"]}

        self.assertEqual(providers["packy-primary"]["display_name"], "Packy #1")
        self.assertEqual(providers["packy-primary"]["failed"], 2)
        self.assertEqual(providers["packy-primary"]["succeeded"], 0)
        self.assertEqual(providers["packy-primary"]["success_rate"], 0.0)
        self.assertEqual(providers["packy-backup"]["display_name"], "Packy #2")
        self.assertEqual(providers["packy-backup"]["succeeded"], 1)
        self.assertEqual(providers["packy-backup"]["failed"], 0)
        self.assertEqual(providers["packy-backup"]["success_rate"], 1.0)
        self.assertIn("disabled-provider", providers)
        self.assertFalse(providers["disabled-provider"]["enabled"])
        self.assertEqual(providers["disabled-provider"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
