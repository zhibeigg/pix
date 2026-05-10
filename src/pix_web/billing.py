"""充值订单与支付事件。"""

from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.credits import recharge_credits
from pix_web.models import CreditPackage, PaymentEvent, PaymentOrder, User, utcnow

DEFAULT_PACKAGES: list[dict[str, object]] = [
    {"key": "starter", "name": "Starter", "credits": 100, "amount_cents": 990, "currency": "usd", "sort_order": 10},
    {"key": "studio", "name": "Studio", "credits": 500, "amount_cents": 3900, "currency": "usd", "sort_order": 20},
    {"key": "pro", "name": "Pro", "credits": 1500, "amount_cents": 9900, "currency": "usd", "sort_order": 30},
]


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


def create_payment_order(db: Session, user: User, package_key: str) -> PaymentOrder:
    ensure_default_packages(db)
    package = db.scalar(
        select(CreditPackage).where(CreditPackage.key == package_key, CreditPackage.enabled.is_(True))
    )
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值套餐不存在或已停用")
    order = PaymentOrder(
        user_id=user.id,
        package_id=package.id,
        provider="mock",
        provider_order_id=f"mock-{uuid4().hex}",
        status="pending",
        amount_cents=package.amount_cents,
        currency=package.currency,
        credits=package.credits,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


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
        recharge_credits(db, user, order.credits, note=f"充值订单 #{order.id} 到账")

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
