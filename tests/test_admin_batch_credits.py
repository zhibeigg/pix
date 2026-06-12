from __future__ import annotations

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix_web.models import Base, CreditAccount, User
from pix_web.routers.admin import adjust_users_credits_batch
from pix_web.schemas import AdminBatchAdjustCreditsRequest


class AdminBatchCreditsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()
        self.admin = self._user("admin@example.com", role="admin")
        self.user_a = self._user("a@example.com")
        self.user_b = self._user("b@example.com")
        self.inactive = self._user("inactive@example.com", status="disabled")
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, email: str, *, role: str = "user", status: str = "active") -> User:
        user = User(email=email, password_hash="x", display_name=email.split("@", 1)[0], role=role, status=status)
        self.db.add(user)
        self.db.flush()
        return user

    def _available(self, user: User) -> int:
        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
        return account.available_credits if account is not None else 0

    def test_adjusts_selected_users_once(self) -> None:
        result = adjust_users_credits_batch(
            AdminBatchAdjustCreditsRequest(user_ids=[self.user_a.id, self.user_b.id, self.user_a.id], amount=25, note="运营补点"),
            _admin=self.admin,
            db=self.db,
        )
        self.assertEqual(result["adjusted_count"], 2)
        self.assertEqual(self._available(self.user_a), 25)
        self.assertEqual(self._available(self.user_b), 25)
        self.assertEqual(self._available(self.inactive), 0)

    def test_all_users_only_targets_active_users(self) -> None:
        result = adjust_users_credits_batch(
            AdminBatchAdjustCreditsRequest(all_users=True, amount=10, note="全体补点"),
            _admin=self.admin,
            db=self.db,
        )
        self.assertEqual(result["adjusted_count"], 3)
        self.assertEqual(self._available(self.admin), 10)
        self.assertEqual(self._available(self.user_a), 10)
        self.assertEqual(self._available(self.user_b), 10)
        self.assertEqual(self._available(self.inactive), 0)

    def test_missing_selected_user_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            adjust_users_credits_batch(
                AdminBatchAdjustCreditsRequest(user_ids=[self.user_a.id, 9999], amount=5, note="补点"),
                _admin=self.admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
