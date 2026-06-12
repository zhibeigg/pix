from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix_web.config import WebSettings
from pix_web.credits import adjust_credits
from pix_web.models import Base, CreditAccount, GenerationJob, GenerationOutput, User
from pix_web.retention import MAX_RETAINED_PHOTOS_PER_USER, effective_gallery_limit, prune_user_photos
from pix_web.routers.jobs import expand_gallery_quota, get_gallery_quota


class GalleryQuotaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings = WebSettings(storage_root=Path(self.tmpdir.name))
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()
        self.user = User(email="user@example.com", password_hash="x", display_name="user", role="user", status="active")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _available(self) -> int:
        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == self.user.id))
        return account.available_credits if account is not None else 0

    def _successful_job(self, index: int) -> GenerationJob:
        finished_at = datetime.now(timezone.utc) - timedelta(minutes=index)
        job = GenerationJob(
            user_id=self.user.id,
            client_request_id=f"job-{index}",
            job_type="asset",
            status="succeeded",
            prompt=f"job {index}",
            finished_at=finished_at,
        )
        self.db.add(job)
        self.db.flush()
        output = GenerationOutput(job_id=job.id, run_dir="", source_path=f"source-{index}.png", pixelized_path=f"pixel-{index}.png", meta_json_path=f"meta-{index}.json")
        self.db.add(output)
        self.db.flush()
        return job

    def test_default_gallery_quota_is_ten(self) -> None:
        response = get_gallery_quota(user=self.user, db=self.db)
        self.assertEqual(response.retained_limit, MAX_RETAINED_PHOTOS_PER_USER)
        self.assertEqual(response.expand_price_credits, 60)
        self.assertEqual(response.expand_slots, 10)
        self.assertEqual(effective_gallery_limit(self.db, self.user.id), MAX_RETAINED_PHOTOS_PER_USER)

    def test_expand_gallery_quota_spends_credits_and_adds_slots(self) -> None:
        adjust_credits(self.db, self.user, 100, "充值")
        self.db.commit()
        response = expand_gallery_quota(user=self.user, db=self.db)
        self.assertEqual(response.retained_limit, 20)
        self.assertEqual(response.remaining_slots, 20)
        self.assertEqual(self._available(), 40)

    def test_expand_gallery_quota_requires_credits(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            expand_gallery_quota(user=self.user, db=self.db)
        self.assertEqual(ctx.exception.status_code, 402)

    def test_prune_user_photos_uses_expanded_limit(self) -> None:
        adjust_credits(self.db, self.user, 100, "充值")
        expand_gallery_quota(user=self.user, db=self.db)
        for index in range(21):
            self._successful_job(index)
        self.db.commit()

        pruned = prune_user_photos(self.db, self.user.id, self.settings)
        self.db.commit()

        self.assertEqual(pruned, 1)
        remaining = self.db.scalars(select(GenerationJob).where(GenerationJob.user_id == self.user.id, GenerationJob.status == "succeeded")).all()
        self.assertEqual(len(remaining), 20)


if __name__ == "__main__":
    unittest.main()
