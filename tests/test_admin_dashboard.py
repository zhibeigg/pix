from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pix_web.dashboard import admin_dashboard
from pix_web.models import Base, CreditTransaction, GenerationJob, PaymentOrder, SystemSetting, UploadEvent, User


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def test_admin_dashboard_uses_paid_orders_for_today_recharge_and_counts_active_users() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        today = _today_start()
        yesterday = today - timedelta(days=1)
        new_user = User(email="new@example.com", password_hash="x", created_at=today + timedelta(hours=1))
        job_user = User(email="job@example.com", password_hash="x", created_at=yesterday)
        upload_user = User(email="upload@example.com", password_hash="x", created_at=yesterday)
        old_user = User(email="old@example.com", password_hash="x", created_at=yesterday)
        db.add_all([new_user, job_user, upload_user, old_user, SystemSetting(key="site.timezone", value="UTC")])
        db.commit()

        # 注册赠送与人工 recharge 都不应计入后台「今日充值」。
        db.add_all(
            [
                CreditTransaction(
                    user_id=new_user.id,
                    type="recharge",
                    amount=30,
                    balance_after=30,
                    note="注册赠送",
                    created_at=today + timedelta(hours=1),
                ),
                CreditTransaction(
                    user_id=old_user.id,
                    type="recharge",
                    amount=200,
                    balance_after=200,
                    note="管理员补点",
                    created_at=today + timedelta(hours=2),
                ),
                PaymentOrder(
                    user_id=job_user.id,
                    status="paid",
                    credits=100,
                    amount_cents=990,
                    currency="cny",
                    created_at=yesterday,
                    paid_at=today + timedelta(hours=3),
                ),
                PaymentOrder(
                    user_id=old_user.id,
                    status="paid",
                    credits=999,
                    amount_cents=9900,
                    currency="cny",
                    created_at=yesterday,
                    paid_at=yesterday,
                ),
                PaymentOrder(
                    user_id=upload_user.id,
                    status="pending",
                    credits=500,
                    amount_cents=3900,
                    currency="cny",
                    created_at=today + timedelta(hours=4),
                ),
                GenerationJob(
                    user_id=job_user.id,
                    client_request_id="job-today",
                    job_type="asset",
                    status="succeeded",
                    price_credits=5,
                    created_at=today + timedelta(hours=5),
                    finished_at=today + timedelta(hours=5, minutes=1),
                ),
                UploadEvent(
                    user_id=upload_user.id,
                    filename="ref.png",
                    content_type="image/png",
                    size_bytes=128,
                    created_at=today + timedelta(hours=6),
                ),
            ]
        )
        db.commit()

        dashboard = admin_dashboard(db)

        assert dashboard["credits_recharged_today"] == 100
        assert dashboard["orders_paid_today"] == 1
        assert dashboard["paying_users_today"] == 1
        assert dashboard["new_users_today"] == 1
        assert dashboard["active_users_today"] == 3
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
