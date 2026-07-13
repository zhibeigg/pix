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
        assert dashboard["total_users"] == 4
        assert dashboard["total_jobs"] == 1
        assert dashboard["total_succeeded"] == 1
        assert dashboard["total_failed"] == 0
        assert dashboard["total_credits_consumed"] == 5
        assert dashboard["total_orders_created"] == 3
        assert dashboard["total_orders_paid"] == 2
        assert dashboard["total_credits_recharged"] == 1099
        assert dashboard["total_uploads"] == 1
        assert dashboard["history_days"] == 14
        assert len(dashboard["history"]) == 14
        today_point = dashboard["history"][-1]
        assert today_point["date"] == today.date().isoformat()
        assert today_point["jobs"] == 1
        assert today_point["succeeded"] == 1
        assert today_point["credits_consumed"] == 5
        assert today_point["orders_created"] == 1
        assert today_point["orders_paid"] == 1
        assert today_point["credits_recharged"] == 100
        assert today_point["uploads"] == 1
        assert today_point["new_users"] == 1
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_admin_dashboard_preserves_cumulative_totals_and_zero_fills_history() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        today = _today_start()
        old_day = today - timedelta(days=30)
        recent_day = today - timedelta(days=2)
        yesterday = today - timedelta(days=1)
        old_user = User(email="history-old@example.com", password_hash="x", created_at=old_day)
        recent_user = User(
            email="history-recent@example.com",
            password_hash="x",
            created_at=recent_day + timedelta(hours=1),
        )
        db.add_all([old_user, recent_user, SystemSetting(key="site.timezone", value="UTC")])
        db.commit()

        db.add_all(
            [
                GenerationJob(
                    user_id=old_user.id,
                    client_request_id="history-old-success",
                    job_type="asset",
                    status="succeeded",
                    price_credits=10,
                    created_at=old_day + timedelta(hours=1),
                    finished_at=old_day + timedelta(hours=1, minutes=1),
                ),
                GenerationJob(
                    user_id=recent_user.id,
                    client_request_id="history-recent-success",
                    job_type="asset",
                    status="succeeded",
                    price_credits=7,
                    created_at=recent_day + timedelta(hours=2),
                    finished_at=recent_day + timedelta(hours=2, minutes=1),
                ),
                GenerationJob(
                    user_id=recent_user.id,
                    client_request_id="history-yesterday-failed",
                    job_type="asset",
                    status="failed",
                    price_credits=99,
                    created_at=yesterday + timedelta(hours=3),
                    finished_at=yesterday + timedelta(hours=3, minutes=1),
                ),
                PaymentOrder(
                    user_id=old_user.id,
                    status="paid",
                    credits=200,
                    amount_cents=1990,
                    currency="cny",
                    created_at=old_day + timedelta(hours=4),
                    paid_at=old_day + timedelta(hours=4, minutes=1),
                ),
                PaymentOrder(
                    user_id=recent_user.id,
                    status="paid",
                    credits=50,
                    amount_cents=590,
                    currency="cny",
                    created_at=recent_day + timedelta(hours=5),
                    paid_at=yesterday + timedelta(hours=1),
                ),
                UploadEvent(
                    user_id=recent_user.id,
                    filename="history.png",
                    content_type="image/png",
                    size_bytes=256,
                    created_at=recent_day + timedelta(hours=6),
                ),
            ]
        )
        db.commit()

        dashboard = admin_dashboard(db)

        assert dashboard["total_users"] == 2
        assert dashboard["total_jobs"] == 3
        assert dashboard["total_succeeded"] == 2
        assert dashboard["total_failed"] == 1
        assert dashboard["total_credits_consumed"] == 17
        assert dashboard["total_orders_created"] == 2
        assert dashboard["total_orders_paid"] == 2
        assert dashboard["total_credits_recharged"] == 250
        assert dashboard["total_uploads"] == 1

        history = dashboard["history"]
        assert len(history) == 14
        assert [point["date"] for point in history] == sorted(point["date"] for point in history)
        by_date = {point["date"]: point for point in history}
        recent_point = by_date[recent_day.date().isoformat()]
        assert recent_point["jobs"] == 1
        assert recent_point["succeeded"] == 1
        assert recent_point["failed"] == 0
        assert recent_point["credits_consumed"] == 7
        assert recent_point["orders_created"] == 1
        assert recent_point["orders_paid"] == 0
        assert recent_point["uploads"] == 1
        assert recent_point["new_users"] == 1

        yesterday_point = by_date[yesterday.date().isoformat()]
        assert yesterday_point["jobs"] == 1
        assert yesterday_point["failed"] == 1
        assert yesterday_point["credits_consumed"] == 0
        assert yesterday_point["orders_created"] == 0
        assert yesterday_point["orders_paid"] == 1
        assert yesterday_point["credits_recharged"] == 50

        empty_point = by_date[(today - timedelta(days=3)).date().isoformat()]
        assert all(value == 0 for key, value in empty_point.items() if key != "date")
        assert old_day.date().isoformat() not in by_date
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
