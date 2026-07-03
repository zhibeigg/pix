from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix_web.billing import create_membership_order, mock_pay_order
from pix_web.credits import consume_reserved, ensure_credit_account, refund_reserved, reserve_credits
from pix_web.membership import activate_or_extend, ensure_default_membership_plans, get_user_membership
from pix_web.models import Base, CreditAccount, GenerationJob, User


class MembershipCreditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()
        ensure_default_membership_plans(self.db)
        self.user = self._user("member@example.com")
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, email: str) -> User:
        user = User(email=email, password_hash="x", display_name=email.split("@", 1)[0])
        self.db.add(user)
        self.db.flush()
        ensure_credit_account(self.db, user)
        return user

    def _job(self, price: int) -> GenerationJob:
        job = GenerationJob(user_id=self.user.id, client_request_id=f"req-{price}", job_type="asset", status="pending", price_credits=price)
        self.db.add(job)
        self.db.flush()
        return job

    def _account(self) -> CreditAccount:
        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == self.user.id))
        assert account is not None
        return account

    def test_reserve_consumes_daily_quota_before_permanent_credits(self) -> None:
        activate_or_extend(self.db, self.user, "bronze")  # 100 / day
        account = self._account()
        account.available_credits = 50
        job = self._job(130)

        reserve_credits(self.db, self.user, job, 130)

        self.assertEqual(job.reserved_quota, 100)
        self.assertEqual(job.reserved_credits, 30)
        self.assertEqual(account.daily_quota_balance, 0)
        self.assertEqual(account.available_credits, 20)
        self.assertEqual(account.reserved_quota, 100)
        self.assertEqual(account.reserved_credits, 30)

        consume_reserved(self.db, job)
        self.assertEqual(account.reserved_quota, 0)
        self.assertEqual(account.reserved_credits, 0)
        self.assertEqual(account.available_credits, 20)
        self.assertEqual(account.total_consumed, 130)

    def test_same_day_quota_refund_returns_to_daily_quota(self) -> None:
        activate_or_extend(self.db, self.user, "bronze")
        account = self._account()
        job = self._job(80)
        reserve_credits(self.db, self.user, job, 80)
        self.assertEqual(account.daily_quota_balance, 20)

        refund_reserved(self.db, job)

        self.assertEqual(account.daily_quota_balance, 100)
        self.assertEqual(account.reserved_quota, 0)
        self.assertEqual(job.reserved_quota, 0)

    def test_cross_day_quota_refund_expires(self) -> None:
        activate_or_extend(self.db, self.user, "bronze")
        account = self._account()
        job = self._job(80)
        reserve_credits(self.db, self.user, job, 80)
        job.reserved_quota_date = "2000-01-01"
        self.assertEqual(account.daily_quota_balance, 20)

        refund_reserved(self.db, job)

        self.assertEqual(account.daily_quota_balance, 20)
        self.assertEqual(account.reserved_quota, 0)
        self.assertEqual(job.reserved_quota, 0)

    def test_paid_membership_order_activates_membership(self) -> None:
        order = create_membership_order(self.db, self.user, "silver", provider="mock")
        self.assertEqual(order.order_kind, "membership")
        self.assertEqual(order.membership_plan_key, "silver")

        paid = mock_pay_order(self.db, order.id)
        membership = get_user_membership(self.db, self.user.id)
        account = self._account()

        self.assertEqual(paid.status, "paid")
        self.assertIsNotNone(membership)
        assert membership is not None
        self.assertEqual(membership.plan_key, "silver")
        self.assertEqual(membership.daily_quota, 200)
        self.assertEqual(account.daily_quota_balance, 200)


if __name__ == "__main__":
    unittest.main()
