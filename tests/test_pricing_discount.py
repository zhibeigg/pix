from __future__ import annotations

from pix_web.pricing import apply_discount


def test_apply_discount_passthrough_when_no_discount() -> None:
    assert apply_discount(20, 1.0) == 20
    assert apply_discount(20, 1.5) == 20  # 异常 >1 也不放大


def test_apply_discount_floor() -> None:
    assert apply_discount(20, 0.8) == 16
    assert apply_discount(5, 0.85) == 4   # floor(4.25)


def test_apply_discount_minimum_one_for_paid_jobs() -> None:
    assert apply_discount(1, 0.5) == 1    # floor(0.5)=0 → 保底 1


def test_apply_discount_zero_rate_is_free() -> None:
    assert apply_discount(20, 0.0) == 0


def test_apply_discount_zero_amount_stays_free() -> None:
    assert apply_discount(0, 0.8) == 0    # 免费任务（local_pixelize）不变


def test_apply_discount_sprite_total() -> None:
    # 序列帧 8x8: base 5 * units 8 = 40 → 0.8 → 32
    assert apply_discount(40, 0.8) == 32
