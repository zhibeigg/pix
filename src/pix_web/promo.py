"""优惠链接服务：优惠码创建、绑定、折扣计算与使用量统计。

与邀请返佣（referrals.py）独立并存：
- 邀请链接（?aff=）：好友充值后邀请人拿返佣。
- 优惠链接（?promo=）：管理员创建优惠码并设折扣倍率，通过该链接注册的用户
  永久绑定优惠码，之后所有充值/月卡订单按折扣倍率支付。

折扣仅作用于「支付金额」（amount_cents），到账点数 / 月卡额度不变。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from pix_web.models import PaymentOrder, PromoLink, User, utcnow


def clean_code(value: str | None) -> str:
    return (value or "").strip().upper()


def _clamp_rate(rate: float) -> float:
    if rate < 0.0:
        return 0.0
    if rate > 1.0:
        return 1.0
    return float(rate)


def apply_promo_discount(amount_cents: int, rate: float) -> int:
    """按折扣倍率对支付金额打折。

    规则：原价>0 时向下取整且保底 1 分（不因折扣变全免）；
    rate>=1 或 amount<=0 原样返回；rate<=0 返回 0（限免）。
    """
    if amount_cents <= 0 or rate >= 1.0:
        return amount_cents
    if rate <= 0.0:
        return 0
    return max(1, math.floor(amount_cents * rate))


def get_promo_link(db: Session, code: str | None) -> PromoLink | None:
    normalized = clean_code(code)
    if not normalized:
        return None
    return db.scalar(select(PromoLink).where(PromoLink.code == normalized))


def get_active_promo_link(db: Session, code: str | None) -> PromoLink | None:
    """返回启用中的优惠链接；未启用或不存在返回 None。"""
    link = get_promo_link(db, code)
    if link is None or not link.enabled:
        return None
    return link


def resolve_user_discount_rate(db: Session, user: User) -> float:
    """用户绑定的有效折扣倍率；无绑定或链接停用时返回 1.0（不打折）。"""
    link = get_active_promo_link(db, user.promo_code)
    if link is None:
        return 1.0
    return _clamp_rate(link.discount_rate)


def bind_user_promo(db: Session, user: User, code: str | None) -> PromoLink | None:
    """注册时绑定优惠码（永久）。仅在用户尚未绑定且链接启用时绑定。"""
    if (user.promo_code or "").strip():
        return None
    link = get_active_promo_link(db, code)
    if link is None:
        return None
    user.promo_code = link.code
    link.signup_count += 1
    db.flush()
    return link


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ── 管理端 CRUD ──────────────────────────────────────────────

def list_promo_links(db: Session) -> list[PromoLink]:
    return list(
        db.scalars(select(PromoLink).order_by(PromoLink.created_at.desc(), PromoLink.id.desc()))
    )


def create_promo_link(
    db: Session,
    *,
    code: str,
    name: str,
    discount_rate: float,
    enabled: bool,
    note: str,
) -> PromoLink:
    normalized = clean_code(code)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="优惠码不能为空")
    existing = db.scalar(select(PromoLink).where(PromoLink.code == normalized))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="优惠码已存在")
    link = PromoLink(
        code=normalized,
        name=name.strip(),
        discount_rate=_clamp_rate(discount_rate),
        enabled=enabled,
        note=note.strip(),
    )
    db.add(link)
    db.flush()
    return link


def update_promo_link(
    db: Session,
    link_id: int,
    *,
    name: str,
    discount_rate: float,
    enabled: bool,
    note: str,
) -> PromoLink:
    link = db.get(PromoLink, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优惠链接不存在")
    link.name = name.strip()
    link.discount_rate = _clamp_rate(discount_rate)
    link.enabled = enabled
    link.note = note.strip()
    db.flush()
    return link


def delete_promo_link(db: Session, link_id: int) -> None:
    link = db.get(PromoLink, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优惠链接不存在")
    db.delete(link)
    db.flush()


# ── 统计 ─────────────────────────────────────────────────────

def promo_link_stats(db: Session) -> list[dict[str, object]]:
    """每个优惠链接的使用量统计：注册数、下单/付费数、付费金额与点数。

    付费金额按订单实付 amount_cents 聚合（已折后金额）。
    """
    # 按 promo_code 聚合订单：区分全部订单与已付订单。
    order_rows = db.execute(
        select(
            PaymentOrder.promo_code,
            func.count(PaymentOrder.id),
            func.sum(case((PaymentOrder.status == "paid", 1), else_=0)),
            func.sum(
                case((PaymentOrder.status == "paid", PaymentOrder.amount_cents), else_=0)
            ),
            func.sum(case((PaymentOrder.status == "paid", PaymentOrder.credits), else_=0)),
        )
        .where(PaymentOrder.promo_code != "")
        .group_by(PaymentOrder.promo_code)
    ).all()
    orders_by_code: dict[str, dict[str, int]] = {}
    for code, total, paid, paid_amount, paid_credits in order_rows:
        orders_by_code[code] = {
            "order_count": int(total or 0),
            "paid_order_count": int(paid or 0),
            "paid_amount_cents": int(paid_amount or 0),
            "paid_credits": int(paid_credits or 0),
        }

    # 已绑定用户数（可能大于 signup_count 的历史值，以实际用户表为准）。
    user_rows = db.execute(
        select(User.promo_code, func.count(User.id))
        .where(User.promo_code != "")
        .group_by(User.promo_code)
    ).all()
    users_by_code = {code: int(count or 0) for code, count in user_rows}

    result: list[dict[str, object]] = []
    for link in list_promo_links(db):
        orders = orders_by_code.get(link.code, {})
        result.append(
            {
                "id": link.id,
                "code": link.code,
                "name": link.name,
                "discount_rate": link.discount_rate,
                "enabled": link.enabled,
                "note": link.note,
                "signup_count": link.signup_count,
                "bound_user_count": users_by_code.get(link.code, 0),
                "order_count": orders.get("order_count", 0),
                "paid_order_count": orders.get("paid_order_count", 0),
                "paid_amount_cents": orders.get("paid_amount_cents", 0),
                "paid_credits": orders.get("paid_credits", 0),
                "created_at": link.created_at,
                "updated_at": link.updated_at,
            }
        )
    return result
