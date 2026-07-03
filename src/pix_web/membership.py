"""月卡会员与每日临时额度。

会员档位（membership_plans）配置每日临时额度、价格与时长；用户购买后写入
user_memberships，续期顺延 expires_at，可切换档位。每日临时额度当天有效、次日
按业务时区（site.timezone，默认 Asia/Shanghai）刷新，仅用于生成任务且优先于永久
点数消耗（见 credits.py）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import MembershipPlan, User, UserMembership, utcnow
from pix_web.system_settings import resolve_site_timezone

# 默认档位：铜/银/金。价格单位为分（cny）。可在后台增删改。
DEFAULT_MEMBERSHIP_PLANS: list[dict[str, object]] = [
    {"key": "bronze", "name": "铜卡", "daily_quota": 100, "amount_cents": 9900, "currency": "cny", "duration_days": 30, "sort_order": 10},
    {"key": "silver", "name": "银卡", "daily_quota": 200, "amount_cents": 19900, "currency": "cny", "duration_days": 30, "sort_order": 20},
    {"key": "gold", "name": "金卡", "daily_quota": 300, "amount_cents": 29900, "currency": "cny", "duration_days": 30, "sort_order": 30},
]


def ensure_default_membership_plans(db: Session) -> None:
    changed = False
    for item in DEFAULT_MEMBERSHIP_PLANS:
        exists = db.scalar(select(MembershipPlan).where(MembershipPlan.key == item["key"]))
        if exists is None:
            db.add(MembershipPlan(**item))
            changed = True
    if changed:
        db.commit()


def list_enabled_plans(db: Session) -> list[MembershipPlan]:
    ensure_default_membership_plans(db)
    return list(
        db.scalars(
            select(MembershipPlan)
            .where(MembershipPlan.enabled.is_(True))
            .order_by(MembershipPlan.sort_order.asc(), MembershipPlan.amount_cents.asc())
        )
    )


def get_plan(db: Session, key: str) -> MembershipPlan | None:
    return db.scalar(select(MembershipPlan).where(MembershipPlan.key == key))


def business_day_key(tz: tzinfo, now: datetime | None = None) -> str:
    """业务时区下的自然日键（YYYY-MM-DD），用于每日额度刷新判断。"""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(tz).strftime("%Y-%m-%d")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def get_user_membership(db: Session, user_id: int) -> UserMembership | None:
    return db.scalar(select(UserMembership).where(UserMembership.user_id == user_id))


def is_active(membership: UserMembership | None, now: datetime | None = None) -> bool:
    if membership is None or membership.status != "active":
        return False
    now_utc = now or datetime.now(timezone.utc)
    expires = _as_utc(membership.expires_at)
    return expires is not None and expires > now_utc


def active_daily_quota(db: Session, user_id: int, now: datetime | None = None) -> int:
    """当前有效会员的每日额度；无有效会员返回 0。"""
    membership = get_user_membership(db, user_id)
    return membership.daily_quota if is_active(membership, now) else 0


def activate_or_extend(db: Session, user: User, plan_key: str) -> UserMembership:
    """激活或续期会员：顺延时长、切换档位，并立即刷新当日临时额度。

    - 已有有效会员：从当前 expires_at 顺延 duration_days；否则从现在起算。
    - 切换档位：更新 plan_key / daily_quota。
    - 立即把当日临时额度提升到新档 daily_quota（当日 date 命中时补足到新额度，
      否则重置为新额度并更新 date）。
    """
    plan = get_plan(db, plan_key)
    if plan is None or not plan.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="月卡档位不存在或已停用")

    now = datetime.now(timezone.utc)
    membership = get_user_membership(db, user.id)
    duration = timedelta(days=max(1, plan.duration_days))

    was_active = is_active(membership, now)
    previous_daily_quota = membership.daily_quota if membership is not None and was_active else 0
    if was_active:
        base = _as_utc(membership.expires_at) or now
        new_expires = base + duration
    else:
        new_expires = now + duration

    if membership is None:
        membership = UserMembership(
            user_id=user.id,
            plan_key=plan.key,
            daily_quota=plan.daily_quota,
            status="active",
            started_at=now,
            expires_at=new_expires,
        )
        db.add(membership)
    else:
        membership.plan_key = plan.key
        membership.daily_quota = plan.daily_quota
        membership.status = "active"
        if not was_active:
            membership.started_at = now
        membership.expires_at = new_expires
    db.flush()

    _grant_today_quota(db, user, plan.daily_quota, previous_daily_quota=previous_daily_quota, now=now)
    return membership


def _grant_today_quota(
    db: Session,
    user: User,
    daily_quota: int,
    *,
    previous_daily_quota: int = 0,
    now: datetime | None = None,
) -> None:
    """购买/续期后处理当日临时额度。

    防止同一天重复续费反复补满：
    - 非活跃用户首次/重新购买：当日给满 daily_quota。
    - 同档续费：不额外补点。
    - 升档：只补新旧日额度差额。
    - 降档：不扣回已剩余额度。
    """
    from pix_web.credits import ensure_credit_account

    tz = resolve_site_timezone(db)
    today = business_day_key(tz, now)
    account = ensure_credit_account(db, user)
    if account.daily_quota_date == today:
        delta = max(0, daily_quota - previous_daily_quota)
        account.daily_quota_balance += delta
    else:
        account.daily_quota_date = today
        account.daily_quota_balance = daily_quota
