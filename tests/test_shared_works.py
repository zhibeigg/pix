from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.models import CreditAccount, CreditTransaction, GenerationJob, GenerationOutput, SharedWork, SystemSetting, User
from pix_web.retention import prune_user_photos
from pix_web.security import create_access_token, create_file_ticket


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
        self.admin = User(email="admin@example.com", password_hash="x", display_name="Admin", role="admin", status="active")
        self.db.add_all([self.user, self.other, self.admin])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.other)
        self.db.refresh(self.admin)
        self.jwt = create_access_token(self.user, self.settings)
        self.other_jwt = create_access_token(self.other, self.settings)
        self.admin_jwt = create_access_token(self.admin, self.settings)

    def tearDown(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    def _auth(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

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

    def _publish(self, job: GenerationJob) -> dict:
        response = self.client.post(f"/shares/jobs/{job.id}/publish", headers=self._auth(self.jwt))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _approve(self, share_id: int) -> dict:
        response = self.client.post(f"/admin/shares/{share_id}/approve", headers=self._auth(self.admin_jwt))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _reject(self, share_id: int, note: str = "画面含水印，请修改后重提") -> dict:
        response = self.client.post(f"/admin/shares/{share_id}/reject", json={"note": note}, headers=self._auth(self.admin_jwt))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _credit_balance(self, user_id: int) -> int:
        with self.app.state.SessionLocal() as db:
            account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
            return int(account.available_credits if account is not None else 0)

    def _share_reward_transactions(self, user_id: int) -> list[CreditTransaction]:
        with self.app.state.SessionLocal() as db:
            return list(db.scalars(select(CreditTransaction).where(CreditTransaction.user_id == user_id, CreditTransaction.type == "share_reward")))

    def _share_row(self, share_id: int) -> dict[str, object]:
        with self.app.state.SessionLocal() as db:
            share = db.get(SharedWork, share_id)
            self.assertIsNotNone(share)
            assert share is not None
            return {
                "id": share.id,
                "job_id": share.job_id,
                "status": share.status,
                "review_note": share.review_note or "",
                "reviewed_at": share.reviewed_at,
                "reviewed_by_user_id": share.reviewed_by_user_id,
                "published_at": share.published_at,
                "reward_credits": share.reward_credits,
                "rewarded_at": share.rewarded_at,
            }

    def test_publish_enters_pending_and_public_listing_requires_login(self) -> None:
        job = self._successful_job(index=10)

        anonymous_list = self.client.get("/shares")
        self.assertEqual(anonymous_list.status_code, 401, anonymous_list.text)

        first = self._publish(job)
        self.assertEqual(first["status"], "pending")
        self.assertEqual(first["reward_credits"], 0)
        self.assertEqual(first["review_note"], "")
        self.assertIsNone(first["reviewed_at"])
        self.assertTrue(first["preview_url"].endswith(f"/shares/{first['id']}/preview"))
        self.assertGreaterEqual(len(first["download_options"]), 1)
        self.assertEqual(self._credit_balance(self.user.id), 0)

        # 待审核作品不进入公开池，普通登录用户也看不到。
        authed_list = self.client.get("/shares", headers=self._auth(self.other_jwt))
        self.assertEqual(authed_list.status_code, 200, authed_list.text)
        self.assertEqual(authed_list.json()["total"], 0)

        # 只有管理员审核列表能看到 pending。
        user_admin_list = self.client.get("/admin/shares?status=pending", headers=self._auth(self.jwt))
        self.assertEqual(user_admin_list.status_code, 403, user_admin_list.text)
        admin_list = self.client.get("/admin/shares?status=pending", headers=self._auth(self.admin_jwt))
        self.assertEqual(admin_list.status_code, 200, admin_list.text)
        self.assertEqual(admin_list.json()["total"], 1)
        self.assertEqual(admin_list.json()["items"][0]["user_email"], self.user.email)

        listing = self.client.get("/jobs", headers=self._auth(self.jwt))
        self.assertEqual(listing.status_code, 200, listing.text)
        listed_job = next(item for item in listing.json() if item["id"] == job.id)
        self.assertEqual(listed_job["share"]["status"], "pending")
        self.assertEqual(listed_job["share"]["review_note"], "")

        duplicate = self._publish(job)
        self.assertEqual(duplicate["id"], first["id"])
        self.assertEqual(duplicate["status"], "pending")

        withdrawn = self.client.post(f"/shares/{first['id']}/unpublish", headers=self._auth(self.jwt))
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertEqual(withdrawn.json()["status"], "hidden")
        resubmitted = self._publish(job)
        self.assertEqual(resubmitted["id"], first["id"])
        self.assertEqual(resubmitted["status"], "pending")

    def test_admin_approve_makes_active_visible_rewards_once_and_likes(self) -> None:
        job = self._successful_job(index=20)
        pending = self._publish(job)
        share_id = pending["id"]

        approved = self._approve(share_id)
        self.assertEqual(approved["status"], "active")
        self.assertEqual(approved["reward_credits"], 1)
        self.assertIsNotNone(approved["published_at"])
        self.assertIsNotNone(approved["reviewed_at"])
        self.assertEqual(approved["reviewed_by_user_id"], self.admin.id)
        self.assertEqual(self._credit_balance(self.user.id), 1)
        self.assertEqual(len(self._share_reward_transactions(self.user.id)), 1)

        public_list = self.client.get("/shares", headers=self._auth(self.jwt))
        self.assertEqual(public_list.status_code, 200, public_list.text)
        self.assertEqual(public_list.json()["total"], 1)
        self.assertEqual(public_list.json()["items"][0]["id"], share_id)
        self.assertFalse(public_list.json()["items"][0]["liked_by_me"])

        liked = self.client.post(f"/shares/{share_id}/like", headers=self._auth(self.other_jwt))
        self.assertEqual(liked.status_code, 200, liked.text)
        self.assertTrue(liked.json()["liked_by_me"])
        self.assertEqual(liked.json()["like_count"], 1)
        other_list = self.client.get("/shares", headers=self._auth(self.other_jwt))
        self.assertTrue(other_list.json()["items"][0]["liked_by_me"])
        unliked = self.client.delete(f"/shares/{share_id}/like", headers=self._auth(self.other_jwt))
        self.assertEqual(unliked.status_code, 200, unliked.text)
        self.assertEqual(unliked.json()["like_count"], 0)

        second_approval = self._approve(share_id)
        self.assertEqual(second_approval["status"], "active")
        self.assertEqual(self._credit_balance(self.user.id), 1)
        self.assertEqual(len(self._share_reward_transactions(self.user.id)), 1)

        forbidden = self.client.post(f"/shares/{share_id}/unpublish", headers=self._auth(self.jwt))
        self.assertEqual(forbidden.status_code, 403, forbidden.text)
        admin_hidden = self.client.post(f"/admin/shares/{share_id}/unpublish", headers=self._auth(self.admin_jwt))
        self.assertEqual(admin_hidden.status_code, 200, admin_hidden.text)
        self.assertEqual(admin_hidden.json()["status"], "hidden")
        after_hidden = self.client.get("/shares", headers=self._auth(self.jwt))
        self.assertEqual(after_hidden.json()["total"], 0)

    def test_approval_rewards_respect_author_daily_limit(self) -> None:
        reward_credits = self.db.scalar(select(SystemSetting).where(SystemSetting.key == "share.reward_credits"))
        daily_limit = self.db.scalar(select(SystemSetting).where(SystemSetting.key == "share.daily_reward_limit"))
        self.assertIsNotNone(reward_credits)
        self.assertIsNotNone(daily_limit)
        assert reward_credits is not None and daily_limit is not None
        reward_credits.value = "3"
        daily_limit.value = "1"
        self.db.commit()

        first_job = self._successful_job(index=31)
        second_job = self._successful_job(index=32)
        first_share = self._publish(first_job)
        second_share = self._publish(second_job)

        first = self._approve(first_share["id"])
        second = self._approve(second_share["id"])
        self.assertEqual(first["reward_credits"], 3)
        self.assertEqual(second["reward_credits"], 0)
        self.assertEqual(self._credit_balance(self.user.id), 3)
        self.assertEqual(len(self._share_reward_transactions(self.user.id)), 1)

    def test_reject_returns_reason_on_job_and_allows_resubmission(self) -> None:
        job = self._successful_job(index=40)
        pending = self._publish(job)
        note = "边缘有明显水印，请去除后重新提交"

        rejected = self._reject(pending["id"], note=note)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["review_note"], note)
        self.assertIsNotNone(rejected["reviewed_at"])
        self.assertEqual(rejected["reviewed_by_user_id"], self.admin.id)

        listing = self.client.get("/jobs", headers=self._auth(self.jwt))
        self.assertEqual(listing.status_code, 200, listing.text)
        listed_job = next(item for item in listing.json() if item["id"] == job.id)
        self.assertEqual(listed_job["share"]["status"], "rejected")
        self.assertEqual(listed_job["share"]["review_note"], note)

        public_list = self.client.get("/shares", headers=self._auth(self.jwt))
        self.assertEqual(public_list.json()["total"], 0)

        resubmitted = self._publish(job)
        self.assertEqual(resubmitted["id"], pending["id"])
        self.assertEqual(resubmitted["status"], "pending")
        self.assertEqual(resubmitted["review_note"], "")
        self.assertIsNone(resubmitted["reviewed_at"])

    def test_active_and_pending_source_jobs_are_locked_but_rejected_hidden_can_delete(self) -> None:
        pending_job = self._successful_job(index=50)
        self._publish(pending_job)
        pending_delete = self.client.post("/jobs/bulk-delete", json={"job_ids": [pending_job.id]}, headers=self._auth(self.jwt))
        self.assertEqual(pending_delete.status_code, 409, pending_delete.text)

        active_job = self._successful_job(index=51)
        active_share = self._publish(active_job)
        self._approve(active_share["id"])
        active_delete = self.client.post("/jobs/bulk-delete", json={"job_ids": [active_job.id]}, headers=self._auth(self.jwt))
        self.assertEqual(active_delete.status_code, 409, active_delete.text)

        rejected_job = self._successful_job(index=52)
        rejected_share = self._publish(rejected_job)
        self._reject(rejected_share["id"])
        rejected_delete = self.client.post("/jobs/bulk-delete", json={"job_ids": [rejected_job.id]}, headers=self._auth(self.jwt))
        self.assertEqual(rejected_delete.status_code, 200, rejected_delete.text)
        rejected_row = self._share_row(rejected_share["id"])
        self.assertEqual(rejected_row["status"], "deleted")
        self.assertIsNone(rejected_row["job_id"])
        self.db.expunge_all()

        hidden_job = self._successful_job(index=53)
        hidden_share = self._publish(hidden_job)
        hidden = self.client.post(f"/shares/{hidden_share['id']}/unpublish", headers=self._auth(self.jwt))
        self.assertEqual(hidden.status_code, 200, hidden.text)
        hidden_delete = self.client.post("/jobs/bulk-delete", json={"job_ids": [hidden_job.id]}, headers=self._auth(self.jwt))
        self.assertEqual(hidden_delete.status_code, 200, hidden_delete.text)
        hidden_row = self._share_row(hidden_share["id"])
        self.assertEqual(hidden_row["status"], "deleted")
        self.assertIsNone(hidden_row["job_id"])

    def test_preview_and_download_require_ticket_or_bearer_and_admin_preview_checks_admin(self) -> None:
        pending_job = self._successful_job(index=60)
        pending_share = self._publish(pending_job)
        admin_preview_url = f"/admin/shares/{pending_share['id']}/preview"

        admin_preview_without_auth = self.client.get(admin_preview_url)
        self.assertEqual(admin_preview_without_auth.status_code, 401, admin_preview_without_auth.text)
        user_ticket = create_file_ticket(self.user, self.settings)
        admin_preview_as_user = self.client.get(f"{admin_preview_url}?token={user_ticket}")
        self.assertEqual(admin_preview_as_user.status_code, 403, admin_preview_as_user.text)
        admin_ticket = create_file_ticket(self.admin, self.settings)
        admin_preview = self.client.get(f"{admin_preview_url}?token={admin_ticket}")
        self.assertEqual(admin_preview.status_code, 200, admin_preview.text)
        self.assertEqual(admin_preview.content, b"pixel")

        # 公开预览/下载即使是登录票据，也只允许 active 分享。
        pending_public_preview = self.client.get(f"/shares/{pending_share['id']}/preview?token={user_ticket}")
        self.assertEqual(pending_public_preview.status_code, 404, pending_public_preview.text)

        active = self._approve(pending_share["id"])
        public_preview_url = pending_share["preview_url"]
        preview_without_ticket = self.client.get(public_preview_url)
        self.assertEqual(preview_without_ticket.status_code, 401, preview_without_ticket.text)
        preview_with_ticket = self.client.get(f"{public_preview_url}?token={user_ticket}")
        self.assertEqual(preview_with_ticket.status_code, 200, preview_with_ticket.text)
        self.assertEqual(preview_with_ticket.content, b"pixel")
        preview_with_bearer = self.client.get(public_preview_url, headers=self._auth(self.jwt))
        self.assertEqual(preview_with_bearer.status_code, 200, preview_with_bearer.text)

        download_url = pending_share["download_options"][0]["url"]
        download_without_ticket = self.client.get(download_url)
        self.assertEqual(download_without_ticket.status_code, 401, download_without_ticket.text)
        missing_kind = self.client.get(f"/shares/{active['id']}/download/not_allowed?token={user_ticket}")
        self.assertEqual(missing_kind.status_code, 404, missing_kind.text)
        download_with_ticket = self.client.get(f"{download_url}?token={user_ticket}")
        self.assertEqual(download_with_ticket.status_code, 200, download_with_ticket.text)
        self.assertEqual(download_with_ticket.content, b"source")

    def test_publish_rejects_non_owner_and_unfinished_work(self) -> None:
        job = self._successful_job(index=70)
        forbidden = self.client.post(f"/shares/jobs/{job.id}/publish", headers=self._auth(self.other_jwt))
        self.assertEqual(forbidden.status_code, 404, forbidden.text)

        pending = GenerationJob(user_id=self.user.id, client_request_id="pending-share", job_type="asset", status="pending")
        self.db.add(pending)
        self.db.commit()
        blocked = self.client.post(f"/shares/jobs/{pending.id}/publish", headers=self._auth(self.jwt))
        self.assertEqual(blocked.status_code, 409, blocked.text)

    def test_prune_keeps_active_and_pending_shared_work_sources(self) -> None:
        pending_job = self._successful_job(index=80)
        active_job = self._successful_job(index=81)
        self._publish(pending_job)
        active_share = self._publish(active_job)
        self._approve(active_share["id"])

        for index in range(90, 104):
            self._successful_job(index=index)
        pruned = prune_user_photos(self.db, self.user.id, self.settings, keep=1)
        self.db.commit()
        self.assertGreater(pruned, 0)
        self.assertIsNotNone(self.db.get(GenerationJob, pending_job.id))
        self.assertIsNotNone(self.db.get(GenerationJob, active_job.id))
        self.assertEqual(self._share_row(active_share["id"])["status"], "active")


if __name__ == "__main__":
    unittest.main()
