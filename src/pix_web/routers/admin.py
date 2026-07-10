"""管理员接口。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.announcement_service import (
    active_user_emails,
    create_announcement,
    delete_announcement,
    load_announcement_list,
    publish_site_announcement,
    update_announcement,
)
from pix_web.config import WebSettings
from pix_web.credits import adjust_credits
from pix_web.dashboard import admin_dashboard
from pix_web.job_observability import (
    admin_fail_job_and_refund,
    cancel_job_and_refund,
    load_job_with_outputs,
)
from pix_web.metrics import task_performance_metrics
from pix_web.membership import is_active as is_membership_active
from pix_web.jobs import retry_failed_job
from pix_web.email_sender import (
    EmailDeliveryError,
    send_announcement_email,
    send_announcement_email_batch_task,
    send_verification_email,
)
from pix_web.email_verification import generate_code
from pix_web.models import (
    CreditAccount,
    CreditPackage,
    GenerationJob,
    MembershipPlan,
    PaymentOrder,
    PricingRule,
    PromoLink,
    User,
    UserMembership,
)
from pix_web.promo import create_promo_link, delete_promo_link, promo_link_stats, update_promo_link
from pix_web.queue import enqueue_jobs
from pix_web.referrals import frontend_invite_base_url
from pix_web.schemas import (
    AdminAdjustCreditsRequest,
    AdminBatchAdjustCreditsRequest,
    AdminBatchAdjustCreditsResponse,
    AdminDashboardResponse,
    AdminJobResponse,
    AdminPaymentOrderResponse,
    AdminUserResponse,
    PerformanceMetricsResponse,
    AnnouncementCreateRequest,
    AnnouncementItemResponse,
    AnnouncementListResponse,
    AnnouncementPublishRequest,
    AnnouncementPublishResponse,
    AnnouncementTestEmailRequest,
    AnnouncementUpdateRequest,
    CreditPackageCreateRequest,
    CreditPackageResponse,
    CreditPackageUpdateRequest,
    CreditTransactionResponse,
    MembershipPlanCreateRequest,
    MembershipPlanResponse,
    MembershipPlanUpdateRequest,
    EmailTestRequest,
    EmailTestResponse,
    PricingRuleResponse,
    PricingRuleUpdateRequest,
    PromoLinkCreateRequest,
    PromoLinkResponse,
    PromoLinkStatsResponse,
    PromoLinkUpdateRequest,
    SystemSettingResponse,
    SystemSettingUpdateRequest,
)
from pix_web.security import get_db, get_settings, require_admin
from pix_web.system_settings import (
    AdminSettingView,
    list_admin_settings,
    load_effective_web_settings,
    update_system_setting,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse)
def dashboard(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict[str, int | float]:
    return admin_dashboard(db)


@router.get("/performance-metrics", response_model=PerformanceMetricsResponse)
def performance_metrics(
    range: str = "24h",
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return task_performance_metrics(db, range)


@router.get("/users", response_model=list[AdminUserResponse])
def users(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 100
) -> list[AdminUserResponse]:
    """后台用户列表：附带点数余额与会员状态。批量取账户 / 会员避免 N+1；排序 / 筛选由前端完成。"""
    capped = max(1, min(500, limit))
    user_rows = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(capped)))
    if not user_rows:
        return []
    user_ids = [user.id for user in user_rows]
    accounts = {
        account.user_id: account
        for account in db.scalars(select(CreditAccount).where(CreditAccount.user_id.in_(user_ids)))
    }
    memberships = {
        membership.user_id: membership
        for membership in db.scalars(
            select(UserMembership).where(UserMembership.user_id.in_(user_ids))
        )
    }
    now = datetime.now(timezone.utc)
    result: list[AdminUserResponse] = []
    for user in user_rows:
        account = accounts.get(user.id)
        membership = memberships.get(user.id)
        membership_active = is_membership_active(membership, now)
        result.append(
            AdminUserResponse(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                status=user.status,
                created_at=user.created_at,
                available_credits=account.available_credits if account else 0,
                reserved_credits=account.reserved_credits if account else 0,
                total_recharged=account.total_recharged if account else 0,
                total_consumed=account.total_consumed if account else 0,
                daily_quota_balance=account.daily_quota_balance if account else 0,
                membership_status=(membership.status if membership else None),
                membership_plan_key=(membership.plan_key if membership_active else None),
                membership_expires_at=(membership.expires_at if membership else None),
            )
        )
    return result


@router.get("/orders", response_model=list[AdminPaymentOrderResponse])
def orders(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 200
) -> list[AdminPaymentOrderResponse]:
    """后台订单列表：所有用户的充值 / 月卡订单，附带下单用户信息。排序 / 筛选由前端完成。"""
    capped = max(1, min(500, limit))
    order_rows = list(
        db.scalars(select(PaymentOrder).order_by(PaymentOrder.created_at.desc()).limit(capped))
    )
    if not order_rows:
        return []
    owner_ids = {order.user_id for order in order_rows}
    owners = {owner.id: owner for owner in db.scalars(select(User).where(User.id.in_(owner_ids)))}
    result: list[AdminPaymentOrderResponse] = []
    for order in order_rows:
        owner = owners.get(order.user_id)
        result.append(
            AdminPaymentOrderResponse(
                id=order.id,
                user_id=order.user_id,
                user_email=(owner.email if owner else ""),
                user_display_name=(owner.display_name if owner else ""),
                provider=order.provider,
                provider_order_id=order.provider_order_id,
                status=order.status,
                amount_cents=order.amount_cents,
                currency=order.currency,
                credits=order.credits,
                order_kind=order.order_kind,
                membership_plan_key=order.membership_plan_key,
                created_at=order.created_at,
                paid_at=order.paid_at,
            )
        )
    return result


@router.post("/users/{user_id}/adjust-credits", response_model=CreditTransactionResponse)
def adjust_user_credits(
    user_id: int,
    req: AdminAdjustCreditsRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    tx = adjust_credits(db, user, req.amount, req.note or "管理员调整点数")
    db.commit()
    db.refresh(tx)
    return tx


@router.post("/users/adjust-credits-batch", response_model=AdminBatchAdjustCreditsResponse)
def adjust_users_credits_batch(
    req: AdminBatchAdjustCreditsRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if req.all_users:
        stmt = select(User).where(User.status == "active").order_by(User.id.asc())
    else:
        unique_ids = sorted({int(user_id) for user_id in req.user_ids if int(user_id) > 0})
        if not unique_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="请选择至少一个有效用户"
            )
        stmt = select(User).where(User.id.in_(unique_ids)).order_by(User.id.asc())

    target_users = list(db.scalars(stmt))
    if not target_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="没有找到可调整点数的用户"
        )
    if not req.all_users:
        found_ids = {user.id for user in target_users}
        missing_ids = [user_id for user_id in unique_ids if user_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户不存在：{', '.join(str(user_id) for user_id in missing_ids[:10])}",
            )

    note = req.note or (
        "管理员批量调整点数（全部活跃用户）" if req.all_users else "管理员批量调整点数"
    )
    transactions = [adjust_credits(db, user, req.amount, note) for user in target_users]
    db.commit()
    for tx in transactions:
        db.refresh(tx)
    return {
        "adjusted_count": len(transactions),
        "amount": req.amount,
        "note": note,
        "all_users": req.all_users,
        "transactions": transactions,
    }


@router.get("/jobs", response_model=list[AdminJobResponse])
def jobs(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 100
) -> list[GenerationJob]:
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
        .order_by(GenerationJob.created_at.desc())
        .limit(max(1, min(500, limit)))
    )
    return list(db.scalars(stmt))


@router.post("/jobs/{job_id}/retry", response_model=AdminJobResponse)
def retry_admin_job(
    job_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> GenerationJob:
    failed_job = db.get(GenerationJob, job_id)
    if failed_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    owner = db.get(User, failed_job.user_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务用户不存在")
    job = retry_failed_job(db, owner, job_id, settings)
    enqueue_jobs(settings, [job.id])
    return job


@router.post("/jobs/{job_id}/cancel", response_model=AdminJobResponse)
def cancel_admin_job(
    job_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenerationJob:
    job = load_job_with_outputs(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    try:
        cancel_job_and_refund(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return load_job_with_outputs(db, job_id) or job


@router.post("/jobs/{job_id}/fail-refund", response_model=AdminJobResponse)
def fail_refund_admin_job(
    job_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenerationJob:
    job = load_job_with_outputs(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    try:
        admin_fail_job_and_refund(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return load_job_with_outputs(db, job_id) or job


@router.get("/pricing", response_model=list[PricingRuleResponse])
def pricing(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[PricingRule]:
    return list(db.scalars(select(PricingRule).order_by(PricingRule.key.asc())))


@router.put("/pricing/{key}", response_model=PricingRuleResponse)
def update_pricing(
    key: str,
    req: PricingRuleUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PricingRule:
    rule = db.scalar(select(PricingRule).where(PricingRule.key == key))
    if rule is None:
        rule = PricingRule(key=key)
        db.add(rule)
    rule.price_credits = req.price_credits
    rule.enabled = req.enabled
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/packages", response_model=list[CreditPackageResponse])
def packages(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[CreditPackage]:
    return list(
        db.scalars(
            select(CreditPackage).order_by(
                CreditPackage.sort_order.asc(), CreditPackage.amount_cents.asc()
            )
        )
    )


@router.post("/packages", response_model=CreditPackageResponse)
def create_package(
    req: CreditPackageCreateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CreditPackage:
    existing = db.scalar(select(CreditPackage).where(CreditPackage.key == req.key))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="充值套餐 key 已存在")
    package = CreditPackage(**req.model_dump())
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


@router.put("/packages/{key}", response_model=CreditPackageResponse)
def update_package(
    key: str,
    req: CreditPackageUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CreditPackage:
    package = db.scalar(select(CreditPackage).where(CreditPackage.key == key))
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值套餐不存在")
    package.name = req.name
    package.credits = req.credits
    package.amount_cents = req.amount_cents
    package.currency = req.currency
    package.enabled = req.enabled
    package.sort_order = req.sort_order
    db.commit()
    db.refresh(package)
    return package


@router.get("/membership-plans", response_model=list[MembershipPlanResponse])
def membership_plans(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[MembershipPlan]:
    from pix_web.membership import ensure_default_membership_plans

    ensure_default_membership_plans(db)
    return list(
        db.scalars(
            select(MembershipPlan).order_by(
                MembershipPlan.sort_order.asc(), MembershipPlan.amount_cents.asc()
            )
        )
    )


@router.post("/membership-plans", response_model=MembershipPlanResponse)
def create_membership_plan(
    req: MembershipPlanCreateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MembershipPlan:
    existing = db.scalar(select(MembershipPlan).where(MembershipPlan.key == req.key))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="月卡档位 key 已存在")
    plan = MembershipPlan(**req.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/membership-plans/{key}", response_model=MembershipPlanResponse)
def update_membership_plan(
    key: str,
    req: MembershipPlanUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MembershipPlan:
    plan = db.scalar(select(MembershipPlan).where(MembershipPlan.key == key))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="月卡档位不存在")
    plan.name = req.name
    plan.daily_quota = req.daily_quota
    plan.amount_cents = req.amount_cents
    plan.currency = req.currency
    plan.duration_days = req.duration_days
    plan.enabled = req.enabled
    plan.sort_order = req.sort_order
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/promo-links", response_model=list[PromoLinkStatsResponse])
def promo_links(
    request: Request,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> list[dict[str, object]]:
    """优惠链接列表（附使用量统计与完整优惠链接 URL）。"""
    effective = load_effective_web_settings(db, web_settings)
    base = frontend_invite_base_url(effective.frontend_base_url, effective.public_base_url)
    stats = promo_link_stats(db)
    for item in stats:
        item["promo_url"] = f"{base}/?promo={item['code']}#auth-panel"
    return stats


@router.post("/promo-links", response_model=PromoLinkResponse)
def create_promo_link_route(
    req: PromoLinkCreateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PromoLink:
    link = create_promo_link(
        db,
        code=req.code,
        name=req.name,
        discount_rate=req.discount_rate,
        enabled=req.enabled,
        note=req.note,
    )
    db.commit()
    db.refresh(link)
    return link


@router.put("/promo-links/{link_id}", response_model=PromoLinkResponse)
def update_promo_link_route(
    link_id: int,
    req: PromoLinkUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PromoLink:
    link = update_promo_link(
        db,
        link_id,
        name=req.name,
        discount_rate=req.discount_rate,
        enabled=req.enabled,
        note=req.note,
    )
    db.commit()
    db.refresh(link)
    return link


@router.delete("/promo-links/{link_id}")
def delete_promo_link_route(
    link_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    delete_promo_link(db, link_id)
    db.commit()
    return {"deleted": True}


@router.get("/settings", response_model=list[SystemSettingResponse])
def settings(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> list[AdminSettingView]:
    return list_admin_settings(db, web_settings)


@router.put("/settings/{key}", response_model=SystemSettingResponse)
def update_setting(
    key: str,
    req: SystemSettingUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> AdminSettingView:
    update_system_setting(db, key, req.value or "", clear=req.clear)
    return next(item for item in list_admin_settings(db, web_settings) if item.key == key)


@router.put("/announcement", response_model=AnnouncementPublishResponse)
def publish_announcement(
    req: AnnouncementPublishRequest,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> AnnouncementPublishResponse:
    effective = load_effective_web_settings(db, web_settings)
    outcome = publish_site_announcement(db, title=req.title, body=req.body, enabled=req.enabled)
    recipient_count = 0
    notification_queued = False
    skipped_reason = outcome.skipped_reason
    if outcome.should_notify:
        emails = active_user_emails(db)
        recipient_count = len(emails)
        if emails:
            smtp_ready = effective.email_provider == "console" or (
                effective.email_provider == "smtp" and effective.smtp_host and effective.smtp_from
            )
            if smtp_ready:
                site_url = frontend_invite_base_url(
                    effective.frontend_base_url, effective.public_base_url
                )
                background_tasks.add_task(
                    send_announcement_email_batch_task,
                    effective,
                    emails,
                    title=outcome.announcement.title,
                    body=outcome.announcement.body,
                    site_url=site_url,
                    updated_at=outcome.announcement.updated_at,
                )
                notification_queued = True
                skipped_reason = ""
            else:
                skipped_reason = "smtp_not_configured"
        else:
            skipped_reason = "no_recipients"
    return AnnouncementPublishResponse(
        enabled=outcome.announcement.enabled,
        title=outcome.announcement.title,
        body=outcome.announcement.body,
        updated_at=outcome.announcement.updated_at,
        email_notification_queued=notification_queued,
        email_recipient_count=recipient_count,
        email_skipped_reason=skipped_reason,
    )


@router.get("/announcements", response_model=AnnouncementListResponse)
def admin_list_announcements(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> AnnouncementListResponse:
    """管理员：列出全部公告（含 disabled）。"""
    items = load_announcement_list(db, include_disabled=True, limit=limit)
    active_count = len([a for a in items if a.enabled])
    return AnnouncementListResponse(
        items=[AnnouncementItemResponse.model_validate(a) for a in items],
        active_count=active_count,
    )


@router.post("/announcements", response_model=AnnouncementItemResponse)
def admin_create_announcement(
    req: AnnouncementCreateRequest,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> AnnouncementItemResponse:
    """管理员：创建公告。publish_now=True 时设置 published_at，notify=True 时触发邮件。"""
    announcement = create_announcement(
        db,
        title=req.title,
        body=req.body,
        enabled=req.enabled,
        publish_now=req.publish_now,
    )
    if req.publish_now and req.enabled and req.notify:
        effective = load_effective_web_settings(db, web_settings)
        emails = active_user_emails(db)
        if emails:
            smtp_ready = effective.email_provider == "console" or (
                effective.email_provider == "smtp" and effective.smtp_host and effective.smtp_from
            )
            if smtp_ready:
                site_url = frontend_invite_base_url(
                    effective.frontend_base_url, effective.public_base_url
                )
                background_tasks.add_task(
                    send_announcement_email_batch_task,
                    effective,
                    emails,
                    title=announcement.title,
                    body=announcement.body,
                    site_url=site_url,
                    updated_at=announcement.updated_at,
                )
    return AnnouncementItemResponse.model_validate(announcement)


@router.put("/announcements/{announcement_id}", response_model=AnnouncementItemResponse)
def admin_update_announcement(
    announcement_id: int,
    req: AnnouncementUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AnnouncementItemResponse:
    """管理员：编辑公告。"""
    announcement = update_announcement(
        db,
        announcement_id,
        title=req.title,
        body=req.body,
        enabled=req.enabled,
    )
    return AnnouncementItemResponse.model_validate(announcement)


@router.delete("/announcements/{announcement_id}")
def admin_delete_announcement(
    announcement_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """管理员：删除公告。"""
    delete_announcement(db, announcement_id)
    return {"deleted": True}


@router.post("/announcements/test-email", response_model=EmailTestResponse)
def admin_test_announcement_email(
    req: AnnouncementTestEmailRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> EmailTestResponse:
    """管理员：发送公告测试邮件到指定邮箱。"""
    effective = load_effective_web_settings(db, web_settings)
    site_url = frontend_invite_base_url(effective.frontend_base_url, effective.public_base_url)
    try:
        send_announcement_email(
            effective,
            str(req.email),
            title=req.title,
            body=req.body,
            site_url=site_url,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return EmailTestResponse(
        message="公告测试邮件已发送"
        if effective.email_provider == "smtp"
        else "console 公告测试邮件已生成",
    )


@router.post("/settings/test-email", response_model=EmailTestResponse)
def test_email_setting(
    req: EmailTestRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> EmailTestResponse:
    effective = load_effective_web_settings(db, web_settings)
    code = generate_code()
    try:
        send_verification_email(effective, str(req.email), code)
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return EmailTestResponse(
        message="测试邮件已发送"
        if effective.email_provider == "smtp"
        else "console 测试验证码已生成",
        debug_code=code
        if effective.email_debug_codes or effective.email_provider == "console"
        else None,
    )
