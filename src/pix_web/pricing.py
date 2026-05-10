"""价格规则。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule


DEFAULT_PRICES: dict[str, int] = {
    "text_to_image": 20,
    "image_to_image": 20,
    "local_pixelize": 0,
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
