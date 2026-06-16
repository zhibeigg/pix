# 全局点数折扣 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给生成任务增加一个管理员可控的全局点数折扣，消耗点数按折扣倍率向下取整（保底 1 点）扣除。

**Architecture:** 折扣配置复用现有 `SystemSetting` 基础设施（三个设置项）；折扣计算是 `pricing.py` 的一个纯函数；接入点是 `jobs.py` 价格函数的单一收口（`_price_for_request`），所有创建/批量/重试路径自动按折后价冻结，冻结/确认/退款链路零改动；新增一个公开只读接口 `GET /pricing/discount` 供前端展示原价划线 + 折后价 + 折扣标签。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.x（同步 Session）/ pytest；React + Vite + TypeScript 前端。

> 设计依据：[`docs/superpowers/specs/2026-06-16-pricing-discount-design.md`](../specs/2026-06-16-pricing-discount-design.md)

---

## 文件结构（创建 / 修改）

**后端**
- 修改 `src/pix_web/pricing.py` — 新增纯函数 `apply_discount`（核心取整规则）
- 修改 `src/pix_web/system_settings.py` — 新增三个折扣设置项、`_parse_float`、`PricingDiscount` 数据类、`load_pricing_discount`、`_normalize_value` 倍率范围校验
- 修改 `src/pix_web/jobs.py` — 价格函数收口接入折扣 + 计费快照扩展
- 修改 `src/pix_web/schemas.py` — 新增 `PricingDiscountResponse`
- 修改 `src/pix_web/routers/pricing.py` — 新增 `GET /pricing/discount`
- 创建 `tests/test_pricing_discount.py` — 折扣单测 + 集成测试

**前端**
- 修改 `apps/web/src/types.ts` — 新增 `PricingDiscount` 类型
- 修改 `apps/web/src/api.ts` — 新增 `pricingDiscount()`
- 创建 `apps/web/src/lib/pricing.ts` — 共享 `applyDiscount` / 标签辅助
- 创建 `apps/web/src/components/EstimateBadge.tsx` — 共享估价 Badge（含折扣展示）
- 修改 `apps/web/src/App.tsx` — `discount` state + 加载 + 透传 + 登出清理
- 修改 `apps/web/src/pages/WorkspacePage.tsx` — 透传 `discount`
- 修改 `apps/web/src/components/SingleGeneratePanel.tsx` — 用 `EstimateBadge`
- 修改 `apps/web/src/components/BatchGeneratePanel.tsx` — 折后单价 / 总价 + 折扣标签
- 修改 `apps/web/src/pages/RawImagePage.tsx` — 用 `EstimateBadge` + 折后余额判断

**文档与版本**
- 修改 `README.md`、`CHANGELOG.md`、`pyproject.toml`、`src/pix/__init__.py`、`apps/web/package.json`

---

## Task 1: `apply_discount` 纯函数

**Files:**
- Modify: `src/pix_web/pricing.py`
- Test: `tests/test_pricing_discount.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_pricing_discount.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_pricing_discount.py -v`
Expected: FAIL（`ImportError: cannot import name 'apply_discount'`）

- [ ] **Step 3: 实现 `apply_discount`**

在 `src/pix_web/pricing.py` 顶部 `from __future__ import annotations` 之后加入 `import math`，并在文件末尾追加：

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_pricing_discount.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add src/pix_web/pricing.py tests/test_pricing_discount.py
git commit -m "feat(pricing): add apply_discount rounding helper"
```

---

## Task 2: 折扣设置项与加载器

**Files:**
- Modify: `src/pix_web/system_settings.py`
- Test: `tests/test_pricing_discount.py`

参考实现位置：`SETTING_DEFINITIONS`（约 84-214 行）、`DEFAULT_SYSTEM_SETTINGS`（约 217-234 行）、`_parse_bool` / `_parse_positive_int`（约 259-267 行）、`_normalize_value`（约 386-402 行）、`load_referral_settings`（约 477-492 行，照此写 `load_pricing_discount`）、`_stored_values`（约 420-422 行）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_pricing_discount.py` 顶部追加 import 与 db fixture 基类（沿用 `tests/test_gallery_quota.py` 的内存库模式），并加入设置相关测试：

```python
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pix_web.models import Base, SystemSetting
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_pricing_discount.py -k "Settings" -v`
Expected: FAIL（`ImportError: cannot import name 'load_pricing_discount'`）

- [ ] **Step 3: 实现设置项、数据类、加载器、校验**

(a) 在 `SETTING_DEFINITIONS` 元组末尾（`env.wechat_private_key` 之前任意位置即可，建议紧跟运营保护类之后）新增三项：

```python
    SettingDefinition("pricing.discount_enabled", "折扣总开关", "价格折扣", "boolean", "false", "开启后所有生成任务按折扣倍率扣点；作品库 / 素材包扩容不受影响。"),
    SettingDefinition("pricing.discount_rate", "折扣倍率", "价格折扣", "number", "1.0", "0~1，例如 0.8 = 8 折；0 = 限免；1 = 不打折。向下取整，原价>0 的任务折后保底 1 点。"),
    SettingDefinition("pricing.discount_label", "折扣标签", "价格折扣", "string", "", "可选促销文案，例如「限时 8 折」；留空时前端按倍率自动生成。"),
```

(b) 在 `DEFAULT_SYSTEM_SETTINGS` 的 key 集合里加入这三个 key（让它们被种子化）：

```python
        "pricing.discount_enabled",
        "pricing.discount_rate",
        "pricing.discount_label",
```

(c) 在 `_parse_positive_int` 之后新增 `_parse_float`：

```python
def _parse_float(value: str, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
```

(d) 在 `ReferralSettings` 数据类附近（约 69-74 行后）新增数据类：

```python
@dataclass(frozen=True)
class PricingDiscount:
    enabled: bool
    rate: float
    label: str

    @property
    def active(self) -> bool:
        return self.enabled and 0.0 <= self.rate < 1.0
```

(e) 在 `load_referral_settings` 之后新增加载器：

```python
def load_pricing_discount(db: Session) -> PricingDiscount:
    values = _stored_values(db)
    enabled = _parse_bool(values.get("pricing.discount_enabled", "false"))
    rate = min(1.0, max(0.0, _parse_float(values.get("pricing.discount_rate", "1"), 1.0)))
    label = values.get("pricing.discount_label", "").strip()
    return PricingDiscount(enabled=enabled, rate=rate, label=label)
```

(f) 在 `_normalize_value` 的 `number` 分支里，对倍率加范围校验。把现有：

```python
    if definition.type == "number":
        try:
            number = float(clean) if "." in clean else int(clean)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="数字格式不正确") from exc
        if isinstance(number, float):
            return str(number)
        return str(max(0, number))
```

改为：

```python
    if definition.type == "number":
        try:
            number = float(clean) if "." in clean else int(clean)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="数字格式不正确") from exc
        if definition.key == "pricing.discount_rate":
            rate = float(number)
            if rate < 0.0 or rate > 1.0:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="折扣倍率应在 0~1 之间")
            return str(rate)
        if isinstance(number, float):
            return str(number)
        return str(max(0, number))
```

> 写时校验（422）与读时裁剪（`load_pricing_discount` 的 `min/max`）是互补的两道防线，二者都要保留：前者给管理员即时反馈，后者兜底历史脏数据 / 早于校验写入的旧行。

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_pricing_discount.py -k "Settings" -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add src/pix_web/system_settings.py tests/test_pricing_discount.py
git commit -m "feat(pricing): add global discount settings and loader"
```

---

## Task 3: 计费链路接入折扣

**Files:**
- Modify: `src/pix_web/jobs.py`
- Test: `tests/test_pricing_discount.py`

参考实现位置：imports（15-20 行）、`_price_for_request`（200-204 行）、`_billing_snapshot_for_request`（207-226 行）、`create_job_in_transaction`（229-260 行，注意 243-244 与 258-259 行）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_pricing_discount.py` 追加集成测试（沿用内存库 + 直接调用函数，不走 HTTP）：

```python
from sqlalchemy import select

from pix_web.credits import adjust_credits, refund_reserved
from pix_web.jobs import create_job_in_transaction
from pix_web.models import CreditAccount, User
from pix_web.schemas import AssetParamsSchema, JobCreateRequest, SpriteParamsSchema


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
```

> 关键约束：rows>=2 的序列帧在 `validate_job_request`（jobs.py:123）会要求 `len(row_prompts) >= rows`，所以上面给了 `["run"] * 8`（恰好 8 条，`max_length=8`）。若想避开多行约束改用单行：`SpriteParamsSchema(rows=1, cols=8)`（无需 row_prompts，units=1，原价 base 5 → `apply_discount(5, 0.5)` = floor(2.5) = 2，断言改为 price_credits=2 / original_total_points=5 / total_points=2）。核心是验证折后价 == `apply_discount(原价, rate)`。

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_pricing_discount.py -k "Billing" -v`
Expected: FAIL（折扣未接入，`price_credits` 仍是原价 20）

- [ ] **Step 3: 实现接入**

(a) 改 import（18 行与 20 行）：

```python
from pix_web.pricing import PricingDisabledError, apply_discount, get_price
```
```python
from pix_web.system_settings import enforce_generation_limits, enforce_prompt_policy, load_pricing_discount
```

(b) 把现有 `_price_for_request`（200-204 行）**重命名**为 `_original_price_for_request`（函数体不变）：

```python
def _original_price_for_request(db: Session, req: JobCreateRequest) -> int:
    base_price = _base_price_for_request(db, req)
    if req.job_type == "sprite_sheet":
        return base_price * _sprite_billing_units(req)
    return base_price


def _price_for_request(db: Session, req: JobCreateRequest) -> int:
    """对外的实扣价：原价经全局折扣后的折后价。"""
    original = _original_price_for_request(db, req)
    return apply_discount(original, load_pricing_discount(db).rate)
```

(c) 重写 `_billing_snapshot_for_request`（207-226 行），改为接收原价 / 折后价 / 折扣对象：

```python
def _billing_snapshot_for_request(
    db: Session,
    req: JobCreateRequest,
    *,
    original_total: int,
    discounted_total: int,
    discount,
) -> dict | None:
    is_sprite = req.job_type == "sprite_sheet"
    if not is_sprite and not discount.active:
        return None
    snapshot: dict = {}
    if is_sprite:
        base_price = _base_price_for_request(db, req)
        snapshot.update(
            {
                "rows": req.sprite.rows,
                "cols": req.sprite.cols,
                "frame_base_price": base_price,
                "frame_count": _frame_count_for_price(req),
                "billing_units": _sprite_billing_units(req),
                "max_frame_count": 64,
                "formula": "ceil(rows*cols/9) * frame_base_price",
                "billing_note": "one API call per job; postprocess included",
            }
        )
    snapshot["original_total_points"] = original_total
    snapshot["total_points"] = discounted_total
    if discount.active:
        snapshot["discount"] = {"rate": discount.rate, "label": discount.label}
    return snapshot
```

(d) 改 `create_job_in_transaction` 里算价 + 快照那两行（243-244 行）：

```python
    original_price = _original_price_for_request(db, req)
    discount = load_pricing_discount(db)
    price = apply_discount(original_price, discount.rate)
    billing = _billing_snapshot_for_request(
        db, req, original_total=original_price, discounted_total=price, discount=discount
    )
```

其余（`price_credits=price`、`reserve_credits(db, user, job, price)`）保持不变。批量 / 重试路径调用的是 `_price_for_request`，已自动返回折后价，无需改动。

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_pricing_discount.py -v`
Expected: PASS（全部）

- [ ] **Step 5: 回归现有测试**

Run: `python -m pytest tests/ -v`
Expected: PASS（无回归；尤其 `test_gallery_quota.py` 不受影响）

- [ ] **Step 6: 提交**

```bash
git add src/pix_web/jobs.py tests/test_pricing_discount.py
git commit -m "feat(pricing): apply global discount when reserving job credits"
```

---

## Task 4: 公开折扣接口

**Files:**
- Modify: `src/pix_web/schemas.py`
- Modify: `src/pix_web/routers/pricing.py`
- Test: `tests/test_pricing_discount.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_pricing_discount.py` 追加：

```python
from pix_web.routers.pricing import pricing_discount


class PricingDiscountEndpointTests(_DbTestCase):
    def test_inactive_by_default(self) -> None:
        resp = pricing_discount(db=self.db)
        assert resp.active is False
        assert resp.rate == 1.0

    def test_active_payload(self) -> None:
        self.db.add(SystemSetting(key="pricing.discount_enabled", value="true"))
        self.db.add(SystemSetting(key="pricing.discount_rate", value="0.8"))
        self.db.add(SystemSetting(key="pricing.discount_label", value="限时 8 折"))
        self.db.commit()
        resp = pricing_discount(db=self.db)
        assert resp.active is True
        assert resp.rate == 0.8
        assert resp.label == "限时 8 折"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_pricing_discount.py -k "Endpoint" -v`
Expected: FAIL（`cannot import name 'pricing_discount'`）

- [ ] **Step 3: 实现 schema + 路由**

(a) `src/pix_web/schemas.py`，在 `PricingRuleUpdateRequest`（886-888 行）之后新增：

```python
class PricingDiscountResponse(BaseModel):
    active: bool
    rate: float
    label: str = ""
```

(b) `src/pix_web/routers/pricing.py` 整体改为：

```python
"""公开价格规则接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule
from pix_web.schemas import PricingDiscountResponse, PricingRuleResponse
from pix_web.security import get_db
from pix_web.system_settings import load_pricing_discount

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("", response_model=list[PricingRuleResponse])
def pricing(db: Session = Depends(get_db)) -> list[PricingRule]:
    return list(db.scalars(select(PricingRule).order_by(PricingRule.key.asc())))


@router.get("/discount", response_model=PricingDiscountResponse)
def pricing_discount(db: Session = Depends(get_db)) -> PricingDiscountResponse:
    discount = load_pricing_discount(db)
    return PricingDiscountResponse(active=discount.active, rate=discount.rate, label=discount.label)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_pricing_discount.py -v`
Expected: PASS（全部）

- [ ] **Step 5: 提交**

```bash
git add src/pix_web/schemas.py src/pix_web/routers/pricing.py tests/test_pricing_discount.py
git commit -m "feat(pricing): expose GET /pricing/discount endpoint"
```

---

## Task 5: 前端类型、API、共享辅助

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/lib/pricing.ts`

- [ ] **Step 1: 新增类型**

`apps/web/src/types.ts`，在 `PricingRule` 类型（410-415 行）之后新增：

```ts
export type PricingDiscount = {
  active: boolean
  rate: number
  label: string
}
```

- [ ] **Step 2: 新增 API 方法**

`apps/web/src/api.ts`：在顶部类型 import 列表（约 24 行，`PricingRule,` 处）加入 `PricingDiscount,`；在 `pricing()`（356-358 行）之后新增：

```ts
  pricingDiscount(token?: string | null) {
    return request<PricingDiscount>('/pricing/discount', {}, token)
  },
```

- [ ] **Step 3: 新增共享辅助**

创建 `apps/web/src/lib/pricing.ts`：

```ts
import type { PricingDiscount } from '../types'

/** 展示用折后价；必须与后端 apply_discount 取整规则保持一致（向下取整 + 保底 1 点）。 */
export function applyDiscount(amount: number, discount?: PricingDiscount | null): number {
  if (!discount?.active || amount <= 0) return amount
  if (discount.rate <= 0) return 0
  return Math.max(1, Math.floor(amount * discount.rate))
}

/** 0.8 → 8；0.85 → 8.5（避免浮点噪声）。 */
export function discountZhe(rate: number): number {
  return Math.round(rate * 100) / 10
}

/** 0.8 → 20（百分比折扣）。 */
export function discountPercentOff(rate: number): number {
  return Math.round((1 - rate) * 100)
}
```

- [ ] **Step 4: 类型检查**

Run（在 `apps/web` 目录）：`npm run build`
Expected: 构建成功，无 TS 报错

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/lib/pricing.ts
git commit -m "feat(pricing): add frontend discount type, api and helpers"
```

---

## Task 6: 共享 EstimateBadge + App 透传

**Files:**
- Create: `apps/web/src/components/EstimateBadge.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/pages/WorkspacePage.tsx`

- [ ] **Step 1: 新建 EstimateBadge 组件**

创建 `apps/web/src/components/EstimateBadge.tsx`：

```tsx
import { useI18n } from '../i18n'
import { applyDiscount, discountPercentOff, discountZhe } from '../lib/pricing'
import type { PricingDiscount } from '../types'
import { Badge } from './ui/badge'

type Props = {
  price: number
  discount?: PricingDiscount | null
  sprite?: { billingUnits: number; basePrice: number; totalFrames: number } | null
  variant?: 'info' | 'danger' | 'outline' | 'success'
}

export function EstimateBadge({ price, discount, sprite, variant = 'info' }: Props) {
  const { text } = useI18n()
  const discounted = applyDiscount(price, discount)
  const active = !!discount?.active && discounted < price
  const frames = sprite ? text(`（共 ${sprite.totalFrames} 帧）`, ` (${sprite.totalFrames} frames)`) : ''

  if (!active) {
    const label = sprite
      ? text(
          `预计 ${sprite.billingUnits} × ${sprite.basePrice} = ${price} 点${frames}`,
          `Estimated ${sprite.billingUnits} × ${sprite.basePrice} = ${price} credits${frames}`,
        )
      : text(`预计 ${price} 点`, `Estimated ${price} credits`)
    return <Badge variant={variant}>{label}</Badge>
  }

  const rate = discount?.rate ?? 1
  const promo = (discount?.label || '').trim() || text(`${discountZhe(rate)} 折`, `${discountPercentOff(rate)}% OFF`)
  return (
    <Badge variant={variant}>
      <span className="mr-1 font-semibold text-amber-600">{promo}</span>
      <del className="opacity-60">{text(`${price} 点`, `${price} credits`)}</del>
      <span className="ml-1 font-semibold">{text(`${discounted} 点`, `${discounted} credits`)}</span>
      {sprite ? <span className="ml-1 opacity-70">{frames}</span> : null}
    </Badge>
  )
}
```

> 配色 class 仅为示意，可按现有设计系统微调；逻辑（active 判定、原价划线、折后价、双语标签）保持不变。

- [ ] **Step 2: App.tsx 加载 discount state**

`apps/web/src/App.tsx`：
1. 在 `PricingRule` import（31 行 type import 列表）加入 `PricingDiscount`；
2. 在 `const [pricing, setPricing] = useState<PricingRule[]>([])`（87 行）后新增：
   ```ts
   const [discount, setDiscount] = useState<PricingDiscount | null>(null)
   ```
3. 在 `refreshCore` 的 `Promise.all`（162-175 行）数组末尾加入：
   ```ts
       api.pricingDiscount(activeToken).catch(() => null),
   ```
   并把解构（162 行）末尾加上 `, nextDiscount`；
4. 在 `setPricing(nextPricing)`（187 行）后新增：
   ```ts
   setDiscount(nextDiscount)
   ```
5. 登出重置处 `setPricing([])`（约 410 行）后新增：
   ```ts
   setDiscount(null)
   ```
6. 渲染处把 `discount` 透传：WorkspacePage（805 行）与 RawImagePage（806 行）的 props 各加 `discount={discount}`。

- [ ] **Step 3: WorkspacePage 透传**

`apps/web/src/pages/WorkspacePage.tsx`：
1. props 类型 `WorkspacePageProps` 加入 `discount?: PricingDiscount | null`（并 import 类型）；
2. 解构（27 行）加入 `discount`；
3. 传给两个面板（37 行）：`<SingleGeneratePanel ... discount={discount} />` 与 `<BatchGeneratePanel ... discount={discount} />`。

- [ ] **Step 4: 类型检查**

Run（在 `apps/web`）：`npm run build`
Expected: 构建成功（此时面板尚未声明 `discount` prop，TS 会报错——继续 Task 7 修复；若想分步绿，可先在两个面板 Props 加 `discount?: PricingDiscount | null` 占位再 build）

> 为保证每步可构建，建议本步把 SingleGeneratePanel / BatchGeneratePanel 的 Props 先加上 `discount?: PricingDiscount | null`（仅声明、暂不使用），使 `npm run build` 通过，再进入 Task 7 真正使用。

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/components/EstimateBadge.tsx apps/web/src/App.tsx apps/web/src/pages/WorkspacePage.tsx
git commit -m "feat(pricing): add EstimateBadge and thread discount through app"
```

---

## Task 7: 三个估价面板接入折扣

**Files:**
- Modify: `apps/web/src/components/SingleGeneratePanel.tsx`
- Modify: `apps/web/src/components/BatchGeneratePanel.tsx`
- Modify: `apps/web/src/pages/RawImagePage.tsx`

- [ ] **Step 1: SingleGeneratePanel**

1. import：`import { EstimateBadge } from './EstimateBadge'` 与类型 `PricingDiscount`（6 行 type import）；
2. `Props`（20 行）加入 `discount?: PricingDiscount | null`，函数签名（114 行）解构加入 `discount`；
3. 把 `PixPanel` 的 `action`（399 行）替换为：
   ```tsx
   action={<EstimateBadge price={price} discount={discount} sprite={isSprite ? { billingUnits, basePrice, totalFrames } : null} />}
   ```

- [ ] **Step 2: RawImagePage**

1. import `EstimateBadge` 与 `PricingDiscount`；
2. `Props`（21 行附近）加入 `discount?: PricingDiscount | null`，签名（61 行）解构加入 `discount`；
3. 折后价用于余额判断——把 `insufficientCredits`（82 行）改为基于折后价：
   ```tsx
   const discountedPrice = applyDiscount(price, discount)   // import { applyDiscount } from '../lib/pricing'
   const insufficientCredits = typeof balance?.available_credits === 'number' && balance.available_credits < discountedPrice
   ```
4. 估价 Badge（132 行内嵌的 `<Badge variant={insufficientCredits ? 'danger' : 'info'}>预计...`）替换为：
   ```tsx
   <EstimateBadge price={price} discount={discount} variant={insufficientCredits ? 'danger' : 'info'} />
   ```

- [ ] **Step 3: BatchGeneratePanel**

批量是「逐任务折扣后求和」（与后端一致：每个 job 独立 `apply_discount` 再相加）。
> 注意：本面板用 i18next `t('batchForm.taskBadge', {...})`（约 145 行的 Badge）与 `BatchCostSummary` 子组件 `t('batchForm.costSummary', {...})`（约 167 行）展示价格，不是 inline `text(zh,en)`。只要 Step 3.3 把 `unitPrice`/`totalPrice` 换成折后值，这两处数字会自动变为折后价，无需替换 i18n key；折扣标签按下面 3.4 的独立 span 插在 145 行 Badge 旁即可。
1. import `applyDiscount`（`from '../lib/pricing'`）与类型 `PricingDiscount`；
2. `Props` 加入 `discount?: PricingDiscount | null`，签名解构加入 `discount`；
3. 折后单价 / 总价（69-71 行）：
   ```tsx
   const unitPrice = pricing.find((item) => item.key === batchMode)?.price_credits ?? 0
   const discountedUnit = applyDiscount(unitPrice, discount)
   const taskCount = batchMode === 'asset' ? lines.length : uploaded.length
   const totalPrice = taskCount * discountedUnit
   ```
   `insufficientCredits`（73 行）继续用新的 `totalPrice`（已是折后）。
4. 在现有总价展示处补一个折扣标签（找到渲染 `totalPrice` 的 Badge / 文案；用 `discount?.active` 决定是否显示原价划线）。最小实现：当 `discount?.active` 时，额外渲染：
   ```tsx
   {discount?.active && (
     <span className="ml-2 text-xs text-amber-600">
       {(discount.label || '').trim() || `${Math.round(discount.rate * 100) / 10} 折`}
     </span>
   )}
   ```

- [ ] **Step 4: 类型检查 + 视觉自检**

Run（在 `apps/web`）：`npm run build`
Expected: 构建成功，无 TS 报错。
（可选）`npm run dev` 本地起前端，确认折扣关闭时显示「预计 X 点」，折扣开启时显示「标签 + 原价划线 + 折后价」。

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/components/SingleGeneratePanel.tsx apps/web/src/components/BatchGeneratePanel.tsx apps/web/src/pages/RawImagePage.tsx
git commit -m "feat(pricing): show discounted estimate in generate panels"
```

---

## Task 8: 文档与版本号

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `src/pix/__init__.py`
- Modify: `apps/web/package.json`

- [ ] **Step 1: README**

在「管理后台运营能力」一节补充一段（说明折扣机制 + 新接口）：

```markdown
管理后台「系统设置 → 价格折扣」可开启全局点数折扣：设置 `pricing.discount_enabled` 开关、`pricing.discount_rate` 倍率（0~1，如 0.8 = 8 折，0 = 限免）与可选 `pricing.discount_label` 促销文案。折扣只作用于生成任务（asset / 文生图 / 图生图 / 序列帧），按「先算总价再打折、向下取整、原价>0 保底 1 点」扣点，并在创建任务时锁定；作品库 / 素材包扩容不受影响。前端通过公开接口 `GET /pricing/discount`（返回 `{active, rate, label}`）展示原价划线 + 折后价 + 折扣标签。折扣实扣点数会写入任务计费快照（`billing.original_total_points` / `total_points` / `discount`）。
```

并把「版本与发布」里的当前版本从 `1.80.1` 改为 `1.81.0`。

- [ ] **Step 2: CHANGELOG**

在 `## [Unreleased]` 的 `### Added` 列表末尾新增：

```markdown
- 新增全局点数折扣：管理后台「系统设置 → 价格折扣」可开关折扣、设置倍率（0~1）与促销文案，生成任务按折扣倍率向下取整（原价>0 保底 1 点）扣点并在创建时锁定；作品库 / 素材包扩容不打折。新增公开接口 `GET /pricing/discount`，前端估价展示原价划线 + 折后价 + 折扣标签。
```

- [ ] **Step 3: 版本号 1.81.0**

- `pyproject.toml` 第 7 行：`version = "1.81.0"`
- `src/pix/__init__.py` 第 3 行：`__version__ = "1.81.0"`
- `apps/web/package.json` 第 4 行：`"version": "1.81.0",`

- [ ] **Step 4: 全量回归**

Run: `python -m pytest tests/ -v`
Expected: PASS
Run（在 `apps/web`）：`npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add README.md CHANGELOG.md pyproject.toml src/pix/__init__.py apps/web/package.json
git commit -m "docs(pricing): document global discount and bump version to 1.81.0"
```

---

## 完成校验清单

- [ ] `python -m pytest tests/ -v` 全绿（含新 `tests/test_pricing_discount.py`）
- [ ] `apps/web` 下 `npm run build` 成功
- [ ] 折扣关闭：估价显示「预计 X 点」，扣点 = 原价（回归）
- [ ] 折扣开启（如 0.8）：估价显示标签 + 原价划线 + 折后价；建任务冻结 = 折后价；失败退款 = 折后价
- [ ] 倍率越界（如 2 / -1）在系统设置保存时报 422
- [ ] 作品库扩容（60 点）、素材包扩容仍按原价（未被折扣影响）
