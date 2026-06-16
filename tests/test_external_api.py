from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from pix_web.config import WebSettings
from pix_web.credits import adjust_credits, ensure_credit_account
from pix_web.external_api_keys import create_external_api_key, hash_api_key
from pix_web.main import create_app
from pix_web.models import ExternalApiKey, GenerationJob, User
from pix_web.security import create_access_token


class ExternalApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'pix-api-test.db'}",
            storage_root=root / "outputs",
            queue_backend="database",
            auto_create_db=True,
            jwt_secret="test-secret",
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.db = self.app.state.SessionLocal()
        self.user = User(email="api@example.com", password_hash="x", display_name="API User", role="user", status="active")
        self.other = User(email="other@example.com", password_hash="x", display_name="Other", role="user", status="active")
        self.db.add_all([self.user, self.other])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.other)
        adjust_credits(self.db, self.user, 200, "test credits")
        self.db.commit()
        self.jwt = create_access_token(self.user, self.settings)

    def tearDown(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    def _create_key(self, scopes: list[str] | None = None) -> str:
        raw, _row = create_external_api_key(self.db, self.user, name="test key", scopes=scopes)
        return raw

    def _asset_payload(self) -> dict:
        return {
            "job_type": "asset",
            "asset": {"name": "蓝色魔法剑", "asset_kind": "item_icon"},
            "pixelize": {"output_size": [32, 32], "colors": 8, "remove_bg": True},
            "skip_vl": True,
        }

    def test_api_key_management_returns_plaintext_only_once_and_hashes_secret(self) -> None:
        response = self.client.post(
            "/api-keys",
            headers={"Authorization": f"Bearer {self.jwt}"},
            json={"name": "Unity", "scopes": ["jobs:create", "jobs:read"]},
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        raw_key = body["key"]
        self.assertTrue(raw_key.startswith("pix_live_"))
        self.assertEqual(body["item"]["name"], "Unity")
        self.assertEqual(body["item"]["scopes"], ["jobs:create", "jobs:read"])

        row = self.db.get(ExternalApiKey, body["item"]["id"])
        self.assertIsNotNone(row)
        self.assertEqual(row.key_hash, hash_api_key(raw_key))
        self.assertNotIn(raw_key, row.key_hash)

        listing = self.client.get("/api-keys", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertNotIn(raw_key, listing.text)

        revoked = self.client.delete(f"/api-keys/{row.id}", headers={"Authorization": f"Bearer {self.jwt}"})
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertFalse(revoked.json()["enabled"])
        self.assertIsNotNone(revoked.json()["revoked_at"])

    def test_api_key_create_accepts_pre_generated_token_once(self) -> None:
        custom_key = "pix_live_" + "a" * 64
        response = self.client.post(
            "/api-keys",
            headers={"Authorization": f"Bearer {self.jwt}"},
            json={"name": "Generated", "scopes": ["me:read"], "custom_key": custom_key},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["key"], custom_key)
        row = self.db.get(ExternalApiKey, response.json()["item"]["id"])
        self.assertIsNotNone(row)
        self.assertEqual(row.key_hash, hash_api_key(custom_key))

        duplicate = self.client.post(
            "/api-keys",
            headers={"Authorization": f"Bearer {self.jwt}"},
            json={"name": "Duplicate", "scopes": ["me:read"], "custom_key": custom_key},
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

    def test_external_api_key_auth_and_scope_enforcement(self) -> None:
        raw = self._create_key(scopes=["me:read"])
        me = self.client.get("/external/v1/me", headers={"X-Pix-Api-Key": raw})
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["user"]["email"], self.user.email)

        forbidden = self.client.post(
            "/external/v1/jobs",
            headers={"Authorization": f"Bearer {raw}"},
            json=self._asset_payload(),
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

    def test_external_job_create_is_idempotent_and_uses_user_credits(self) -> None:
        raw = self._create_key()
        headers = {"Authorization": f"Bearer {raw}", "Idempotency-Key": "demo-job-001"}
        first = self.client.post("/external/v1/jobs", headers=headers, json=self._asset_payload())
        self.assertEqual(first.status_code, 202, first.text)
        second = self.client.post("/external/v1/jobs", headers=headers, json=self._asset_payload())
        self.assertEqual(second.status_code, 202, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])

        jobs = list(self.db.scalars(select(GenerationJob).where(GenerationJob.user_id == self.user.id)))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].client_request_id, "external:demo-job-001")
        account = ensure_credit_account(self.db, self.user)
        self.assertEqual(account.reserved_credits, jobs[0].reserved_credits)
        self.assertGreater(jobs[0].reserved_credits, 0)

        listed = self.client.get("/external/v1/jobs", headers={"Authorization": f"Bearer {raw}"})
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], jobs[0].id)

    def test_external_job_access_is_limited_to_key_owner(self) -> None:
        raw, _row = create_external_api_key(self.db, self.user, name="owner", scopes=["jobs:read"])
        other_job = GenerationJob(user_id=self.other.id, client_request_id="other", job_type="asset", status="pending")
        self.db.add(other_job)
        self.db.commit()
        self.db.refresh(other_job)

        response = self.client.get(f"/external/v1/jobs/{other_job.id}", headers={"Authorization": f"Bearer {raw}"})
        self.assertEqual(response.status_code, 404, response.text)


if __name__ == "__main__":
    unittest.main()
