from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import pix.api.image_gen as ig
from pix.api.image_gen import (
    ASPECT_RATIO_PROTOCOLS,
    SizeRetryConfig,
    generate_image,
    last_size_retry_outcome,
    parse_size,
)
from pix.config import AppConfig
from pix_web.credits import adjust_credits, reserve_credits, settle_partial_reserved
from pix_web.jobs import _size_retry_plan, create_job_in_transaction
from pix_web.models import Base, CreditAccount, GenerationJob, SystemSetting, User
from pix_web.schemas import JobCreateRequest
from pix_web.system_settings import load_pricing_discount


# ---------- 核心：parse_size ----------

def test_parse_size_concrete() -> None:
    assert parse_size("1024x768") == (1024, 768)


def test_parse_size_auto_and_invalid() -> None:
    assert parse_size("auto") is None
    assert parse_size("") is None
    assert parse_size(None) is None
    assert parse_size("1024") is None


# ---------- 核心：generate_image 尺寸重试循环 ----------

class _FakeImage:
    def __init__(self, protocol: str) -> None:
        self.url = None
        self.b64_json = None
        self.protocol = protocol


class _FakeDispatch:
    def __init__(self, protocol: str) -> None:
        self.image = _FakeImage(protocol)


class SizeRetryLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = AppConfig()
        self.calls = 0
        self.tmpdir = Path(tempfile.mkdtemp())

    def _run(self, sizes: list[tuple[int, int]], *, expected: tuple[int, int], max_attempts: int,
             protocol: str = "openai_images", enabled: bool = True):
        """mock dispatch + 落盘，按 sizes 顺序产出对应尺寸图，返回 outcome。"""
        def fake_write(entry, dest, **kw):
            idx = min(self.calls, len(sizes) - 1)
            w, h = sizes[idx]
            self.calls += 1
            Image.new("RGB", (w, h), (10, 20, 30)).save(dest)
            return Path(dest)

        def fake_dispatch(cfg, **kw):
            return _FakeDispatch(protocol)

        retry = SizeRetryConfig(enabled=enabled, max_attempts=max_attempts, expected_size=expected) if enabled else None
        dest = self.tmpdir / f"out-{self.calls}.png"
        with mock.patch.object(ig, "dispatch_image_request", fake_dispatch), \
             mock.patch.object(ig, "_write_entry", fake_write):
            generate_image(self.cfg, "p", dest, size=f"{expected[0]}x{expected[1]}", size_retry=retry)
        return last_size_retry_outcome()

    def test_matches_first_try_no_retry(self) -> None:
        outcome = self._run([(1024, 1024)], expected=(1024, 1024), max_attempts=5)
        assert outcome is not None
        assert outcome.actual_attempts == 1
        assert outcome.matched is True

    def test_retries_until_match(self) -> None:
        outcome = self._run([(1024, 1536), (1024, 1536), (1024, 1024)], expected=(1024, 1024), max_attempts=5)
        assert outcome is not None
        assert outcome.actual_attempts == 3
        assert outcome.matched is True

    def test_exhausts_attempts_without_match(self) -> None:
        outcome = self._run([(1024, 1536)], expected=(1024, 1024), max_attempts=3)
        assert outcome is not None
        assert outcome.actual_attempts == 3
        assert outcome.matched is False

    def test_aspect_ratio_protocol_stops_after_first(self) -> None:
        outcome = self._run([(1024, 1536)], expected=(1024, 1024), max_attempts=5,
                            protocol=next(iter(ASPECT_RATIO_PROTOCOLS)))
        assert outcome is not None
        assert outcome.actual_attempts == 1
        assert outcome.aspect_ratio_protocol is True

    def test_disabled_runs_once(self) -> None:
        outcome = self._run([(1024, 1536)], expected=(1024, 1024), max_attempts=1, enabled=False)
        assert outcome is not None
        assert outcome.enabled is False
        assert outcome.actual_attempts == 1


# ---------- 计费：settle_partial_reserved ----------

class _DbTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()
        self.user = User(email="u@example.com", password_hash="x", display_name="u", role="user", status="active")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        adjust_credits(self.db, self.user, 1000, "充值")
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _available(self) -> int:
        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == self.user.id))
        return account.available_credits if account is not None else 0

    def _reserved(self) -> int:
        account = self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == self.user.id))
        return account.reserved_credits if account is not None else 0


class SettlePartialReservedTests(_DbTestCase):
    def _make_reserved_job(self, amount: int) -> GenerationJob:
        job = GenerationJob(
            user_id=self.user.id, client_request_id="x", job_type="text_to_image",
            status="running", price_credits=amount,
        )
        self.db.add(job)
        self.db.flush()
        reserve_credits(self.db, self.user, job, amount)
        self.db.commit()
        return job

    def test_partial_consume_refunds_rest(self) -> None:
        job = self._make_reserved_job(60)   # 预扣 60 (per=12 * 5)
        assert self._available() == 940 and self._reserved() == 60
        settle_partial_reserved(self.db, job, consume_amount=24)  # 实际 2 次
        self.db.commit()
        assert job.reserved_credits == 0
        assert self._reserved() == 0
        assert self._available() == 976     # 940 + 退还 36

    def test_full_consume_no_refund(self) -> None:
        job = self._make_reserved_job(60)
        settle_partial_reserved(self.db, job, consume_amount=60)  # 跑满
        self.db.commit()
        assert self._available() == 940     # 无退款
        assert self._reserved() == 0

    def test_consume_clamped_to_reserved(self) -> None:
        job = self._make_reserved_job(60)
        settle_partial_reserved(self.db, job, consume_amount=999)  # 超额夹取
        self.db.commit()
        assert self._available() == 940     # 全消费，无负数
        assert self._reserved() == 0

    def test_zero_reserved_noop(self) -> None:
        job = GenerationJob(
            user_id=self.user.id, client_request_id="y", job_type="text_to_image",
            status="running", price_credits=0, reserved_credits=0,
        )
        self.db.add(job)
        self.db.commit()
        assert settle_partial_reserved(self.db, job, consume_amount=10) is None


# ---------- 计费：_size_retry_plan ----------

class SizeRetryPlanTests(_DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.cfg = AppConfig()

    def _req(self, **kw) -> JobCreateRequest:
        base = dict(
            job_type="text_to_image", prompt="hello", image_size="1024x1024",
            size_retry_enabled=True, size_retry_mode="attempts", size_retry_max_attempts=5,
        )
        base.update(kw)
        return JobCreateRequest(**base)

    def test_plan_attempts_mode_per_attempt_6折(self) -> None:
        discount = load_pricing_discount(self.db)
        plan = _size_retry_plan(self.db, self._req(), self.cfg, discount)
        assert plan.enabled is True
        assert plan.per_attempt == 12       # base 20 * 0.6
        assert plan.max_attempts == 5
        assert plan.reserve_total == 60

    def test_plan_takes_better_global_discount(self) -> None:
        # 全局 5 折比 6 折更优
        self.db.add(SystemSetting(key="pricing.discount_enabled", value="true"))
        self.db.add(SystemSetting(key="pricing.discount_rate", value="0.5"))
        self.db.commit()
        discount = load_pricing_discount(self.db)
        plan = _size_retry_plan(self.db, self._req(), self.cfg, discount)
        assert plan.per_attempt == 10       # min(12, 10)

    def test_plan_credits_mode_converts_to_attempts(self) -> None:
        discount = load_pricing_discount(self.db)
        req = self._req(size_retry_mode="credits", size_retry_max_credits=50)
        plan = _size_retry_plan(self.db, req, self.cfg, discount)
        # budget 50 / per 12 = 4 次
        assert plan.max_attempts == 4
        assert plan.reserve_total == 48

    def test_plan_clamped_to_limit(self) -> None:
        discount = load_pricing_discount(self.db)
        # schema 允许到 20，但 cfg.size_retry_max_attempts_limit=8 会进一步夹取
        req = self._req(size_retry_max_attempts=15)
        plan = _size_retry_plan(self.db, req, self.cfg, discount)
        assert plan.max_attempts == self.cfg.image_gen.size_retry_max_attempts_limit  # 8

    def test_plan_disabled_for_auto_size(self) -> None:
        discount = load_pricing_discount(self.db)
        req = self._req(image_size="auto")
        plan = _size_retry_plan(self.db, req, self.cfg, discount)
        assert plan.enabled is False

    def test_plan_disabled_for_sprite(self) -> None:
        discount = load_pricing_discount(self.db)
        req = JobCreateRequest(
            job_type="sprite_sheet", prompt="run", image_size="1024x1024",
            size_retry_enabled=True,
        )
        plan = _size_retry_plan(self.db, req, self.cfg, discount)
        assert plan.enabled is False

    def test_plan_disabled_when_global_off(self) -> None:
        discount = load_pricing_discount(self.db)
        self.cfg.image_gen.size_retry_enabled = False
        plan = _size_retry_plan(self.db, self._req(), self.cfg, discount)
        assert plan.enabled is False


class SizeRetryJobCreationTests(_DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.cfg = AppConfig()

    def test_create_job_reserves_worst_case(self) -> None:
        req = JobCreateRequest(
            job_type="text_to_image", prompt="hi", image_size="1024x1024",
            size_retry_enabled=True, size_retry_max_attempts=5,
        )
        job = create_job_in_transaction(self.db, self.user, req, cfg=self.cfg)
        self.db.commit()
        assert job.price_credits == 60          # per 12 * 5
        assert job.reserved_credits == 60
        assert self._available() == 940
        assert job.params_json["size_retry"]["per_attempt"] == 12
        assert job.params_json["size_retry"]["max_attempts"] == 5


if __name__ == "__main__":
    unittest.main()
