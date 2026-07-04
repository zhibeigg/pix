from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pix_web.config import WebSettings
from pix_web.models import Base, GenerationJob, GenerationOutput, User
from pix_web.routers.jobs import bulk_download_jobs
from pix_web.schemas import JobBulkDownloadRequest


class BulkDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.settings = WebSettings(storage_root=self.root)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()
        self.user = User(email="user@example.com", password_hash="x", display_name="user", role="user", status="active")
        self.other = User(email="other@example.com", password_hash="x", display_name="other", role="user", status="active")
        self.db.add_all([self.user, self.other])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.other)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _asset_job(self, index: int, *, owner: User | None = None, status: str = "succeeded", with_files: bool = True) -> GenerationJob:
        owner = owner or self.user
        run_dir = self.root / f"run-{index}"
        run_dir.mkdir(parents=True, exist_ok=True)
        source = run_dir / "01_source.png"
        pixelized = run_dir / "03_pixelized.png"
        meta = run_dir / "meta.json"
        if with_files:
            source.write_bytes(b"source-bytes")
            pixelized.write_bytes(b"pixel-bytes")
            meta.write_text(json.dumps({"outputs": {}}), encoding="utf-8")
        job = GenerationJob(
            user_id=owner.id,
            client_request_id=f"job-{index}",
            job_type="asset",
            status=status,
            prompt=f"asset {index}",
            params_json={"asset": {"name": f"asset{index}"}},
        )
        self.db.add(job)
        self.db.flush()
        output = GenerationOutput(
            job_id=job.id,
            run_dir=str(run_dir),
            source_path=str(source),
            pixelized_path=str(pixelized),
            meta_json_path=str(meta),
        )
        self.db.add(output)
        self.db.flush()
        return job

    def _zip_names(self, response) -> list[str]:
        with ZipFile(BytesIO(response.body)) as zip_file:
            return sorted(zip_file.namelist())

    def test_bulk_download_packs_selected_jobs(self) -> None:
        first = self._asset_job(1)
        second = self._asset_job(2)
        req = JobBulkDownloadRequest(job_ids=[first.id, second.id])
        response = bulk_download_jobs(req, user=self.user, db=self.db)
        self.assertEqual(response.media_type, "application/zip")
        names = self._zip_names(response)
        # 每个作品一个子目录，含 source/pixelized/meta 三个文件。
        self.assertIn("asset1_1/asset1_1_01_source.png", names)
        self.assertIn("asset1_1/asset1_1_03_pixelized.png", names)
        self.assertIn("asset1_1/asset1_1_meta.json", names)
        self.assertIn("asset2_2/asset2_2_01_source.png", names)
        self.assertEqual(len(names), 6)

    def test_bulk_download_ignores_other_users_jobs(self) -> None:
        mine = self._asset_job(1)
        theirs = self._asset_job(2, owner=self.other)
        req = JobBulkDownloadRequest(job_ids=[mine.id, theirs.id])
        response = bulk_download_jobs(req, user=self.user, db=self.db)
        names = self._zip_names(response)
        self.assertTrue(all(name.startswith("asset1_") for name in names))

    def test_bulk_download_skips_non_succeeded(self) -> None:
        failed = self._asset_job(1, status="failed", with_files=False)
        succeeded = self._asset_job(2)
        req = JobBulkDownloadRequest(job_ids=[failed.id, succeeded.id])
        response = bulk_download_jobs(req, user=self.user, db=self.db)
        names = self._zip_names(response)
        self.assertTrue(all(name.startswith("asset2_") for name in names))

    def test_bulk_download_missing_jobs_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            bulk_download_jobs(JobBulkDownloadRequest(job_ids=[999]), user=self.user, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_bulk_download_without_files_returns_409(self) -> None:
        job = self._asset_job(1, with_files=False)
        with self.assertRaises(HTTPException) as ctx:
            bulk_download_jobs(JobBulkDownloadRequest(job_ids=[job.id]), user=self.user, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
