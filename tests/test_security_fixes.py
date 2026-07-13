"""安全修复回归测试：LFI、/files 越权、文件票据、SSRF 出站防护。"""

from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from pix.net_guard import UnsafeDownloadURLError, assert_safe_download_url
from pix_web.config import WebSettings, load_web_settings
from pix_web.credits import adjust_credits
from pix_web.file_ownership import resolve_owned_input_path, user_owns_file
from pix_web.jobs import create_jobs_batch, retry_failed_job, validate_job_request
from pix_web.main import create_app
from pix_web.models import CharacterLibraryItem, GenerationJob, User
from pix_web.schemas import JobCreateRequest
from pix_web.security import create_access_token, create_file_ticket, decode_file_ticket


class FileOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.legacy_storage_root = root / "legacy-web-outputs"
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'sec-test.db'}",
            storage_root=root / "outputs",
            legacy_storage_roots=(self.legacy_storage_root,),
            queue_backend="database",
            auto_create_db=True,
            jwt_secret="test-secret-please-change-32chars!!",
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.db = self.app.state.SessionLocal()
        self.user = User(email="a@example.com", password_hash="x", role="user", status="active")
        self.other = User(email="b@example.com", password_hash="x", role="user", status="active")
        self.admin = User(email="admin@example.com", password_hash="x", role="admin", status="active")
        self.db.add_all([self.user, self.other, self.admin])
        self.db.commit()
        for u in (self.user, self.other, self.admin):
            self.db.refresh(u)
        adjust_credits(self.db, self.user, 200, "test")
        self.db.commit()
        self.storage_root = self.settings.storage_root.resolve()
        (self.storage_root / "uploads" / str(self.user.id)).mkdir(parents=True, exist_ok=True)
        (self.storage_root / "uploads" / str(self.other.id)).mkdir(parents=True, exist_ok=True)
        self.own_file = self.storage_root / "uploads" / str(self.user.id) / "a.png"
        self.own_file.write_bytes(b"img")
        self.other_file = self.storage_root / "uploads" / str(self.other.id) / "b.png"
        self.other_file.write_bytes(b"img")
        self.legacy_own_file = (
            self.legacy_storage_root / "uploads" / str(self.user.id) / self.own_file.name
        )
        self.legacy_other_file = (
            self.legacy_storage_root / "uploads" / str(self.other.id) / self.other_file.name
        )

    def tearDown(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    def test_user_owns_own_upload_but_not_others(self) -> None:
        self.assertTrue(user_owns_file(self.own_file.resolve(), self.user, self.db, self.settings))
        self.assertFalse(user_owns_file(self.other_file.resolve(), self.user, self.db, self.settings))

    def test_admin_owns_any_file(self) -> None:
        self.assertTrue(user_owns_file(self.other_file.resolve(), self.admin, self.db, self.settings))

    def test_resolve_owned_input_path_blocks_lfi(self) -> None:
        # 系统任意路径
        with self.assertRaises(ValueError):
            resolve_owned_input_path("/etc/hosts", self.user, self.db, self.settings)
        # 他人上传目录
        with self.assertRaises(ValueError):
            resolve_owned_input_path(str(self.other_file), self.user, self.db, self.settings)
        # 自己的文件放行
        self.assertEqual(
            resolve_owned_input_path(str(self.own_file), self.user, self.db, self.settings),
            self.own_file.resolve(),
        )

    def test_files_endpoint_rejects_cross_user(self) -> None:
        ticket = create_file_ticket(self.user, self.settings)
        own = self.client.get("/files", params={"path": str(self.own_file), "token": ticket})
        self.assertEqual(own.status_code, 200)
        other = self.client.get("/files", params={"path": str(self.other_file), "token": ticket})
        self.assertEqual(other.status_code, 403)

    def test_bound_file_ticket_only_serves_its_reference_image(self) -> None:
        second_own_file = self.own_file.parent / "second.png"
        second_own_file.write_bytes(b"second")
        ticket = create_file_ticket(self.user, self.settings, bound_path=self.own_file)

        bound = self.client.get(
            "/files", params={"path": str(self.own_file), "token": ticket}
        )
        changed = self.client.get(
            "/files", params={"path": str(second_own_file), "token": ticket}
        )

        self.assertEqual(bound.status_code, 200, bound.text)
        self.assertEqual(changed.status_code, 403)
        self.assertEqual(changed.json()["detail"], "文件票据与目标文件不匹配")

    def test_configured_legacy_storage_root_rebases_without_bypassing_ownership(self) -> None:
        ticket = create_file_ticket(self.user, self.settings)

        own = self.client.get(
            "/files",
            params={"path": str(self.legacy_own_file), "token": ticket},
        )
        other = self.client.get(
            "/files",
            params={"path": str(self.legacy_other_file), "token": ticket},
        )

        self.assertEqual(own.status_code, 200, own.text)
        self.assertEqual(own.content, b"img")
        self.assertEqual(other.status_code, 403)
        self.assertEqual(
            resolve_owned_input_path(
                str(self.legacy_own_file), self.user, self.db, self.settings
            ),
            self.own_file.resolve(),
        )

    def test_admin_preview_ticket_serves_rebased_legacy_job_output(self) -> None:
        relative = Path("runs/job-3487/legacy-run/03_pixelized.png")
        current_file = self.storage_root / relative
        current_file.parent.mkdir(parents=True, exist_ok=True)
        current_file.write_bytes(b"legacy-preview")
        legacy_file = self.legacy_storage_root / relative
        ticket = create_file_ticket(self.admin, self.settings)

        response = self.client.get(
            "/files",
            params={"path": str(legacy_file), "token": ticket},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, b"legacy-preview")

    def test_unconfigured_legacy_storage_root_remains_forbidden(self) -> None:
        ticket = create_file_ticket(self.user, self.settings)
        unexpected = (
            self.storage_root.parent
            / "unexpected-web-outputs"
            / "uploads"
            / str(self.user.id)
            / self.own_file.name
        )

        response = self.client.get(
            "/files",
            params={"path": str(unexpected), "token": ticket},
        )

        self.assertEqual(response.status_code, 403)

    def test_legacy_storage_roots_load_from_environment(self) -> None:
        second_root = self.legacy_storage_root.parent / "older-web-outputs"
        with patch.dict(
            "os.environ",
            {
                "PIX_DISABLE_DOTENV": "1",
                "PIX_WEB_LEGACY_STORAGE_ROOTS": (
                    f"{self.legacy_storage_root},{second_root}"
                ),
            },
            clear=True,
        ):
            settings = load_web_settings()

        self.assertEqual(
            settings.legacy_storage_roots,
            (self.legacy_storage_root, second_root),
        )

    def test_files_endpoint_requires_auth(self) -> None:
        resp = self.client.get("/files", params={"path": str(self.own_file)})
        self.assertEqual(resp.status_code, 401)

    def test_file_ticket_issue_and_decode(self) -> None:
        jwt_token = create_access_token(self.user, self.settings)
        resp = self.client.post("/files/ticket", headers={"Authorization": f"Bearer {jwt_token}"})
        self.assertEqual(resp.status_code, 200)
        ticket = resp.json()["ticket"]
        self.assertEqual(decode_file_ticket(ticket, self.settings), self.user.id)
        # 完整登录 token 不是 file ticket
        self.assertIsNone(decode_file_ticket(jwt_token, self.settings))

    def test_file_ticket_cannot_be_promoted_to_full_bearer_session(self) -> None:
        ticket = create_file_ticket(self.user, self.settings)
        headers = {"Authorization": f"Bearer {ticket}"}

        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/files/ticket", headers=headers).status_code, 401)

    def test_local_bg_remove_with_foreign_path_is_rejected(self) -> None:
        jwt_token = create_access_token(self.user, self.settings)
        resp = self.client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={
                "job_type": "local_bg_remove",
                "input_image_path": str(self.other_file),
                "pixelize": {"remove_bg": True},
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_validate_job_request_does_not_probe_raw_user_path(self) -> None:
        req = JobCreateRequest(
            job_type="local_bg_remove",
            input_image_path=str(self.own_file),
            pixelize={"remove_bg": True},
        )
        with patch.object(Path, "exists", side_effect=AssertionError("raw path probed")):
            validate_job_request(req)

    def test_owned_missing_input_is_checked_after_ownership(self) -> None:
        jwt_token = create_access_token(self.user, self.settings)
        missing = self.own_file.parent / "missing.png"
        resp = self.client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={
                "job_type": "local_bg_remove",
                "input_image_path": str(missing),
                "pixelize": {"remove_bg": True},
            },
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"], "输入图片不存在")

    def test_job_stores_resolved_path_and_idempotent_hit_skips_new_payload_probe(self) -> None:
        jwt_token = create_access_token(self.user, self.settings)
        request_id = "path-idempotency"
        non_normalized = self.own_file.parent / "nested" / ".." / self.own_file.name
        payload = {
            "job_type": "local_bg_remove",
            "input_image_path": str(non_normalized),
            "client_request_id": request_id,
            "pixelize": {"remove_bg": True},
        }
        first = self.client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json=payload,
        )
        self.assertEqual(first.status_code, 200, first.text)

        self.db.expire_all()
        stored = self.db.get(GenerationJob, first.json()["id"])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.input_image_path, str(self.own_file.resolve()))

        payload["input_image_path"] = str(self.other_file)
        with patch(
            "pix_web.jobs.resolve_owned_input_path",
            side_effect=AssertionError("idempotent payload path probed"),
        ):
            second = self.client.post(
                "/jobs",
                headers={"Authorization": f"Bearer {jwt_token}"},
                json=payload,
            )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["id"], first.json()["id"])

    def test_batch_idempotent_hit_skips_new_payload_probe(self) -> None:
        existing = GenerationJob(
            user_id=self.user.id,
            client_request_id="batch-path-idempotency",
            job_type="local_bg_remove",
            status="pending",
            input_image_path=str(self.own_file.resolve()),
            params_json={"pixelize": {"remove_bg": True}},
            price_credits=0,
        )
        self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)
        req = JobCreateRequest(
            job_type="local_bg_remove",
            input_image_path=str(self.other_file),
            client_request_id=existing.client_request_id,
            pixelize={"remove_bg": True},
        )

        with patch(
            "pix_web.jobs.resolve_owned_input_path",
            side_effect=AssertionError("batch idempotent payload path probed"),
        ):
            jobs, total_price, batch = create_jobs_batch(
                self.db,
                self.user,
                [req],
                settings=self.settings,
            )

        self.assertEqual([job.id for job in jobs], [existing.id])
        self.assertEqual(total_price, 0)
        self.assertIsNone(batch)

    def test_failed_retry_rechecks_input_path_ownership(self) -> None:
        job = GenerationJob(
            user_id=self.user.id,
            client_request_id="failed-foreign-path",
            job_type="local_bg_remove",
            status="failed",
            input_image_path=str(self.other_file),
            params_json={"pixelize": {"remove_bg": True}},
            price_credits=0,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        with self.assertRaises(HTTPException) as exc_info:
            retry_failed_job(self.db, self.user, job.id, self.settings)
        self.assertEqual(exc_info.exception.status_code, 422)
        self.assertEqual(exc_info.exception.detail, "输入图片路径不合法")

    def test_character_library_file_is_owned_and_usable_as_sprite_reference(self) -> None:
        character_dir = self.storage_root / "characters" / str(self.user.id)
        character_dir.mkdir(parents=True, exist_ok=True)
        character_file = character_dir / "hero.png"
        character_file.write_bytes(b"img")
        self.db.add(CharacterLibraryItem(user_id=self.user.id, name="Hero", image_path=str(character_file), preview_path=str(character_file)))
        self.db.commit()

        self.assertTrue(user_owns_file(character_file.resolve(), self.user, self.db, self.settings))
        self.assertFalse(user_owns_file(character_file.resolve(), self.other, self.db, self.settings))
        self.assertEqual(resolve_owned_input_path(str(character_file), self.user, self.db, self.settings), character_file.resolve())

        ticket = create_file_ticket(self.user, self.settings)
        response = self.client.get("/files", params={"path": str(character_file), "token": ticket})
        self.assertEqual(response.status_code, 200, response.text)

        jwt_token = create_access_token(self.user, self.settings)
        job_response = self.client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={
                "job_type": "sprite_sheet",
                "prompt": "蓝袍骑士行走动画",
                "sprite": {"mode": "mosaic", "rows": 1, "cols": 2, "fps": 8, "reference_image_path": str(character_file)},
                "pixelize": {"output_size": [32, 32], "colors": 8, "remove_bg": False},
            },
        )
        self.assertEqual(job_response.status_code, 200, job_response.text)
        self.assertEqual(job_response.json()["sprite_reference_image_url"].startswith("/files?path="), True)


class SsrfGuardTests(unittest.TestCase):
    def test_blocks_metadata_and_private(self) -> None:
        for url in (
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1/x.png",
            "http://10.0.0.1/x.png",
            "http://192.168.0.1/x.png",
            "file:///etc/passwd",
        ):
            with self.assertRaises(UnsafeDownloadURLError):
                assert_safe_download_url(url)

    def test_allows_public_ip_literal(self) -> None:
        # 公网 IP 字面量无需 DNS 解析，应放行
        assert_safe_download_url("https://8.8.8.8/x.png")

    def test_allows_trusted_ark_tos_fake_ip(self) -> None:
        fake_info = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("198.18.1.202", 443))]
        with patch("socket.getaddrinfo", return_value=fake_info):
            assert_safe_download_url("https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/video.mp4")

    def test_blocks_untrusted_fake_ip(self) -> None:
        fake_info = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("198.18.1.202", 443))]
        with patch("socket.getaddrinfo", return_value=fake_info):
            with self.assertRaises(UnsafeDownloadURLError):
                assert_safe_download_url("https://example.com/video.mp4")


if __name__ == "__main__":
    unittest.main()
