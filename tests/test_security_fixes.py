"""安全修复回归测试：LFI、/files 越权、文件票据、SSRF 出站防护。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from pix.net_guard import UnsafeDownloadURLError, assert_safe_download_url
from pix_web.config import WebSettings
from pix_web.credits import adjust_credits
from pix_web.file_ownership import resolve_owned_input_path, user_owns_file
from pix_web.main import create_app
from pix_web.models import User
from pix_web.security import create_access_token, create_file_ticket, decode_file_ticket


class FileOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'sec-test.db'}",
            storage_root=root / "outputs",
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


if __name__ == "__main__":
    unittest.main()
