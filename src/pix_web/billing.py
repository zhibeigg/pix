"""充值订单与支付事件。"""

from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.credits import recharge_credits
from pix_web.models import CreditPackage, PaymentEvent, PaymentOrder, User, utcnow

DEFAULT_PACKAGES: list[dict[str, object]] = [
    {"key": "starter", "name": "Starter", "credits": 100, "amount_cents": 990, "currency": "cny", "sort_order": 10},
    {"key": "studio", "name": "Studio", "credits": 500, "amount_cents": 3900, "currency": "cny", "sort_order": 20},
    {"key": "pro", "name": "Pro", "credits": 1500, "amount_cents": 9900, "currency": "cny", "sort_order": 30},
]
CUSTOM_RECHARGE_MIN_CREDITS = 10
CUSTOM_RECHARGE_MAX_CREDITS = 100000
CUSTOM_RECHARGE_SUGGESTED_CREDITS = [50, 100, 200, 500, 1000]


def ensure_default_packages(db: Session) -> None:
    changed = False
    for item in DEFAULT_PACKAGES:
        exists = db.scalar(select(CreditPackage).where(CreditPackage.key == item["key"]))
        if exists is None:
            db.add(CreditPackage(**item))
            changed = True
    if changed:
        db.commit()


def list_enabled_packages(db: Session) -> list[CreditPackage]:
    ensure_default_packages(db)
    return list(
        db.scalars(
            select(CreditPackage)
            .where(CreditPackage.enabled.is_(True))
            .order_by(CreditPackage.sort_order.asc(), CreditPackage.amount_cents.asc())
        )
    )


def normalize_payment_provider(provider: str) -> str:
    clean = provider.strip().lower()
    if clean == "wechat":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="微信支付已关闭")
    if clean not in {"mock", "alipay"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的支付方式")
    return clean


def _persist_payment_order(
    db: Session,
    user: User,
    *,
    provider: str,
    credits: int,
    amount_cents: int,
    currency: str,
    package_id: int | None = None,
    order_kind: str = "recharge",
    membership_plan_key: str | None = None,
) -> PaymentOrder:
    provider = normalize_payment_provider(provider)
    order = PaymentOrder(
        user_id=user.id,
        package_id=package_id,
        provider=provider,
        provider_order_id=f"{provider}-{uuid4().hex}",
        status="pending",
        amount_cents=amount_cents,
        currency=currency,
        credits=credits,
        order_kind=order_kind,
        membership_plan_key=membership_plan_key,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def create_membership_order(db: Session, user: User, plan_key: str, *, provider: str = "mock") -> PaymentOrder:
    """创建月卡会员订单：金额取自档位，credits=0（到账时激活会员而非充点）。"""
    from pix_web.membership import ensure_default_membership_plans, get_plan

    ensure_default_membership_plans(db)
    plan = get_plan(db, plan_key)
    if plan is None or not plan.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="月卡档位不存在或已停用")
    return _persist_payment_order(
        db,
        user,
        provider=provider,
        credits=0,
        amount_cents=plan.amount_cents,
        currency=plan.currency,
        order_kind="membership",
        membership_plan_key=plan.key,
    )


def create_payment_order(db: Session, user: User, package_key: str, *, provider: str = "mock") -> PaymentOrder:
    ensure_default_packages(db)
    package = db.scalar(
        select(CreditPackage).where(CreditPackage.key == package_key, CreditPackage.enabled.is_(True))
    )
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值套餐不存在或已停用")
    return _persist_payment_order(
        db,
        user,
        provider=provider,
        credits=package.credits,
        amount_cents=package.amount_cents,
        currency=package.currency,
        package_id=package.id,
    )


def _custom_recharge_base(db: Session) -> CreditPackage | None:
    ensure_default_packages(db)
    return db.scalar(
        select(CreditPackage)
        .where(CreditPackage.enabled.is_(True), CreditPackage.credits > 0, CreditPackage.amount_cents > 0)
        .order_by(CreditPackage.sort_order.asc(), CreditPackage.amount_cents.asc())
        .limit(1)
    )


def _default_custom_base() -> dict[str, object]:
    return DEFAULT_PACKAGES[0]


def custom_recharge_options(db: Session) -> dict[str, object]:
    base = _custom_recharge_base(db)
    if base is None:
        default_base = _default_custom_base()
        base_key = str(default_base["key"])
        base_credits = int(default_base["credits"])
        base_amount_cents = int(default_base["amount_cents"])
        currency = str(default_base["currency"])
    else:
        base_key = base.key
        base_credits = base.credits
        base_amount_cents = base.amount_cents
        currency = base.currency
    return {
        "min_credits": CUSTOM_RECHARGE_MIN_CREDITS,
        "max_credits": CUSTOM_RECHARGE_MAX_CREDITS,
        "currency": currency,
        "unit_amount_cents_per_credit": base_amount_cents / base_credits,
        "base_package_key": base_key,
        "base_package_credits": base_credits,
        "base_package_amount_cents": base_amount_cents,
        "suggested_credits": CUSTOM_RECHARGE_SUGGESTED_CREDITS,
    }


def calculate_custom_recharge_amount_cents(db: Session, credits: int) -> tuple[int, str]:
    if credits < CUSTOM_RECHARGE_MIN_CREDITS or credits > CUSTOM_RECHARGE_MAX_CREDITS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="自定义充值点数超出允许范围")
    options = custom_recharge_options(db)
    base_credits = int(options["base_package_credits"])
    base_amount_cents = int(options["base_package_amount_cents"])
    amount_cents = (base_amount_cents * credits + base_credits - 1) // base_credits
    return amount_cents, str(options["currency"])


def create_custom_payment_order(db: Session, user: User, credits: int, *, provider: str = "mock") -> PaymentOrder:
    amount_cents, currency = calculate_custom_recharge_amount_cents(db, credits)
    return _persist_payment_order(
        db,
        user,
        provider=provider,
        credits=credits,
        amount_cents=amount_cents,
        currency=currency,
    )


def list_payment_orders(db: Session, user: User, *, limit: int = 50) -> list[PaymentOrder]:
    return list(
        db.scalars(
            select(PaymentOrder)
            .where(PaymentOrder.user_id == user.id)
            .order_by(PaymentOrder.created_at.desc())
            .limit(max(1, min(200, limit)))
        )
    )


def list_all_payment_orders(db: Session, *, limit: int = 100) -> list[PaymentOrder]:
    return list(
        db.scalars(
            select(PaymentOrder)
            .order_by(PaymentOrder.created_at.desc())
            .limit(max(1, min(500, limit)))
        )
    )


def mark_order_paid(db: Session, order: PaymentOrder, *, provider_event_id: str, payload: dict | None = None) -> PaymentOrder:
    event = db.scalar(select(PaymentEvent).where(PaymentEvent.provider_event_id == provider_event_id))
    if event is not None:
        db.refresh(order)
        return order

    event = PaymentEvent(
        provider=order.provider,
        provider_event_id=provider_event_id,
        order_id=order.id,
        payload_json=payload or {},
        processed=True,
    )
    db.add(event)

    if order.status != "paid":
        order.status = "paid"
        order.paid_at = utcnow()
        user = db.get(User, order.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单用户不存在")
        if order.order_kind == "membership":
            from pix_web.membership import activate_or_extend

            activate_or_extend(db, user, order.membership_plan_key or "")
        else:
            recharge_credits(db, user, order.credits, note=f"充值订单 #{order.id} 到账")
        from pix_web.referrals import create_reward_for_paid_order
        from pix_web.system_settings import load_referral_settings

        create_reward_for_paid_order(db, order, load_referral_settings(db))

    db.commit()
    db.refresh(order)
    return order


def mock_pay_order(db: Session, order_id: int) -> PaymentOrder:
    order = db.get(PaymentOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值订单不存在")
    return mark_order_paid(
        db,
        order,
        provider_event_id=f"mock-pay:{order.id}",
        payload={"kind": "admin_mock_pay", "order_id": order.id},
    )


def process_mock_webhook(db: Session, *, order_id: int, event_id: str) -> PaymentOrder:
    order = db.get(PaymentOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值订单不存在")
    return mark_order_paid(
        db,
        order,
        provider_event_id=f"mock-webhook:{event_id}",
        payload={"kind": "mock_webhook", "event_id": event_id, "order_id": order.id},
    )
