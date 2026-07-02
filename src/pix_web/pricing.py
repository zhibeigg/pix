"""价格规则。"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_CEILING

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule


VIDEO_BRIDGE_PRICE_SOURCE_URL = "https://bytedance.larkoffice.com/share/base/form/shrcnP1Bl0mqCP9OHCbjpe1oBkf"
VIDEO_BRIDGE_IMAGE_PRICE_CREDITS = 10
VIDEO_BRIDGE_PRICE_MULTIPLIER = 20
VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS = 4
VIDEO_BRIDGE_DEFAULT_MODEL = "doubao-seedance-2-0-260128"
VIDEO_BRIDGE_ALLOWED_DURATION_SECONDS = tuple(range(4, 16))
VIDEO_BRIDGE_MODEL_PRICE_CNY_BY_DURATION: dict[str, dict[int, Decimal]] = {
    # 飞书价格计算器：Seedance 2.0，480p，16:9，输入不含视频，4–15 秒视频价格。
    # 计费口径：ceil(视频价格 × 20 + 10 点关键帧生图价)。
    "doubao-seedance-2-0-260128": {
        4: Decimal("1.85"),
        5: Decimal("2.31"),
        6: Decimal("2.77"),
        7: Decimal("3.23"),
        8: Decimal("3.70"),
        9: Decimal("4.16"),
        10: Decimal("4.62"),
        11: Decimal("5.08"),
        12: Decimal("5.54"),
        13: Decimal("6.01"),
        14: Decimal("6.47"),
        15: Decimal("6.93"),
    },
    "doubao-seedance-2-0-fast-260128": {
        4: Decimal("1.49"),
        5: Decimal("1.86"),
        6: Decimal("2.23"),
        7: Decimal("2.60"),
        8: Decimal("2.97"),
        9: Decimal("3.34"),
        10: Decimal("3.72"),
        11: Decimal("4.09"),
        12: Decimal("4.46"),
        13: Decimal("4.83"),
        14: Decimal("5.20"),
        15: Decimal("5.57"),
    },
    "doubao-seedance-2-0-mini-260615": {
        4: Decimal("0.92"),
        5: Decimal("1.16"),
        6: Decimal("1.39"),
        7: Decimal("1.62"),
        8: Decimal("1.85"),
        9: Decimal("2.08"),
        10: Decimal("2.31"),
        11: Decimal("2.54"),
        12: Decimal("2.77"),
        13: Decimal("3.00"),
        14: Decimal("3.23"),
        15: Decimal("3.47"),
    },
}
VIDEO_BRIDGE_MODEL_PRICE_CNY: dict[str, Decimal] = {
    model: prices[VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS]
    for model, prices in VIDEO_BRIDGE_MODEL_PRICE_CNY_BY_DURATION.items()
}
VIDEO_BRIDGE_MODEL_PRICE_CREDITS: dict[str, int] = {}


def normalize_video_bridge_model(model: str | None) -> str:
    value = (model or "").strip()
    return value if value in VIDEO_BRIDGE_MODEL_PRICE_CNY_BY_DURATION else VIDEO_BRIDGE_DEFAULT_MODEL


def normalize_video_bridge_duration_seconds(duration_seconds: int | None) -> int:
    seconds = max(VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS, int(duration_seconds or 0))
    for tier in VIDEO_BRIDGE_ALLOWED_DURATION_SECONDS:
        if seconds <= tier:
            return tier
    return VIDEO_BRIDGE_ALLOWED_DURATION_SECONDS[-1]


def video_bridge_price_cny(model: str | None, duration_seconds: int | None = None) -> Decimal:
    normalized = normalize_video_bridge_model(model)
    seconds = normalize_video_bridge_duration_seconds(duration_seconds)
    return VIDEO_BRIDGE_MODEL_PRICE_CNY_BY_DURATION[normalized][seconds]


def _credits_from_video_price_cny(price_cny: Decimal) -> int:
    total = price_cny * Decimal(VIDEO_BRIDGE_PRICE_MULTIPLIER) + Decimal(VIDEO_BRIDGE_IMAGE_PRICE_CREDITS)
    return int(total.to_integral_value(rounding=ROUND_CEILING))


VIDEO_BRIDGE_MODEL_PRICE_CREDITS.update(
    {
        model: _credits_from_video_price_cny(price)
        for model, price in VIDEO_BRIDGE_MODEL_PRICE_CNY.items()
    }
)


def video_bridge_price_key(model: str | None) -> str:
    return f"sprite_video_bridge:{normalize_video_bridge_model(model)}"


def video_bridge_price_credits(
    model: str | None,
    *,
    duration_seconds: int = VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS,
    base_duration_price_credits: int | None = None,
) -> int:
    """首尾帧视频补间价格点数。

    价格来源为飞书价格计算器中 480p、16:9、输入不含视频的「视频价格」，
    计费公式：ceil(视频价格 × 20 + 10)，其中 10 点为关键帧生图价格。
    支持的官方时长档位为 4–15 秒；传入其它秒数时会向上吸附到
    不小于它的最近价格表档位。
    """
    normalized = normalize_video_bridge_model(model)
    seconds = normalize_video_bridge_duration_seconds(duration_seconds)
    default_price = VIDEO_BRIDGE_MODEL_PRICE_CREDITS[normalized]
    if base_duration_price_credits is not None and int(base_duration_price_credits) != default_price:
        base_price = max(0, int(base_duration_price_credits))
        if seconds <= VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS or base_price <= VIDEO_BRIDGE_IMAGE_PRICE_CREDITS:
            return base_price
        video_component = base_price - VIDEO_BRIDGE_IMAGE_PRICE_CREDITS
        base_video_price = video_bridge_price_cny(normalized, VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS)
        duration_video_price = video_bridge_price_cny(normalized, seconds)
        scaled_video = math.ceil(video_component * float(duration_video_price / base_video_price))
        return VIDEO_BRIDGE_IMAGE_PRICE_CREDITS + scaled_video
    return _credits_from_video_price_cny(video_bridge_price_cny(normalized, seconds))


DEFAULT_PRICES: dict[str, int] = {
    "asset": 20,
    "text_to_image": 20,
    "image_to_image": 20,
    # sprite_sheet 表示“mosaic 序列帧单帧组基础价”，总价 = ceil(frame_count / 9) × 该基础价。
    "sprite_sheet": 5,
    # video_bridge 表示“关键帧生图 + 4 秒 480p Seedance 视频补间”的单任务价。
    **{
        video_bridge_price_key(model): price
        for model, price in VIDEO_BRIDGE_MODEL_PRICE_CREDITS.items()
    },
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
