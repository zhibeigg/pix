from __future__ import annotations

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix_web.credits import adjust_credits, refund_reserved
from pix_web.jobs import create_job_in_transaction
from pix_web.models import Base, CreditAccount, SystemSetting, User
from pix_web.pricing import apply_discount
from pix_web.schemas import AssetParamsSchema, JobCreateRequest, SpriteParamsSchema
from pix_web.system_settings import (
    SETTING_DEFINITIONS,
    load_pricing_discount,
    update_system_setting,
)


class _DbTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()


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


class PricingDiscountSettingsTests(_DbTestCase):
    def test_setting_definitions_present(self) -> None:
        keys = {item.key for item in SETTING_DEFINITIONS}
        assert "pricing.discount_enabled" in keys
        assert "pricing.discount_rate" in keys
        assert "pricing.discount_label" in keys

    def test_default_discount_inactive(self) -> None:
        discount = load_pricing_discount(self.db)
        assert discount.enabled is False
        assert discount.rate == 1.0
        assert discount.active is False

    def test_active_discount_parsed(self) -> None:
        self.db.add(SystemSetting(key="pricing.discount_enabled", value="true"))
        self.db.add(SystemSetting(key="pricing.discount_rate", value="0.8"))
        self.db.add(SystemSetting(key="pricing.discount_label", value="限时 8 折"))
        self.db.commit()
        discount = load_pricing_discount(self.db)
        assert discount.enabled is True
        assert discount.rate == 0.8
        assert discount.label == "限时 8 折"
        assert discount.active is True

    def test_rate_one_is_inactive(self) -> None:
        self.db.add(SystemSetting(key="pricing.discount_enabled", value="true"))
        self.db.add(SystemSetting(key="pricing.discount_rate", value="1"))
        self.db.commit()
        assert load_pricing_discount(self.db).active is False

    def test_rate_clamped_on_load(self) -> None:
        # 历史脏数据兜底：读取时裁剪到 [0,1]
        self.db.add(SystemSetting(key="pricing.discount_enabled", value="true"))
        self.db.add(SystemSetting(key="pricing.discount_rate", value="2.5"))
        self.db.commit()
        assert load_pricing_discount(self.db).rate == 1.0

    def test_normalize_rejects_out_of_range_rate(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            update_system_setting(self.db, "pricing.discount_rate", "2")
        assert ctx.exception.status_code == 422


class DiscountBillingTests(_DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User(email="u@example.com", password_hash="x", display_name="u", role="user", status="active")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        adjust_credits(self.db, self.user, 1000, "充值")
        self.db.commit()

    def _enable_discount(self, rate: str) -> None:
        self.db.add(SystemSetting(key="pricing.discount_enabled", value="true"))
        self.db.add(SystemSetting(key="pricing.discount_rate", value=rate))
        self.db.commit()

    def _available(self) -> int:
        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == self.user.id))
        return account.available_credits if account is not None else 0

    def _asset_req(self) -> JobCreateRequest:
        return JobCreateRequest(job_type="asset", asset=AssetParamsSchema(name="frost"))

    def test_asset_job_reserves_discounted_price(self) -> None:
        self._enable_discount("0.5")
        job = create_job_in_transaction(self.db, self.user, self._asset_req())
        self.db.commit()
        assert job.price_credits == 10        # 20 * 0.5
        assert job.reserved_credits == 10
        assert self._available() == 990        # 1000 - 10

    def test_discount_disabled_charges_original(self) -> None:
        job = create_job_in_transaction(self.db, self.user, self._asset_req())
        self.db.commit()
        assert job.price_credits == 20

    def test_refund_returns_discounted_amount(self) -> None:
        self._enable_discount("0.5")
        job = create_job_in_transaction(self.db, self.user, self._asset_req())
        self.db.commit()
        refund_reserved(self.db, job)
        self.db.commit()
        assert self._available() == 1000       # 全额退回折后冻结的 10 点
        assert job.reserved_credits == 0

    def test_sprite_discount_and_billing_snapshot(self) -> None:
        self._enable_discount("0.5")
        # rows>=2 时 validate_job_request 要求每行动作描述，必须给满 rows 条 row_prompts
        req = JobCreateRequest(
            job_type="sprite_sheet",
            prompt="run",
            sprite=SpriteParamsSchema(rows=8, cols=8, row_prompts=["run"] * 8),
        )
        job = create_job_in_transaction(self.db, self.user, req)
        self.db.commit()
        assert job.price_credits == 20          # base 5 * units 8 = 40 → 0.5 → 20
        billing = job.params_json["billing"]
        assert billing["original_total_points"] == 40
        assert billing["total_points"] == 20
        assert billing["discount"]["rate"] == 0.5
