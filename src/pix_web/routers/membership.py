"""月卡会员接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.membership import ensure_default_membership_plans, get_plan, get_user_membership, is_active, list_enabled_plans
from pix_web.models import MembershipPlan, User
from pix_web.payment_providers import create_checkout
from pix_web.routers.billing import _checkout_return_to
from pix_web.schemas import MembershipCheckoutRequest, MembershipPlanResponse, PaymentCheckoutResponse, PaymentOrderResponse, UserMembershipResponse
from pix_web.security import get_current_user, get_db
from pix_web.system_settings import load_effective_web_settings

router = APIRouter(prefix="/membership", tags=["membership"])


@router.get("/plans", response_model=list[MembershipPlanResponse])
def plans(db: Session = Depends(get_db)) -> list[MembershipPlan]:
    return list_enabled_plans(db)


@router.get("/me", response_model=UserMembershipResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserMembershipResponse:
    ensure_default_membership_plans(db)
    membership = get_user_membership(db, user.id)
    if membership is None:
        return UserMembershipResponse(plan_key="", name="", daily_quota=0, status="none", expires_at=None, active=False)
    plan = get_plan(db, membership.plan_key)
    return UserMembershipResponse(
        plan_key=membership.plan_key,
        name=plan.name if plan is not None else membership.plan_key,
        daily_quota=membership.daily_quota,
        status=membership.status,
        expires_at=membership.expires_at,
        active=is_active(membership),
    )


@router.post("/checkout", response_model=PaymentCheckoutResponse)
def checkout(
    req: MembershipCheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentCheckoutResponse:
    settings: WebSettings = load_effective_web_settings(db, request.app.state.web_settings)
    result = create_checkout(
        db,
        user,
        provider=req.provider,
        settings=settings,
        membership_plan_key=req.plan_key,
        return_to=_checkout_return_to(request, settings),
    )
    return PaymentCheckoutResponse(
        order=PaymentOrderResponse.model_validate(result.order),
        provider=result.provider,
        payment_url=result.payment_url,
        code_url=result.code_url,
    )
