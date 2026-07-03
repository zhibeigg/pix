from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from pix_web.character_library import auto_save_character_for_job
from pix_web.config import WebSettings
from pix_web.credits import adjust_credits, ensure_credit_account
from pix_web.external_api_keys import create_external_api_key, hash_api_key
from pix_web.main import create_app
from pix_web.models import CharacterLibraryItem, ExternalApiKey, GenerationJob, GenerationOutput, SystemSetting, User
from pix_web.schemas import AssetParamsSchema
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

    def test_external_job_batch_create_submits_independent_same_parameter_assets(self) -> None:
        raw = self._create_key()
        payloads = []
        for index in range(3):
            payload = self._asset_payload()
            payload["client_request_id"] = f"asset-draw-{index}"
            payloads.append(payload)

        response = self.client.post(
            "/external/v1/jobs/batch",
            headers={"Authorization": f"Bearer {raw}"},
            json={"jobs": payloads, "batch_name": "Blue sword draws", "mode": "asset_multi"},
        )
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(len(body["jobs"]), 3)
        self.assertEqual(body["total_price_credits"], 60)
        self.assertIsNotNone(body["batch_id"])

        ids = [item["id"] for item in body["jobs"]]
        self.assertEqual(len(set(ids)), 3)
        jobs = list(
            self.db.scalars(
                select(GenerationJob).where(GenerationJob.id.in_(ids)).order_by(GenerationJob.id)
            )
        )
        self.assertEqual(len(jobs), 3)
        self.assertEqual(
            [job.client_request_id for job in jobs],
            ["asset-draw-0", "asset-draw-1", "asset-draw-2"],
        )
        self.assertTrue(all(job.job_type == "asset" for job in jobs))
        self.assertTrue(all(job.params_json["asset"]["name"] == "蓝色魔法剑" for job in jobs))
        account = ensure_credit_account(self.db, self.user)
        self.assertEqual(account.reserved_credits, 60)

    def test_external_job_create_accepts_character_asset_kind(self) -> None:
        raw = self._create_key()
        payload = self._asset_payload()
        payload["asset"] = {
            "name": "蓝袍骑士",
            "asset_kind": "character",
            "subject_kind": "single_prop",
        }
        payload["pixelize"] = {"output_size": [64, 64], "colors": 32, "remove_bg": True}

        response = self.client.post("/external/v1/jobs", headers={"Authorization": f"Bearer {raw}"}, json=payload)
        self.assertEqual(response.status_code, 202, response.text)

        job = self.db.get(GenerationJob, response.json()["id"])
        self.assertIsNotNone(job)
        asset = job.params_json["asset"]
        self.assertEqual(asset["asset_kind"], "character")
        self.assertEqual(asset["subject_kind"], "single_character")

    def test_character_asset_schema_normalizes_and_auto_saves_library_item(self) -> None:
        params = AssetParamsSchema(asset_kind="character", subject_kind="single_prop")
        self.assertEqual(params.subject_kind, "single_character")
        # 角色默认生成三视图；非角色类型即便显式传入也会被归一回落到 single。
        self.assertEqual(params.character_views, "three_view")
        self.assertEqual(
            AssetParamsSchema(asset_kind="item_icon", character_views="three_view").character_views,
            "single",
        )

        job = GenerationJob(
            user_id=self.user.id,
            client_request_id="character-job",
            job_type="asset",
            status="succeeded",
            prompt="蓝袍骑士",
            params_json={
                "asset": {"name": "蓝袍骑士", "asset_kind": "character", "subject_kind": "single_character"},
                "pixelize": {"output_size": [64, 64], "colors": 32, "remove_bg": True},
            },
        )
        self.db.add(job)
        self.db.flush()
        run_dir = self.settings.storage_root / "runs" / f"job-{job.id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        pixelized = run_dir / "pixelized.png"
        preview = run_dir / "preview.png"
        pixelized.write_bytes(b"pixel")
        preview.write_bytes(b"preview")
        output = GenerationOutput(
            job_id=job.id,
            run_dir=str(run_dir),
            source_path=str(pixelized),
            pixelized_path=str(pixelized),
            preview_path=str(preview),
            meta_json_path=str(run_dir / "meta.json"),
        )
        self.db.add(output)
        self.db.flush()

        item = auto_save_character_for_job(self.db, job, output)
        self.assertIsNotNone(item)
        self.db.commit()
        self.db.refresh(item)
        self.assertEqual(item.name, "蓝袍骑士")
        self.assertEqual(item.source_job_id, job.id)
        self.assertEqual(item.image_path, str(pixelized))
        self.assertEqual(item.preview_path, str(preview))
        self.assertEqual(item.parameter_snapshot_json["source"], "auto_asset_character")
        self.assertTrue(item.parameter_snapshot_json["auto_saved"])

        duplicate = auto_save_character_for_job(self.db, job, output)
        self.assertEqual(duplicate.id, item.id)
        active_items = list(self.db.scalars(select(CharacterLibraryItem).where(CharacterLibraryItem.source_job_id == job.id)))
        self.assertEqual(len(active_items), 1)

    def test_external_job_access_is_limited_to_key_owner(self) -> None:
        raw, _row = create_external_api_key(self.db, self.user, name="owner", scopes=["jobs:read"])
        other_job = GenerationJob(user_id=self.other.id, client_request_id="other", job_type="asset", status="pending")
        self.db.add(other_job)
        self.db.commit()
        self.db.refresh(other_job)

        response = self.client.get(f"/external/v1/jobs/{other_job.id}", headers={"Authorization": f"Bearer {raw}"})
        self.assertEqual(response.status_code, 404, response.text)

    def test_external_job_create_uses_configured_asset_subject_limit(self) -> None:
        self.db.add(SystemSetting(key="pix.asset.subject_max_chars", value="3"))
        self.db.commit()
        raw = self._create_key()
        payload = self._asset_payload()
        payload["asset"]["name"] = "abcd"

        settings_response = self.client.get("/settings/image-models")
        self.assertEqual(settings_response.status_code, 200, settings_response.text)
        self.assertEqual(settings_response.json()["limits"]["asset_subject_max_chars"], 3)

        response = self.client.post("/external/v1/jobs", headers={"Authorization": f"Bearer {raw}"}, json=payload)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("素材主体最多支持 3 字", response.text)

    def test_external_character_api_requires_scope_and_supports_crud(self) -> None:
        upload_dir = self.settings.storage_root / "uploads" / str(self.user.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_path = upload_dir / "hero.png"
        image_path.write_bytes(b"img")

        no_scope_key = self._create_key(scopes=["me:read"])
        forbidden = self.client.get("/external/v1/characters", headers={"Authorization": f"Bearer {no_scope_key}"})
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        raw = self._create_key(scopes=["characters:read", "characters:write"])
        rejected_upload = self.client.post(
            "/external/v1/characters",
            headers={"Authorization": f"Bearer {raw}"},
            json={"name": "Hero", "tags": ["blue", "hero"], "image_path": str(image_path)},
        )
        self.assertEqual(rejected_upload.status_code, 409, rejected_upload.text)
        self.assertIn("只有像素直出的角色类型作品才能成为角色", rejected_upload.text)

        job = GenerationJob(
            user_id=self.user.id,
            client_request_id="character-direct",
            job_type="asset",
            status="succeeded",
            prompt="Hero",
            params_json={"asset": {"name": "Hero", "asset_kind": "character", "subject_kind": "single_character"}},
        )
        self.db.add(job)
        self.db.flush()
        run_dir = self.settings.storage_root / "runs" / f"job-{job.id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        pixelized = run_dir / "pixelized.png"
        pixelized.write_bytes(b"img")
        self.db.add(GenerationOutput(job_id=job.id, run_dir=str(run_dir), source_path=str(pixelized), pixelized_path=str(pixelized), preview_path=str(pixelized), meta_json_path=str(run_dir / "meta.json")))
        self.db.commit()

        created = self.client.post(
            "/external/v1/characters",
            headers={"Authorization": f"Bearer {raw}"},
            json={"name": "Hero", "tags": ["blue", "hero"], "image_path": str(pixelized)},
        )
        self.assertEqual(created.status_code, 201, created.text)
        character_id = created.json()["id"]
        self.assertEqual(created.json()["name"], "Hero")
        self.assertEqual(created.json()["tags"], ["blue", "hero"])

        listed = self.client.get("/external/v1/characters", headers={"Authorization": f"Bearer {raw}"})
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["id"] for item in listed.json()], [character_id])

        updated = self.client.patch(
            f"/external/v1/characters/{character_id}",
            headers={"Authorization": f"Bearer {raw}"},
            json={"name": "Hero Prime", "status": "archived"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["status"], "archived")

        deleted = self.client.delete(f"/external/v1/characters/{character_id}", headers={"Authorization": f"Bearer {raw}"})
        self.assertEqual(deleted.status_code, 200, deleted.text)
        row = self.db.get(CharacterLibraryItem, character_id)
        self.assertIsNotNone(row)
        self.assertEqual(row.status, "deleted")

    def test_external_create_character_from_job_records_source_job(self) -> None:
        raw = self._create_key(scopes=["characters:read", "characters:write", "jobs:read"])
        job = GenerationJob(
            user_id=self.user.id,
            client_request_id="done",
            job_type="asset",
            status="succeeded",
            prompt="Hero",
            params_json={"asset": {"name": "Hero", "asset_kind": "character", "subject_kind": "single_character"}},
        )
        self.db.add(job)
        self.db.flush()
        run_dir = self.settings.storage_root / "runs" / f"job-{job.id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        pixelized = run_dir / "pixelized.png"
        pixelized.write_bytes(b"img")
        self.db.add(GenerationOutput(job_id=job.id, run_dir=str(run_dir), source_path=str(pixelized), pixelized_path=str(pixelized), preview_path=str(pixelized), meta_json_path=str(run_dir / "meta.json")))
        self.db.commit()

        response = self.client.post(
            f"/external/v1/characters/jobs/{job.id}",
            headers={"Authorization": f"Bearer {raw}"},
            json={"name": "Hero From Job", "image_kind": "pixelized"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["source_job_id"], job.id)
        self.assertEqual(response.json()["image_path"], str(pixelized))

    def test_external_create_character_from_non_character_job_is_rejected(self) -> None:
        raw = self._create_key(scopes=["characters:read", "characters:write", "jobs:read"])
        job = GenerationJob(
            user_id=self.user.id,
            client_request_id="not-character",
            job_type="asset",
            status="succeeded",
            prompt="Sword",
            params_json={"asset": {"name": "Sword", "asset_kind": "item_icon"}},
        )
        self.db.add(job)
        self.db.flush()
        run_dir = self.settings.storage_root / "runs" / f"job-{job.id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        pixelized = run_dir / "pixelized.png"
        pixelized.write_bytes(b"img")
        self.db.add(GenerationOutput(job_id=job.id, run_dir=str(run_dir), source_path=str(pixelized), pixelized_path=str(pixelized), preview_path=str(pixelized), meta_json_path=str(run_dir / "meta.json")))
        self.db.commit()

        response = self.client.post(
            f"/external/v1/characters/jobs/{job.id}",
            headers={"Authorization": f"Bearer {raw}"},
            json={"name": "Sword As Hero", "image_kind": "pixelized"},
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("只有像素直出的角色类型作品才能成为角色", response.text)


if __name__ == "__main__":
    unittest.main()
