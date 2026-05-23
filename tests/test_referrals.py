from __future__ import annotations

from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix_web.billing import mark_order_paid
from pix_web.models import Base, CreditAccount, PaymentOrder, ReferralInvite, ReferralReward, User, utcnow
from pix_web.referrals import (
    bind_referral_invite,
    create_withdrawal_request,
    ensure_referral_profile,
    referral_summary,
    transfer_available_rewards_to_credits,
)
from pix_web.system_settings import load_referral_settings


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def _user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="x", display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    db.add(CreditAccount(user_id=user.id))
    db.flush()
    return user


def _paid_order(db: Session, user: User, *, amount_cents: int = 9900, credits: int = 1000) -> PaymentOrder:
    order = PaymentOrder(
        user_id=user.id,
        provider="mock",
        provider_order_id=f"mock-{user.id}-{amount_cents}",
        status="pending",
        amount_cents=amount_cents,
        currency="cny",
        credits=credits,
    )
    db.add(order)
    db.flush()
    return mark_order_paid(db, order, provider_event_id=f"event-{order.provider_order_id}")


def test_referral_code_binds_registration_invite() -> None:
    db = _session()
    referrer = _user(db, "maker@example.com")
    referred = _user(db, "friend@example.com")
    profile = ensure_referral_profile(db, referrer)

    invite = bind_referral_invite(db, referred, profile.code.lower(), load_referral_settings(db))

    assert invite is not None
    assert invite.referrer_id == referrer.id
    assert invite.referred_user_id == referred.id
    assert invite.code == profile.code
    assert db.scalar(select(ReferralInvite).where(ReferralInvite.referred_user_id == referred.id)) is not None


def test_paid_order_creates_pending_referral_reward() -> None:
    db = _session()
    referrer = _user(db, "maker@example.com")
    referred = _user(db, "friend@example.com")
    code = ensure_referral_profile(db, referrer).code
    bind_referral_invite(db, referred, code, load_referral_settings(db))

    order = _paid_order(db, referred, amount_cents=9900, credits=1000)
    reward = db.scalar(select(ReferralReward).where(ReferralReward.order_id == order.id))

    assert reward is not None
    assert reward.referrer_id == referrer.id
    assert reward.amount_cents == 990
    assert reward.remaining_cents == 990
    assert reward.currency == "cny"
    assert reward.status == "pending"


def test_available_reward_transfers_to_credit_balance_and_keeps_unconvertible_remainder() -> None:
    db = _session()
    referrer = _user(db, "maker@example.com")
    referred = _user(db, "friend@example.com")
    code = ensure_referral_profile(db, referrer).code
    bind_referral_invite(db, referred, code, load_referral_settings(db))
    order = _paid_order(db, referred, amount_cents=1000, credits=100)
    reward = db.scalar(select(ReferralReward).where(ReferralReward.order_id == order.id))
    assert reward is not None
    reward.available_at = utcnow() - timedelta(days=1)
    reward.status = "pending"
    db.flush()

    settlement = transfer_available_rewards_to_credits(db, referrer)
    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == referrer.id))

    assert settlement.type == "transfer"
    assert settlement.credits == 10
    assert settlement.amount_cents == 99
    assert reward.remaining_cents == 1
    assert reward.status == "available"
    assert account is not None
    assert account.available_credits == 10


def test_withdrawal_request_deducts_available_rewards() -> None:
    db = _session()
    referrer = _user(db, "maker@example.com")
    referred = _user(db, "friend@example.com")
    code = ensure_referral_profile(db, referrer).code
    bind_referral_invite(db, referred, code, load_referral_settings(db))
    order = _paid_order(db, referred, amount_cents=9900, credits=1000)
    reward = db.scalar(select(ReferralReward).where(ReferralReward.order_id == order.id))
    assert reward is not None
    reward.available_at = utcnow() - timedelta(days=1)
    reward.status = "pending"
    db.flush()

    settlement = create_withdrawal_request(db, referrer, amount_cents=990, currency="cny", note="支付宝账户")

    assert settlement.type == "withdrawal"
    assert settlement.status == "pending"
    assert settlement.amount_cents == 990
    assert reward.remaining_cents == 0
    assert reward.status == "settled"


def test_referral_summary_returns_invite_url_and_totals() -> None:
    db = _session()
    referrer = _user(db, "maker@example.com")
    referred = _user(db, "friend@example.com")
    code = ensure_referral_profile(db, referrer).code
    bind_referral_invite(db, referred, code, load_referral_settings(db))
    _paid_order(db, referred, amount_cents=9900, credits=1000)

    data = referral_summary(db, referrer, public_base_url="https://www.packyapi.com")

    assert data["code"] == code
    assert data["invite_url"] == f"https://www.packyapi.com/?aff={code}#auth-panel"
    assert data["invited_count"] == 1
    assert data["pending_cents"] == 990
    assert data["total_reward_cents"] == 990
