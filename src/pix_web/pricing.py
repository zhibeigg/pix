"""价格规则。"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule


DEFAULT_PRICES: dict[str, int] = {
    "asset": 20,
    "text_to_image": 20,
    "image_to_image": 20,
    # sprite_sheet 表示“序列帧单帧基础价”，总价 = frame_count × 该基础价。
    "sprite_sheet": 5,
    "local_pixelize": 0,
    "local_bg_remove": 0,
    "repixelize": 0,
}


class PricingDisabledError(RuntimeError):
    pass


def ensure_default_pricing(db: Session) -> None:
    changed = False
    for key, price in DEFAULT_PRICES.items():
        exists = db.scalar(select(PricingRule).where(PricingRule.key == key))
        if exists is None:
            db.add(PricingRule(key=key, price_credits=price, enabled=True))
            changed = True
    if changed:
        db.commit()


def get_price(db: Session, key: str) -> int:
    rule = db.scalar(select(PricingRule).where(PricingRule.key == key))
    if rule is None:
        price = DEFAULT_PRICES.get(key)
        if price is None:
            raise KeyError(f"未知价格规则: {key}")
        rule = PricingRule(key=key, price_credits=price, enabled=True)
        db.add(rule)
        db.commit()
        db.refresh(rule)
    if not rule.enabled:
        raise PricingDisabledError(f"价格规则已禁用: {key}")
    return max(0, int(rule.price_credits))


def apply_discount(amount: int, rate: float) -> int:
    """按折扣倍率打折后的实扣点数。

    规则：原价>0 时向下取整且保底 1 点（不因折扣变免费）；
    rate>=1 或 amount<=0 原样返回；rate<=0 返回 0（限免）。
    """
    if amount <= 0 or rate >= 1.0:
        return amount
    if rate <= 0.0:
        return 0
    return max(1, math.floor(amount * rate))
