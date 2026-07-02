"""价格规则。"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule


VIDEO_BRIDGE_PRICE_SOURCE_URL = (
    "https://bytedance.larkoffice.com/wiki/FXaYwxzJ5i5Zdik32ipcWzt7nxd"
    "?table=tblns3WjGMNbR8sL&view=vew7f33fzS#CategoryScheduledTask"
)
VIDEO_BRIDGE_IMAGE_PRICE_CREDITS = 10
VIDEO_BRIDGE_PRICE_MULTIPLIER = 20
VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS = 4
VIDEO_BRIDGE_DEFAULT_MODEL = "doubao-seedance-2-0-260128"
VIDEO_BRIDGE_MODEL_PRICE_CNY: dict[str, float] = {
    # 火山/飞书价格表：Seedance 2.0，480p，输入不含视频，4 秒视频价格。
    # 计费口径：视频价格 × 20 + 10 点关键帧生图价。
    "doubao-seedance-2-0-lite-260128": 0.984312,
    "doubao-seedance-2-0-260128": 1.848096,
    "doubao-seedance-2-0-pro-260128": 3.696192,
}
VIDEO_BRIDGE_MODEL_PRICE_CNY_PER_SECOND: dict[str, float] = {
    model: price / VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS
    for model, price in VIDEO_BRIDGE_MODEL_PRICE_CNY.items()
}
VIDEO_BRIDGE_MODEL_PRICE_CREDITS: dict[str, int] = {
    model: math.ceil(price * VIDEO_BRIDGE_PRICE_MULTIPLIER + VIDEO_BRIDGE_IMAGE_PRICE_CREDITS)
    for model, price in VIDEO_BRIDGE_MODEL_PRICE_CNY.items()
}


def normalize_video_bridge_model(model: str | None) -> str:
    value = (model or "").strip()
    return value if value in VIDEO_BRIDGE_MODEL_PRICE_CNY else VIDEO_BRIDGE_DEFAULT_MODEL


def video_bridge_price_key(model: str | None) -> str:
    return f"sprite_video_bridge:{normalize_video_bridge_model(model)}"


def video_bridge_price_credits(
    model: str | None,
    *,
    duration_seconds: int = VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS,
    base_duration_price_credits: int | None = None,
) -> int:
    """首尾帧视频补间价格点数。

    价格来源为火山/飞书价格表中 480p、输入不含视频的「视频价格」，
    计费公式：ceil(视频价格 × 20 + 10)，其中 10 点为关键帧生图价格。
    默认 UI 预设会提交 4 秒视频；若自定义帧数/FPS 推导出更长 Ark 秒数，按同表
    每秒价格线性折算视频价格。
    """
    normalized = normalize_video_bridge_model(model)
    seconds = max(VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS, int(duration_seconds or 0))
    default_price = VIDEO_BRIDGE_MODEL_PRICE_CREDITS[normalized]
    if base_duration_price_credits is not None and int(base_duration_price_credits) != default_price:
        base_price = max(0, int(base_duration_price_credits))
        if seconds <= VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS or base_price <= VIDEO_BRIDGE_IMAGE_PRICE_CREDITS:
            return base_price
        video_component = base_price - VIDEO_BRIDGE_IMAGE_PRICE_CREDITS
        scaled_video = math.ceil(video_component * seconds / VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS)
        return VIDEO_BRIDGE_IMAGE_PRICE_CREDITS + scaled_video
    video_price_cny = VIDEO_BRIDGE_MODEL_PRICE_CNY_PER_SECOND[normalized] * seconds
    return math.ceil(video_price_cny * VIDEO_BRIDGE_PRICE_MULTIPLIER + VIDEO_BRIDGE_IMAGE_PRICE_CREDITS)


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
