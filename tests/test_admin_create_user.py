from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.models import CreditAccount, CreditTransaction, SystemSetting, User
from pix_web.security import create_access_token, verify_password


class AdminCreateUserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 'admin-create-user.db'}",
            storage_root=root / "outputs",
            auto_create_db=True,
            jwt_secret="admin-create-user-test-secret-32-chars",
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.db = self.app.state.SessionLocal()
        self.admin = User(
            email="admin@example.com",
            password_hash="x",
            display_name="Admin",
            role="admin",
            status="active",
        )
        self.user = User(
            email="member@example.com",
            password_hash="x",
            display_name="Member",
            role="user",
            status="active",
        )
        self.db.add_all([self.admin, self.user])
        bonus = self.db.scalar(
            select(SystemSetting).where(SystemSetting.key == "registration_bonus_credits")
        )
        assert bonus is not None
        bonus.value = "47"
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.user)
        self.admin_token = create_access_token(self.admin, self.settings)
        self.user_token = create_access_token(self.user, self.settings)

    def tearDown(self) -> None:
        self.db.close()
        self.client.close()
        self.app.state.engine.dispose()
        self.tmpdir.cleanup()

    @staticmethod
    def _auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _payload(**overrides: str) -> dict[str, str]:
        payload = {
            "email": "New.User@Example.COM",
            "password": "test-password1",
            "display_name": "",
        }
        payload.update(overrides)
        return payload

    def test_admin_creates_active_user_with_normalized_defaults_hash_and_bonus(self) -> None:
        password = "test-password1"
        response = self.client.post(
            "/admin/users",
            headers=self._auth(self.admin_token),
            json=self._payload(password=password, display_name="   "),
        )

        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["email"], "new.user@example.com")
        self.assertEqual(body["display_name"], "new.user")
        self.assertEqual(body["role"], "user")
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["available_credits"], 47)
        self.assertEqual(body["total_recharged"], 47)
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)
        self.assertNotIn(password, response.text)

        created = self.db.scalar(select(User).where(User.email == "new.user@example.com"))
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created.display_name, "new.user")
        self.assertEqual(created.role, "user")
        self.assertEqual(created.status, "active")
        self.assertTrue(created.password_hash.startswith("$argon2"))
        self.assertNotEqual(created.password_hash, password)
        self.assertTrue(verify_password(password, created.password_hash))

        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == created.id))
        self.assertIsNotNone(account)
        assert account is not None
        self.assertEqual(account.available_credits, 47)
        self.assertEqual(account.total_recharged, 47)
        transaction = self.db.scalar(
            select(CreditTransaction).where(CreditTransaction.user_id == created.id)
        )
        self.assertIsNotNone(transaction)
        assert transaction is not None
        self.assertEqual(transaction.type, "recharge")
        self.assertEqual(transaction.amount, 47)
        self.assertEqual(transaction.note, "注册赠送")

    def test_duplicate_email_returns_409_without_creating_another_user(self) -> None:
        first = self.client.post(
            "/admin/users",
            headers=self._auth(self.admin_token),
            json=self._payload(),
        )
        duplicate = self.client.post(
            "/admin/users",
            headers=self._auth(self.admin_token),
            json=self._payload(email="NEW.USER@example.com"),
        )

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        count = self.db.scalar(
            select(func.count()).select_from(User).where(User.email == "new.user@example.com")
        )
        self.assertEqual(count, 1)

    def test_integrity_error_returns_409(self) -> None:
        error = IntegrityError("INSERT INTO users", {}, Exception("duplicate"))
        with patch.object(Session, "flush", side_effect=error):
            response = self.client.post(
                "/admin/users",
                headers=self._auth(self.admin_token),
                json=self._payload(email="race@example.com"),
            )

        self.assertEqual(response.status_code, 409, response.text)

    def test_invalid_payloads_return_422(self) -> None:
        invalid_payloads = (
            self._payload(email="not-an-email"),
            self._payload(password="onlyletters"),
            self._payload(password="123456789"),
            self._payload(password="abc12345"),
            self._payload(display_name="x" * 121),
            {**self._payload(), "role": "admin"},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/admin/users",
                    headers=self._auth(self.admin_token),
                    json=payload,
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_regular_user_is_forbidden(self) -> None:
        response = self.client.post(
            "/admin/users",
            headers=self._auth(self.user_token),
            json=self._payload(),
        )

        self.assertEqual(response.status_code, 403, response.text)

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.post("/admin/users", json=self._payload())

        self.assertEqual(response.status_code, 401, response.text)


if __name__ == "__main__":
    unittest.main()
