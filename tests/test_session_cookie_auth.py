"""浏览器 HttpOnly Cookie 会话与 CSRF 防护回归测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.models import User
from pix_web.security import create_access_token, hash_password


class SessionCookieAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'session.db'}",
            storage_root=root / "outputs",
            auto_create_db=True,
            jwt_secret="session-cookie-test-secret-32-chars!!",
            cors_origins=("https://frontend.example",),
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.db = self.app.state.SessionLocal()
        self.user = User(
            email="session@example.com",
            password_hash=hash_password("correct-password"),
            display_name="Session User",
            role="user",
            status="active",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    def _session_login(self, origin: str = "http://testserver"):
        return self.client.post(
            "/auth/session/login",
            headers={"Origin": origin},
            json={"email": self.user.email, "password": "correct-password"},
        )

    def test_session_login_sets_httponly_cookie_without_returning_token(self) -> None:
        response = self._session_login()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("access_token", response.json())
        set_cookie = response.headers["set-cookie"].lower()
        self.assertIn("pix_web_session=", set_cookie)
        self.assertIn("httponly", set_cookie)
        self.assertIn("samesite=lax", set_cookie)
        self.assertIn("path=/", set_cookie)
        self.assertNotIn("secure", set_cookie)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

    def test_cookie_authenticated_write_requires_allowed_origin(self) -> None:
        self.assertEqual(self._session_login().status_code, 200)

        missing_origin = self.client.post("/files/ticket")
        evil_origin = self.client.post(
            "/files/ticket",
            headers={"Origin": "https://evil.example"},
        )
        allowed_origin = self.client.post(
            "/files/ticket",
            headers={"Origin": "https://frontend.example"},
        )

        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(evil_origin.status_code, 403)
        self.assertEqual(allowed_origin.status_code, 200, allowed_origin.text)

    def test_bearer_jwt_remains_compatible_without_origin_header(self) -> None:
        token = create_access_token(self.user, self.settings)
        response = self.client.post(
            "/files/ticket",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)

    def test_logout_clears_cookie(self) -> None:
        self.assertEqual(self._session_login().status_code, 200)

        response = self.client.post(
            "/auth/session/logout",
            headers={"Origin": "http://testserver"},
        )

        self.assertEqual(response.status_code, 204, response.text)
        self.assertIn("pix_web_session=", response.headers["set-cookie"].lower())
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_session_login_rejects_untrusted_origin(self) -> None:
        response = self._session_login("https://evil.example")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("pix_web_session", self.client.cookies)

    def test_forwarded_host_headers_do_not_expand_csrf_allowlist(self) -> None:
        response = self.client.post(
            "/auth/session/login",
            headers={
                "Origin": "https://evil.example",
                "X-Forwarded-Host": "evil.example",
                "X-Forwarded-Proto": "https",
            },
            json={"email": self.user.email, "password": "correct-password"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("pix_web_session", self.client.cookies)


class ProductionCookieConfigTests(unittest.TestCase):
    def test_production_rejects_explicitly_insecure_session_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = WebSettings(
                database_url=f"sqlite:///{root / 'prod.db'}",
                storage_root=root / "outputs",
                env="prod",
                jwt_secret="production-session-cookie-secret-32chars!!",
                session_cookie_secure=False,
            )
            with self.assertRaisesRegex(RuntimeError, "Cookie"):
                create_app(settings)


if __name__ == "__main__":
    unittest.main()
