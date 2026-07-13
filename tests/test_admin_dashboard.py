from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pix_web import dashboard as dashboard_module
from pix_web.dashboard import DashboardQueryError, admin_dashboard
from pix_web.models import (
    Base,
    CreditTransaction,
    GenerationJob,
    PaymentOrder,
    SystemSetting,
    UploadEvent,
    User,
)
from pix_web.routers import admin as admin_router
from pix_web.security import get_db, require_admin


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

        dashboard = admin_dashboard(db, now=today + timedelta(hours=12))

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

        dashboard = admin_dashboard(db, now=today + timedelta(hours=12))

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


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    db.add(SystemSetting(key="site.timezone", value="UTC"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _add_user(db: Session, email: str, created_at: datetime) -> User:
    user = User(email=email, password_hash="x", created_at=created_at)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_default_window_zero_fills_and_compares_previous_14_days(db_session: Session) -> None:
    now = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
    current_user = _add_user(
        db_session,
        "current-window@example.com",
        datetime(2026, 6, 10, 1, tzinfo=timezone.utc),
    )
    previous_user = _add_user(
        db_session,
        "previous-window@example.com",
        datetime(2026, 5, 25, 1, tzinfo=timezone.utc),
    )
    db_session.add_all(
        [
            GenerationJob(
                user_id=current_user.id,
                client_request_id="current-window-job",
                job_type="asset",
                status="succeeded",
                price_credits=6,
                created_at=datetime(2026, 6, 10, 2, tzinfo=timezone.utc),
                finished_at=datetime(2026, 6, 10, 2, 1, tzinfo=timezone.utc),
            ),
            GenerationJob(
                user_id=previous_user.id,
                client_request_id="previous-window-job",
                job_type="asset",
                status="failed",
                created_at=datetime(2026, 5, 25, 2, tzinfo=timezone.utc),
                finished_at=datetime(2026, 5, 25, 2, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = admin_dashboard(db_session, now=now)

    assert result["window"]["range"] == "14d"
    assert result["window"]["granularity"] == "day"
    assert result["window"]["start_at"] == datetime(2026, 6, 4, tzinfo=timezone.utc)
    assert result["window"]["end_at"] == datetime(2026, 6, 18, tzinfo=timezone.utc)
    assert result["window"]["comparison_start_at"] == datetime(
        2026, 5, 21, tzinfo=timezone.utc
    )
    assert result["window"]["comparison_end_at"] == datetime(
        2026, 6, 4, tzinfo=timezone.utc
    )
    assert len(result["series"]) == 14
    assert len(result["previous_series"]) == 14
    assert result["current_period"]["jobs"] == 1
    assert result["current_period"]["credits_consumed"] == 6
    assert result["previous_period"]["jobs"] == 1
    assert result["previous_period"]["failed"] == 1
    assert sum(point["jobs"] for point in result["series"]) == 1
    assert result["history"] == dashboard_module._history_from_series(result["series"])


def test_24h_uses_24_aligned_hour_buckets_and_previous_period(db_session: Session) -> None:
    now = datetime(2026, 6, 17, 10, 37, tzinfo=timezone.utc)

    result = admin_dashboard(db_session, range="24h", now=now)

    assert result["window"]["granularity"] == "hour"
    assert result["window"]["start_at"] == datetime(2026, 6, 16, 11, tzinfo=timezone.utc)
    assert result["window"]["end_at"] == datetime(2026, 6, 17, 11, tzinfo=timezone.utc)
    assert result["window"]["data_cutoff_at"] == now
    assert result["window"]["comparison_start_at"] == datetime(
        2026, 6, 15, 11, tzinfo=timezone.utc
    )
    assert result["window"]["comparison_end_at"] == datetime(
        2026, 6, 16, 11, tzinfo=timezone.utc
    )
    assert len(result["series"]) == 24
    assert len(result["previous_series"]) == 24
    assert all(
        point["end_at"] - point["start_at"] == timedelta(hours=1)
        for point in result["series"]
    )


def test_site_timezone_controls_day_boundaries_and_bucketing(db_session: Session) -> None:
    setting = db_session.scalar(
        select(SystemSetting).where(SystemSetting.key == "site.timezone")
    )
    assert setting is not None
    setting.value = "Asia/Shanghai"
    user = _add_user(
        db_session,
        "shanghai-boundary@example.com",
        datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add(
        GenerationJob(
            user_id=user.id,
            client_request_id="shanghai-midnight-job",
            job_type="asset",
            status="succeeded",
            price_credits=3,
            created_at=datetime(2026, 6, 16, 16, 30, tzinfo=timezone.utc),
            finished_at=datetime(2026, 6, 16, 16, 31, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    result = admin_dashboard(
        db_session,
        range="7d",
        now=datetime(2026, 6, 17, 1, tzinfo=timezone.utc),
    )

    assert result["window"]["timezone"] == "Asia/Shanghai"
    assert result["window"]["start_at"].isoformat() == "2026-06-11T00:00:00+08:00"
    assert result["window"]["end_at"].isoformat() == "2026-06-18T00:00:00+08:00"
    assert result["series"][-1]["start_at"].isoformat() == "2026-06-17T00:00:00+08:00"
    assert result["series"][-1]["jobs"] == 1
    assert result["jobs_today"] == 1


def test_custom_window_limits_and_auto_week_granularity(db_session: Session) -> None:
    now = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
    today = now.date()
    result = admin_dashboard(
        db_session,
        range="custom",
        from_date=today - timedelta(days=364),
        to_date=today,
        now=now,
    )
    assert result["window"]["granularity"] == "week"
    assert len(result["series"]) == 53
    assert len(result["previous_series"]) == 53

    invalid_queries = [
        {"range": "custom", "from_date": None, "to_date": today},
        {"range": "custom", "from_date": today, "to_date": None},
        {
            "range": "custom",
            "from_date": today,
            "to_date": today - timedelta(days=1),
        },
        {
            "range": "custom",
            "from_date": today,
            "to_date": today + timedelta(days=1),
        },
        {
            "range": "custom",
            "from_date": today - timedelta(days=365),
            "to_date": today,
        },
        {
            "range": "custom",
            "granularity": "hour",
            "from_date": today - timedelta(days=7),
            "to_date": today,
        },
        {"range": "14d", "from_date": today, "to_date": today},
    ]
    for query in invalid_queries:
        with pytest.raises(DashboardQueryError):
            admin_dashboard(db_session, now=now, **query)


def test_active_and_paying_users_are_deduplicated_per_bucket_and_period(
    db_session: Session,
) -> None:
    now = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
    old = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = _add_user(db_session, "dedupe-first@example.com", old)
    second = _add_user(db_session, "dedupe-second@example.com", old)
    event_time = datetime(2026, 6, 16, 8, tzinfo=timezone.utc)
    db_session.add_all(
        [
            GenerationJob(
                user_id=first.id,
                client_request_id="dedupe-job",
                job_type="asset",
                status="succeeded",
                price_credits=4,
                created_at=event_time,
                finished_at=event_time + timedelta(minutes=1),
            ),
            UploadEvent(
                user_id=first.id,
                filename="dedupe.png",
                content_type="image/png",
                size_bytes=10,
                created_at=event_time + timedelta(minutes=2),
            ),
            PaymentOrder(
                user_id=first.id,
                status="paid",
                credits=10,
                amount_cents=100,
                currency="cny",
                created_at=event_time + timedelta(minutes=3),
                paid_at=event_time + timedelta(minutes=4),
            ),
            PaymentOrder(
                user_id=first.id,
                status="paid",
                credits=20,
                amount_cents=200,
                currency="cny",
                created_at=event_time + timedelta(minutes=5),
                paid_at=event_time + timedelta(minutes=6),
            ),
            PaymentOrder(
                user_id=second.id,
                status="paid",
                credits=30,
                amount_cents=300,
                currency="cny",
                created_at=event_time + timedelta(minutes=7),
                paid_at=event_time + timedelta(minutes=8),
            ),
        ]
    )
    db_session.commit()

    result = admin_dashboard(db_session, range="7d", now=now)
    point = next(point for point in result["series"] if point["jobs"] == 1)

    assert result["current_period"]["active_users"] == 2
    assert result["current_period"]["paying_users"] == 2
    assert result["current_period"]["active_to_paying_rate"] == 1.0
    assert point["active_users"] == 2
    assert point["paying_users"] == 2


def test_order_payment_flow_and_created_order_conversion_use_distinct_time_axes(
    db_session: Session,
) -> None:
    now = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
    user = _add_user(
        db_session,
        "order-semantics@example.com",
        datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    db_session.add_all(
        [
            PaymentOrder(
                user_id=user.id,
                status="paid",
                credits=50,
                amount_cents=500,
                currency="cny",
                created_at=datetime(2026, 6, 3, 20, tzinfo=timezone.utc),
                paid_at=datetime(2026, 6, 5, 8, tzinfo=timezone.utc),
            ),
            PaymentOrder(
                user_id=user.id,
                status="paid",
                credits=60,
                amount_cents=600,
                currency="cny",
                created_at=datetime(2026, 6, 6, 8, tzinfo=timezone.utc),
                paid_at=datetime(2026, 6, 6, 9, tzinfo=timezone.utc),
            ),
            PaymentOrder(
                user_id=user.id,
                status="pending",
                credits=70,
                amount_cents=700,
                currency="cny",
                created_at=datetime(2026, 6, 7, 8, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = admin_dashboard(db_session, now=now)

    assert result["current_period"]["orders_created"] == 2
    assert result["current_period"]["orders_paid"] == 2
    assert result["current_period"]["orders_converted"] == 1
    assert result["current_period"]["payment_rate"] == 0.5
    assert result["current_period"]["credits_recharged"] == 110
    assert result["previous_period"]["orders_created"] == 1
    assert result["previous_period"]["orders_converted"] == 0
    assert result["previous_period"]["orders_paid"] == 0


def test_compare_disabled_and_empty_period_flags(db_session: Session) -> None:
    now = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
    no_compare = admin_dashboard(db_session, compare=False, now=now)
    assert no_compare["window"]["compare_enabled"] is False
    assert no_compare["previous_period"] is None
    assert no_compare["previous_series"] == []
    assert no_compare["current_period"]["has_data"] is False

    user = _add_user(
        db_session,
        "previous-only@example.com",
        datetime(2026, 5, 25, 1, tzinfo=timezone.utc),
    )
    db_session.add(
        GenerationJob(
            user_id=user.id,
            client_request_id="previous-only-job",
            job_type="asset",
            status="succeeded",
            created_at=datetime(2026, 5, 25, 2, tzinfo=timezone.utc),
            finished_at=datetime(2026, 5, 25, 2, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    result = admin_dashboard(db_session, now=now)
    assert result["current_period"]["has_data"] is False
    assert result["previous_period"]["has_data"] is True


def test_dashboard_route_query_aliases_and_422_validation(db_session: Session) -> None:
    app = FastAPI()
    app.include_router(admin_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin] = lambda: User(
        email="route-admin@example.com",
        password_hash="x",
        role="admin",
    )
    today = datetime.now(timezone.utc).date()

    with TestClient(app) as client:
        response = client.get(
            "/admin/dashboard",
            params={
                "range": "custom",
                "granularity": "day",
                "compare": "false",
                "from": today.isoformat(),
                "to": today.isoformat(),
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["window"]["range"] == "custom"
        assert payload["window"]["granularity"] == "day"
        assert payload["window"]["compare_enabled"] is False

        assert client.get("/admin/dashboard", params={"range": "custom"}).status_code == 422
        assert (
            client.get(
                "/admin/dashboard",
                params={"range": "30d", "granularity": "hour"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/admin/dashboard",
                params={
                    "range": "custom",
                    "from": today.isoformat(),
                    "to": (today + timedelta(days=1)).isoformat(),
                },
            ).status_code
            == 422
        )
        assert client.get("/admin/dashboard", params={"range": "bad"}).status_code == 422


def test_payment_order_paid_at_is_indexed() -> None:
    assert PaymentOrder.__table__.c.paid_at.index is True
