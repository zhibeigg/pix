"""邀请奖励与返佣服务。"""

from __future__ import annotations

import math
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.credits import add_transaction, ensure_credit_account
from pix_web.models import (
    CreditPackage,
    PaymentOrder,
    ReferralInvite,
    ReferralProfile,
    ReferralReward,
    ReferralSettlement,
    User,
    utcnow,
)
from pix_web.system_settings import ReferralSettings, load_referral_settings

DEFAULT_REFERRAL_CURRENCY = "cny"
_FALLBACK_BASE_PACKAGE_CREDITS = 100
_FALLBACK_BASE_PACKAGE_AMOUNT_CENTS = 990


def _clean_code(value: str | None) -> str:
    return (value or "").strip().upper()


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def frontend_invite_base_url(frontend_base_url: str, public_base_url: str) -> str:
    configured = (frontend_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    base = (public_base_url or "").strip().rstrip("/") or "http://127.0.0.1:8000"
    parts = urlsplit(base)
    path = parts.path.rstrip("/")
    if path.lower() == "/api":
        path = ""
    elif path.lower().endswith("/api"):
        path = path[:-4].rstrip("/")
    normalized = urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")
    return normalized or base


def _invite_url(frontend_base_url: str, public_base_url: str, code: str) -> str:
    base = frontend_invite_base_url(frontend_base_url, public_base_url)
    return f"{base}/?aff={code}#auth-panel"


def _new_referral_code() -> str:
    return f"P{secrets.token_hex(4)}".upper()


def ensure_referral_profile(db: Session, user: User) -> ReferralProfile:
    profile = db.scalar(select(ReferralProfile).where(ReferralProfile.user_id == user.id))
    if profile is not None:
        return profile
    for _ in range(12):
        code = _new_referral_code()
        exists = db.scalar(select(ReferralProfile).where(ReferralProfile.code == code))
        if exists is None:
            profile = ReferralProfile(user_id=user.id, code=code)
            db.add(profile)
            db.flush()
            return profile
    raise RuntimeError("邀请码生成失败")


def bind_referral_invite(
    db: Session, user: User, referral_code: str | None, settings: ReferralSettings
) -> ReferralInvite | None:
    if not settings.enabled:
        return None
    code = _clean_code(referral_code)
    if not code:
        return None
    existing = db.scalar(select(ReferralInvite).where(ReferralInvite.referred_user_id == user.id))
    if existing is not None:
        return existing
    profile = db.scalar(select(ReferralProfile).where(ReferralProfile.code == code))
    if profile is None or profile.user_id == user.id:
        return None
    invite = ReferralInvite(
        referrer_id=profile.user_id, referred_user_id=user.id, code=profile.code
    )
    db.add(invite)
    db.flush()
    return invite


def create_reward_for_paid_order(
    db: Session, order: PaymentOrder, settings: ReferralSettings
) -> ReferralReward | None:
    if not settings.enabled or order.amount_cents <= 0:
        return None
    existing = db.scalar(select(ReferralReward).where(ReferralReward.order_id == order.id))
    if existing is not None:
        return existing
    invite = db.scalar(
        select(ReferralInvite).where(ReferralInvite.referred_user_id == order.user_id)
    )
    if invite is None:
        return None
    amount_cents = order.amount_cents * max(0, min(10000, settings.commission_rate_bps)) // 10000
    if amount_cents <= 0:
        return None
    now = utcnow()
    available_at = now + timedelta(days=max(0, settings.pending_days))
    status_value = "available" if _coerce_utc(available_at) <= _coerce_utc(now) else "pending"
    reward = ReferralReward(
        referrer_id=invite.referrer_id,
        referred_user_id=invite.referred_user_id,
        invite_id=invite.id,
        order_id=order.id,
        order_amount_cents=order.amount_cents,
        order_credits=order.credits,
        amount_cents=amount_cents,
        remaining_cents=amount_cents,
        currency=(order.currency or DEFAULT_REFERRAL_CURRENCY).lower(),
        rate_bps=settings.commission_rate_bps,
        status=status_value,
        available_at=available_at,
    )
    db.add(reward)
    db.flush()
    return reward


def mature_available_rewards(db: Session, user_id: int) -> None:
    now = utcnow()
    changed = False
    rewards = list(
        db.scalars(
            select(ReferralReward).where(
                ReferralReward.referrer_id == user_id,
                ReferralReward.status == "pending",
                ReferralReward.remaining_cents > 0,
            )
        )
    )
    for reward in rewards:
        if _coerce_utc(reward.available_at) <= _coerce_utc(now):
            reward.status = "available"
            changed = True
    if changed:
        db.flush()


def _base_package_for_transfer(db: Session, currency: str) -> tuple[int, int]:
    package = db.scalar(
        select(CreditPackage)
        .where(
            CreditPackage.enabled.is_(True),
            CreditPackage.credits > 0,
            CreditPackage.amount_cents > 0,
            func.lower(CreditPackage.currency) == currency.lower(),
        )
        .order_by(CreditPackage.sort_order.asc(), CreditPackage.amount_cents.asc())
        .limit(1)
    )
    if package is not None:
        return package.credits, package.amount_cents
    return _FALLBACK_BASE_PACKAGE_CREDITS, _FALLBACK_BASE_PACKAGE_AMOUNT_CENTS


def _available_rewards(db: Session, user_id: int, currency: str) -> list[ReferralReward]:
    mature_available_rewards(db, user_id)
    return list(
        db.scalars(
            select(ReferralReward)
            .where(
                ReferralReward.referrer_id == user_id,
                ReferralReward.currency == currency.lower(),
                ReferralReward.status == "available",
                ReferralReward.remaining_cents > 0,
            )
            .order_by(ReferralReward.available_at.asc(), ReferralReward.id.asc())
        )
    )


def _deduct_available_rewards(
    db: Session, user_id: int, *, currency: str, amount_cents: int
) -> int:
    if amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="结算金额必须大于 0"
        )
    remaining = amount_cents
    for reward in _available_rewards(db, user_id, currency):
        if remaining <= 0:
            break
        used = min(reward.remaining_cents, remaining)
        reward.remaining_cents -= used
        remaining -= used
        if reward.remaining_cents <= 0:
            reward.status = "settled"
            reward.settled_at = utcnow()
    deducted = amount_cents - remaining
    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="可用邀请收益不足"
        )
    db.flush()
    return deducted


def transfer_available_rewards_to_credits(
    db: Session, user: User, *, currency: str = DEFAULT_REFERRAL_CURRENCY
) -> ReferralSettlement:
    currency = (currency or DEFAULT_REFERRAL_CURRENCY).lower()
    rewards = _available_rewards(db, user.id, currency)
    available_cents = sum(reward.remaining_cents for reward in rewards)
    base_credits, base_amount_cents = _base_package_for_transfer(db, currency)
    credits = math.floor(available_cents * base_credits / base_amount_cents)
    if credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="可用收益不足 1 点，暂不可划转",
        )
    spend_cents = math.ceil(credits * base_amount_cents / base_credits)
    spend_cents = min(spend_cents, available_cents)
    _deduct_available_rewards(db, user.id, currency=currency, amount_cents=spend_cents)
    account = ensure_credit_account(db, user)
    account.available_credits += credits
    account.total_recharged += credits
    settlement = ReferralSettlement(
        user_id=user.id,
        type="transfer",
        amount_cents=spend_cents,
        currency=currency,
        credits=credits,
        status="completed",
        note="邀请奖励划转到点数余额",
    )
    db.add(settlement)
    db.flush()
    add_transaction(
        db,
        user_id=user.id,
        type="referral_transfer",
        amount=credits,
        balance_after=account.available_credits,
        note=f"邀请奖励划转 #{settlement.id}",
    )
    return settlement


def create_withdrawal_request(
    db: Session,
    user: User,
    *,
    amount_cents: int,
    currency: str = DEFAULT_REFERRAL_CURRENCY,
    note: str = "",
) -> ReferralSettlement:
    currency = (currency or DEFAULT_REFERRAL_CURRENCY).lower()
    _deduct_available_rewards(db, user.id, currency=currency, amount_cents=amount_cents)
    settlement = ReferralSettlement(
        user_id=user.id,
        type="withdrawal",
        amount_cents=amount_cents,
        currency=currency,
        credits=0,
        status="pending",
        note=note.strip() or "邀请奖励提现申请",
    )
    db.add(settlement)
    db.flush()
    return settlement


def referral_summary(
    db: Session, user: User, *, public_base_url: str, frontend_base_url: str = ""
) -> dict[str, Any]:
    settings = load_referral_settings(db)
    profile = ensure_referral_profile(db, user)
    mature_available_rewards(db, user.id)
    db.flush()

    invite_rows = list(
        db.execute(
            select(ReferralInvite, User)
            .join(User, User.id == ReferralInvite.referred_user_id)
            .where(ReferralInvite.referrer_id == user.id)
            .order_by(ReferralInvite.created_at.desc())
            .limit(100)
        )
    )
    reward_rows = list(
        db.execute(
            select(ReferralReward, User)
            .join(User, User.id == ReferralReward.referred_user_id)
            .where(ReferralReward.referrer_id == user.id)
            .order_by(ReferralReward.created_at.desc())
            .limit(100)
        )
    )
    settlements = list(
        db.scalars(
            select(ReferralSettlement)
            .where(ReferralSettlement.user_id == user.id)
            .order_by(ReferralSettlement.created_at.desc())
            .limit(100)
        )
    )

    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"pending_cents": 0, "available_cents": 0, "total_reward_cents": 0}
    )
    all_rewards = list(
        db.scalars(select(ReferralReward).where(ReferralReward.referrer_id == user.id))
    )
    for reward in all_rewards:
        currency = reward.currency or DEFAULT_REFERRAL_CURRENCY
        totals[currency]["total_reward_cents"] += reward.amount_cents
        if reward.status == "pending":
            totals[currency]["pending_cents"] += reward.remaining_cents
        elif reward.status == "available":
            totals[currency]["available_cents"] += reward.remaining_cents

    if DEFAULT_REFERRAL_CURRENCY in totals:
        primary_currency = DEFAULT_REFERRAL_CURRENCY
    elif totals:
        primary_currency = sorted(totals)[0]
    else:
        primary_currency = DEFAULT_REFERRAL_CURRENCY
    primary = totals[primary_currency]

    return {
        "code": profile.code,
        "invite_url": _invite_url(frontend_base_url, public_base_url, profile.code),
        "enabled": settings.enabled,
        "commission_rate_bps": settings.commission_rate_bps,
        "pending_days": settings.pending_days,
        "primary_currency": primary_currency,
        "pending_cents": primary["pending_cents"],
        "available_cents": primary["available_cents"],
        "total_reward_cents": primary["total_reward_cents"],
        "invited_count": len(invite_rows),
        "totals_by_currency": [
            {"currency": currency, **amounts} for currency, amounts in sorted(totals.items())
        ],
        "invites": [
            {
                "id": invite.id,
                "referred_user_id": invite.referred_user_id,
                "referred_user_email": referred.email,
                "referred_user_display_name": referred.display_name,
                "created_at": invite.created_at,
            }
            for invite, referred in invite_rows
        ],
        "rewards": [
            {
                "id": reward.id,
                "referred_user_id": reward.referred_user_id,
                "referred_user_email": referred.email,
                "order_id": reward.order_id,
                "order_amount_cents": reward.order_amount_cents,
                "order_credits": reward.order_credits,
                "amount_cents": reward.amount_cents,
                "remaining_cents": reward.remaining_cents,
                "currency": reward.currency,
                "rate_bps": reward.rate_bps,
                "status": reward.status,
                "available_at": reward.available_at,
                "created_at": reward.created_at,
            }
            for reward, referred in reward_rows
        ],
        "settlements": settlements,
    }
