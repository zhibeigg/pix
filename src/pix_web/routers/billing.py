"""充值与支付订单接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from pix_web.billing import (
    create_custom_payment_order,
    create_payment_order,
    custom_recharge_options,
    list_all_payment_orders,
    list_enabled_packages,
    list_payment_orders,
    mock_pay_order,
    process_mock_webhook,
)
from pix_web.models import CreditPackage, PaymentOrder, User
from pix_web.payment_providers import (
    create_checkout,
    handle_alipay_app_gateway_message,
    handle_alipay_notify,
    handle_wechat_notify,
)
from pix_web.schemas import (
    CreditPackageResponse,
    CustomRechargeOptionsResponse,
    MockWebhookRequest,
    PaymentCheckoutRequest,
    PaymentCheckoutResponse,
    PaymentOrderCreateRequest,
    PaymentOrderResponse,
)
from pix_web.security import get_current_user, get_db, require_admin
from pix_web.system_settings import load_effective_web_settings

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/packages", response_model=list[CreditPackageResponse])
def packages(db: Session = Depends(get_db)) -> list[CreditPackage]:
    return list_enabled_packages(db)


@router.get("/custom-recharge-options", response_model=CustomRechargeOptionsResponse)
def custom_options(db: Session = Depends(get_db)) -> dict[str, object]:
    return custom_recharge_options(db)


@router.post("/checkout", response_model=PaymentCheckoutResponse)
def checkout(
    req: PaymentCheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentCheckoutResponse:
    settings = load_effective_web_settings(db, request.app.state.web_settings)
    result = create_checkout(
        db,
        user,
        provider=req.provider,
        settings=settings,
        package_key=req.package_key,
        custom_credits=req.custom_credits,
    )
    return PaymentCheckoutResponse(
        order=PaymentOrderResponse.model_validate(result.order),
        provider=result.provider,
        payment_url=result.payment_url,
        code_url=result.code_url,
    )


@router.post("/orders", response_model=PaymentOrderResponse)
def create_order(
    req: PaymentOrderCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentOrder:
    if req.custom_credits is not None:
        return create_custom_payment_order(db, user, req.custom_credits, provider=req.provider)
    return create_payment_order(db, user, req.package_key or "", provider=req.provider)


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


@router.post("/webhook/alipay")
async def alipay_webhook(request: Request, db: Session = Depends(get_db)) -> Response:
    form = await request.form()
    settings = load_effective_web_settings(db, request.app.state.web_settings)
    result = handle_alipay_notify(db, {key: str(value) for key, value in form.items()}, settings)
    return Response(content=result, media_type="text/plain")


@router.post("/webhook/alipay/app-gateway")
async def alipay_app_gateway(request: Request, db: Session = Depends(get_db)) -> Response:
    form = await request.form()
    settings = load_effective_web_settings(db, request.app.state.web_settings)
    result = handle_alipay_app_gateway_message(db, {key: str(value) for key, value in form.items()}, settings)
    return Response(content=result, media_type="text/plain")


@router.post("/webhook/wechat")
async def wechat_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    body = await request.body()
    settings = load_effective_web_settings(db, request.app.state.web_settings)
    return handle_wechat_notify(db, dict(request.headers), body, settings)


@router.get("/return/alipay")
def alipay_return(order_id: int | None = None) -> dict[str, str | int | None]:
    return {"status": "ok", "message": "请返回 Pix 页面刷新订单状态", "order_id": order_id}
