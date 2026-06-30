from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from pix_web.config import WebSettings
from pix_web.credits import ensure_credit_account
from pix_web.main import create_app
from pix_web.models import CreditTransaction, GenerationJob, GenerationOutput, SharedWork, SystemSetting, User
from pix_web.retention import prune_user_photos
from pix_web.security import create_access_token


class SharedWorkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'pix-share-test.db'}",
            storage_root=root / "outputs",
            queue_backend="database",
            auto_create_db=True,
            jwt_secret="test-secret",
        )
        self.settings.storage_root.mkdir(parents=True, exist_ok=True)
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.db = self.app.state.SessionLocal()
        self.user = User(email="share@example.com", password_hash="x", display_name="Share User", role="user", status="active")
        self.other = User(email="other@example.com", password_hash="x", display_name="Other", role="user", status="active")
        self.db.add_all([self.user, self.other])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.other)
        self.jwt = create_access_token(self.user, self.settings)
        self.other_jwt = create_access_token(self.other, self.settings)

    def tearDown(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    def _successful_job(self, owner: User | None = None, index: int = 1) -> GenerationJob:
        owner = owner or self.user
        run_dir = self.settings.storage_root / "runs" / f"job-{owner.id}-{index}"
        run_dir.mkdir(parents=True, exist_ok=True)
        source = run_dir / "source.png"
        pixel = run_dir / "pixel.png"
        meta = run_dir / "meta.json"
        source.write_bytes(b"source")
        pixel.write_bytes(b"pixel")
        meta.write_text("{}", encoding="utf-8")
        job = GenerationJob(
            user_id=owner.id,
            client_request_id=f"share-{owner.id}-{index}",
            job_type="asset",
            status="succeeded",
            prompt=f"share prompt {index}",
            params_json={
                "asset": {"name": f"分享飞剑 {index}", "asset_kind": "item_icon", "extra_prompt": "青玉质感"},
                "pixelize": {"output_size": [32, 32], "colors": 16, "remove_bg": True},
                "image_model": "image2",
            },
        )
        self.db.add(job)
        self.db.flush()
        self.db.add(GenerationOutput(job_id=job.id, run_dir=str(run_dir), source_path=str(source), pixelized_path=str(pixel), meta_json_path=str(meta)))
        self.db.commit()
        self.db.refresh(job)
        return job

    def test_publish_rewards_once_and_returns_share_status_on_jobs(self) -> None:
        job = self._successful_job(index=10)

        first = self.client.post(f"/shares/jobs/{job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["reward_credits"], 1)
        account = ensure_credit_account(self.db, self.user)
        self.assertEqual(account.available_credits, 1)

        second = self.client.post(f"/shares/jobs/{job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["id"], body["id"])
        self.db.refresh(account)
        self.assertEqual(account.available_credits, 1)
        hidden = self.client.post(f"/shares/{body['id']}/unpublish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(hidden.status_code, 200, hidden.text)
        republished = self.client.post(f"/shares/jobs/{job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(republished.status_code, 200, republished.text)
        self.assertEqual(republished.json()["reward_credits"], 1)
        self.db.refresh(account)
        self.assertEqual(account.available_credits, 1)

        reward_txs = list(self.db.scalars(select(CreditTransaction).where(CreditTransaction.type == "share_reward")))
        self.assertEqual(len(reward_txs), 1)

        listing = self.client.get("/jobs", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(listing.status_code, 200, listing.text)
        listed_job = next(item for item in listing.json() if item["id"] == job.id)
        self.assertEqual(listed_job["share"]["status"], "active")

    def test_publish_rejects_non_owner_and_unfinished_work(self) -> None:
        job = self._successful_job(index=20)
        forbidden = self.client.post(f"/shares/jobs/{job.id}/publish", headers={"Authorization": f"Bearer {self.other_jwt}"})
        self.assertEqual(forbidden.status_code, 404, forbidden.text)

        pending = GenerationJob(user_id=self.user.id, client_request_id="pending-share", job_type="asset", status="pending")
        self.db.add(pending)
        self.db.commit()
        blocked = self.client.post(f"/shares/jobs/{pending.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(blocked.status_code, 409, blocked.text)

    def test_share_reward_settings_disable_and_daily_limit(self) -> None:
        reward_credits = self.db.scalar(select(SystemSetting).where(SystemSetting.key == "share.reward_credits"))
        daily_limit = self.db.scalar(select(SystemSetting).where(SystemSetting.key == "share.daily_reward_limit"))
        self.assertIsNotNone(reward_credits)
        self.assertIsNotNone(daily_limit)
        reward_credits.value = "3"
        daily_limit.value = "1"
        self.db.commit()

        first_job = self._successful_job(index=31)
        second_job = self._successful_job(index=32)
        first = self.client.post(f"/shares/jobs/{first_job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"})
        second = self.client.post(f"/shares/jobs/{second_job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["reward_credits"], 3)
        self.assertEqual(second.json()["reward_credits"], 0)
        account = ensure_credit_account(self.db, self.user)
        self.assertEqual(account.available_credits, 3)

    def test_like_unlike_list_and_unpublish(self) -> None:
        job = self._successful_job(index=40)
        share = self.client.post(f"/shares/jobs/{job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"}).json()
        share_id = share["id"]

        liked = self.client.post(f"/shares/{share_id}/like", headers={"Authorization": f"Bearer {self.other_jwt}"})
        self.assertEqual(liked.status_code, 200, liked.text)
        self.assertTrue(liked.json()["liked_by_me"])
        self.assertEqual(liked.json()["like_count"], 1)
        duplicate = self.client.post(f"/shares/{share_id}/like", headers={"Authorization": f"Bearer {self.other_jwt}"})
        self.assertEqual(duplicate.json()["like_count"], 1)

        public_list = self.client.get("/shares")
        self.assertEqual(public_list.status_code, 200, public_list.text)
        self.assertEqual(public_list.json()["items"][0]["liked_by_me"], False)
        authed_list = self.client.get("/shares", headers={"Authorization": f"Bearer {self.other_jwt}"})
        self.assertEqual(authed_list.json()["items"][0]["liked_by_me"], True)

        unliked = self.client.delete(f"/shares/{share_id}/like", headers={"Authorization": f"Bearer {self.other_jwt}"})
        self.assertEqual(unliked.status_code, 200, unliked.text)
        self.assertEqual(unliked.json()["like_count"], 0)

        hidden = self.client.post(f"/shares/{share_id}/unpublish", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(hidden.status_code, 200, hidden.text)
        self.assertEqual(hidden.json()["status"], "hidden")
        after = self.client.get("/shares")
        self.assertEqual(after.json()["total"], 0)

    def test_download_uses_manifest_and_prune_keeps_active_shared_work(self) -> None:
        shared_job = self._successful_job(index=50)
        share = self.client.post(f"/shares/jobs/{shared_job.id}/publish", headers={"Authorization": f"Bearer {self.jwt}"}).json()
        download_url = share["download_options"][0]["url"]
        download = self.client.get(download_url)
        self.assertEqual(download.status_code, 200, download.text)
        missing = self.client.get(f"/shares/{share['id']}/download/not_allowed")
        self.assertEqual(missing.status_code, 404, missing.text)

        for index in range(60, 72):
            self._successful_job(index=index)
        pruned = prune_user_photos(self.db, self.user.id, self.settings, keep=1)
        self.db.commit()
        self.assertGreater(pruned, 0)
        self.assertIsNotNone(self.db.get(GenerationJob, shared_job.id))
        row = self.db.get(SharedWork, share["id"])
        self.assertIsNotNone(row)
        self.assertEqual(row.status, "active")


if __name__ == "__main__":
    unittest.main()
