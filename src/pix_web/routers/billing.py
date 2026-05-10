"""充值与支付订单接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pix_web.billing import (
    create_payment_order,
    list_all_payment_orders,
    list_enabled_packages,
    list_payment_orders,
    mock_pay_order,
    process_mock_webhook,
)
from pix_web.models import CreditPackage, PaymentOrder, User
from pix_web.schemas import CreditPackageResponse, MockWebhookRequest, PaymentOrderCreateRequest, PaymentOrderResponse
from pix_web.security import get_current_user, get_db, require_admin

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/packages", response_model=list[CreditPackageResponse])
def packages(db: Session = Depends(get_db)) -> list[CreditPackage]:
    return list_enabled_packages(db)


@router.post("/orders", response_model=PaymentOrderResponse)
def create_order(
    req: PaymentOrderCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentOrder:
    return create_payment_order(db, user, req.package_key)


@router.get("/orders", response_model=list[PaymentOrderResponse])
def orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> list[PaymentOrder]:
    return list_payment_orders(db, user, limit=limit)


@router.get("/admin/orders", response_model=list[PaymentOrderResponse])
def admin_orders(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = 100,
) -> list[PaymentOrder]:
    return list_all_payment_orders(db, limit=limit)


@router.post("/mock-pay/{order_id}", response_model=PaymentOrderResponse)
def mock_pay(
    order_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaymentOrder:
    return mock_pay_order(db, order_id)


@router.post("/webhook/mock", response_model=PaymentOrderResponse)
def mock_webhook(req: MockWebhookRequest, db: Session = Depends(get_db)) -> PaymentOrder:
    return process_mock_webhook(db, order_id=req.order_id, event_id=req.event_id)
