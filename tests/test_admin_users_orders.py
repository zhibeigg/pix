from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pix_web.models import Base, CreditAccount, PaymentOrder, User, UserMembership
from pix_web.routers.admin import orders as admin_orders
from pix_web.routers.admin import users as admin_users


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _admin() -> User:
    return User(id=999, email="admin@example.com", password_hash="x", role="admin")


def test_admin_users_include_credit_balance_and_membership() -> None:
    db = _session()
    try:
        now = datetime.now(timezone.utc)
        user = User(email="u1@example.com", password_hash="x", display_name="用户一", created_at=now)
        db.add(user)
        db.commit()
        db.add(
            CreditAccount(
                user_id=user.id,
                available_credits=120,
                reserved_credits=5,
                total_recharged=300,
                total_consumed=180,
                daily_quota_balance=40,
            )
        )
        db.add(
            UserMembership(
                user_id=user.id,
                plan_key="silver",
                daily_quota=200,
                status="active",
                expires_at=now + timedelta(days=10),
            )
        )
        db.commit()

        rows = admin_users(_admin=_admin(), db=db, limit=100)
        assert len(rows) == 1
        row = rows[0]
        assert row.available_credits == 120
        assert row.total_recharged == 300
        assert row.total_consumed == 180
        assert row.daily_quota_balance == 40
        assert row.membership_status == "active"
        assert row.membership_plan_key == "silver"  # 有效会员才回填 plan_key
    finally:
        db.close()


def test_admin_users_without_account_defaults_to_zero() -> None:
    db = _session()
    try:
        user = User(email="u2@example.com", password_hash="x")
        db.add(user)
        db.commit()

        rows = admin_users(_admin=_admin(), db=db, limit=100)
        assert len(rows) == 1
        assert rows[0].available_credits == 0
        assert rows[0].membership_plan_key is None
    finally:
        db.close()


def test_admin_orders_attach_user_info_and_sort_desc() -> None:
    db = _session()
    try:
        now = datetime.now(timezone.utc)
        buyer = User(email="buyer@example.com", password_hash="x", display_name="买家")
        db.add(buyer)
        db.commit()
        older = PaymentOrder(
            user_id=buyer.id,
            provider="alipay",
            provider_order_id="ORDER-OLD",
            status="paid",
            amount_cents=990,
            currency="cny",
            credits=100,
            order_kind="recharge",
            created_at=now - timedelta(hours=2),
            paid_at=now - timedelta(hours=1),
        )
        newer = PaymentOrder(
            user_id=buyer.id,
            provider="alipay",
            provider_order_id="ORDER-NEW",
            status="pending",
            amount_cents=19900,
            currency="cny",
            credits=0,
            order_kind="membership",
            membership_plan_key="silver",
            created_at=now,
        )
        db.add_all([older, newer])
        db.commit()

        rows = admin_orders(_admin=_admin(), db=db, limit=100)
        assert len(rows) == 2
        # 默认按 created_at 降序：最新订单在前
        assert rows[0].provider_order_id == "ORDER-NEW"
        assert rows[0].user_email == "buyer@example.com"
        assert rows[0].user_display_name == "买家"
        assert rows[0].order_kind == "membership"
        assert rows[1].provider_order_id == "ORDER-OLD"
        assert rows[1].credits == 100
    finally:
        db.close()
