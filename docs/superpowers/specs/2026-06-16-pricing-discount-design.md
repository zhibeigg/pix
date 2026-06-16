# 打折功能设计（全局点数折扣）

- 日期：2026-06-16
- 状态：已确认设计，待实现
- 版本影响：功能更新，`1.80.1 → 1.81.0`（B 位递增）

## 1. 背景与目标

Pix 当前对生成任务按 `PricingRule` 表里的固定点数计费：创建任务时 `_price_for_request`
算出总价 → `reserve_credits` 冻结 → 成功 `consume_reserved` 确认消费 / 失败 `refund_reserved`
退款。前端通过 `GET /pricing` 拿到价格规则，自行计算并展示「预计 X 点」。

目标：新增一个**全局统一折扣**能力，让生成任务的消耗点数按一个折扣倍率打折。管理员在后台
开关折扣、设置倍率与促销文案；用户在估价处看到原价划线、折后价与折扣标签。

## 2. 已确认的关键决策

1. **折扣范围**：全局统一折扣——一个倍率对所有任务类型、所有用户生效（不做按类型 / 按用户 / 限时）。
2. **取整规则**：向下取整 + 保底 1 点——原价 > 0 的任务折后最少扣 1 点（不因折扣变免费）；
   仅当倍率为 0 时才免费。
3. **前端展示**：原价划线 + 折后价 + 折扣标签（如「限时 8 折 ~~5 点~~ 4 点」）。
4. **作用扣点**：只对生成任务（`asset` / `text_to_image` / `image_to_image` / `sprite_sheet`）打折；
   作品库扩容（60 点）、素材包数量扩容等账号功能扣点保持原价。

## 3. 方案选型

| 方案 | 做法 | 取舍 |
|---|---|---|
| **A. 复用 SystemSetting（采用）** | 折扣开关 / 倍率 / 标签作为三个系统设置项，走现有「系统设置」基础设施 | 与 `referral.*`、`registration_bonus_credits` 完全一致；无需建表 / 迁移；后台界面自动渲染；改动最小 |
| B. 给 PricingRule 加列 | 每条价格规则加 `discount_rate` 列 | 全局折扣放进按行存储的表里别扭，需迁移，要么改所有行要么塞特殊「全局行」，反模式 |
| C. 新建折扣表 / 模块 | 单独的 discount 配置实体 | 对「一个全局倍率」严重过度设计 |

采用 **方案 A**。

## 4. 详细设计

### 4.1 配置（系统设置）

在 `src/pix_web/system_settings.py` 的 `SETTING_DEFINITIONS` 新增分类「价格折扣」，三项；
并把三项的默认值加入 `DEFAULT_SYSTEM_SETTINGS` 做种子：

| key | 类型 | 默认 | 含义 |
|---|---|---|---|
| `pricing.discount_enabled` | boolean | `false` | 折扣总开关 |
| `pricing.discount_rate` | number | `1.0` | 折扣倍率，范围 `0 ~ 1`，如 `0.8` = 8 折；`0` = 限免；`1` = 不打折 |
| `pricing.discount_label` | string | `""` | 可选促销文案（如「限时 8 折」）；留空时前端按倍率自动生成 |

校验：在 `_normalize_value` 对 `pricing.discount_rate` 增加范围校验，越界（< 0 或 > 1）返回
`422`（提示「折扣倍率应在 0~1 之间」）。

后台「系统设置」面板按 `SETTING_DEFINITIONS` / `list_admin_settings` 自动渲染，**无需新增管理端前端代码**。

### 4.2 折扣加载与计算

`src/pix_web/system_settings.py` 新增数据类与加载函数（与 `load_referral_settings` 同款）：

```python
@dataclass(frozen=True)
class PricingDiscount:
    enabled: bool
    rate: float   # 已裁剪到 [0, 1]
    label: str    # 管理员显式文案，可能为空

    @property
    def active(self) -> bool:
        return self.enabled and 0.0 <= self.rate < 1.0


def load_pricing_discount(db: Session) -> PricingDiscount:
    values = _stored_values(db)
    enabled = _parse_bool(values.get("pricing.discount_enabled", "false"))
    rate = min(1.0, max(0.0, _parse_float(values.get("pricing.discount_rate", "1"), 1.0)))
    label = values.get("pricing.discount_label", "").strip()
    return PricingDiscount(enabled=enabled, rate=rate, label=label)
```

`src/pix_web/pricing.py` 新增纯函数（核心取整规则，独立可测）：

```python
import math

def apply_discount(amount: int, rate: float) -> int:
    """原价>0 时向下取整且保底 1 点；rate>=1 或 amount<=0 原样返回；rate<=0 返回 0（限免）。"""
    if amount <= 0 or rate >= 1.0:
        return amount
    if rate <= 0.0:
        return 0
    return max(1, math.floor(amount * rate))
```

校验示例：

| 场景 | 原价 | 倍率 | 折后 |
|---|---|---|---|
| asset | 20 | 0.8 | 16 |
| 序列帧 8×8（units=8） | 40 | 0.8 | 32 |
| 序列帧 1×8（units=1） | 5 | 0.8 | 4 |
| 保底 | 1 | 0.5 | 1 |
| 限免 | 20 | 0 | 0 |
| 免费任务（local_pixelize） | 0 | 0.8 | 0 |
| 不打折 | 20 | 1.0 | 20 |

### 4.3 计费链路接入（`src/pix_web/jobs.py`）

折扣作用在「算出总价之后、冻结之前」，**只对生成任务**：

- 现有 `_price_for_request`（原价 = base × 序列帧 billing 单位）重命名为 `_original_price_for_request`；
- 新 `_price_for_request(db, req)` = `apply_discount(_original_price_for_request(db, req), load_pricing_discount(db).rate)`；
- 所有调用点自动按折后价生效——单任务 `create_job_in_transaction`、批量 `create_jobs_batch`、
  重试 `retry_failed_job` / `retry_failed_jobs_in_batch` 的余额校验、`reserve_credits` 冻结、
  `price_credits` 落库都用折后价；
- `consume_reserved` / `refund_reserved` 基于 `job.reserved_credits`（已是折后值），**无需改动**——
  确认消费、失败退款自动正确；
- **折扣在创建时锁定**：任务冻结后管理员改折扣不影响在途任务。

**计费快照** `params_json.billing`（`_billing_snapshot_for_request`）扩展：

- 记录 `original_total_points`（折前总价）、`total_points`（折后实扣）、`discount: {rate, label}`；
- 序列帧保持原有字段（`rows`/`cols`/`frame_base_price`/`frame_count`/`billing_units`/`formula` 等），
  其中 `total_points` 改为折后实扣值，新增 `original_total_points`；
- 非序列帧任务原本返回 `None`；折扣生效（`discount.active`）时也写入一个含 `discount` 块的精简快照，
  方便作品库「参数」快览审计；折扣未生效时维持 `None`（不改变现有行为）。

### 4.4 对外接口

- `GET /pricing` **不变**（仍返回原价规则数组，不破坏现有消费方）；
- **新增** `GET /pricing/discount`（公开，`src/pix_web/routers/pricing.py`）→
  响应模型 `PricingDiscountResponse {active: bool, rate: float, label: str}`，
  数据来自 `load_pricing_discount(db)`（`active=False` 时仍返回 `rate`/`label` 供调试，但前端只在 `active` 时展示折扣）。

### 4.5 前端

- `apps/web/src/types.ts` 新增 `PricingDiscount` 类型；
- `apps/web/src/api.ts` 新增 `pricingDiscount()` → `GET /pricing/discount`；
- `apps/web/src/App.tsx` 在现有加载 `pricing` 的 `Promise.all` 里一并加载 `discount` state，
  随 `pricing` 透传到各估价面板（登出 / 刷新时一并清理 / 刷新）；
- 新增共享展示辅助 `applyDiscount(amount, discount)`（镜像后端取整规则，**仅用于展示**）；
- 估价 Badge：折扣生效时显示「`{标签}` ~~原价 X 点~~ 折后 Y 点」，
  标签 `label` 非空用其原文，留空时按倍率自动生成双语（中「X 折」/ 英「X% OFF」，X = `round((1-rate)*100)`）；
  折扣未生效时维持原样「预计 X 点」。涉及显示「预计点数」的入口：
  `SingleGeneratePanel`、`BatchGeneratePanel`、`RawImagePage` 等。

### 4.6 计费一致性说明

- 前端的 `applyDiscount` 仅用于展示，**权威计费在后端**。前端已经在复刻序列帧
  `basePrice × billingUnits` 的算法，再复刻一次折扣取整属于同类既有模式，可接受；
  spec 与实现需保证两端取整规则一致（向下取整 + 保底 1 点）。

## 5. 测试计划

- 单元测试 `apply_discount`：覆盖 0 原价、保底 1、`rate>=1` passthrough、`rate=0` 限免、序列帧总价；
- 单元测试 `load_pricing_discount`：开关解析、倍率裁剪到 `[0,1]`、默认值；
- 集成测试：
  - 折扣生效时创建任务 → `job.reserved_credits` == `job.price_credits` == 折后值；账户冻结额=折后值；
  - 任务失败退款额 == 折后值（退回 `available_credits`）；
  - 折扣关闭时 == 原价；
  - 序列帧折后价 == `apply_discount(base × units, rate)`。

## 6. 同步更新清单（项目规范要求）

- **默认配置**：`DEFAULT_SYSTEM_SETTINGS` 增加三项种子；
- **示例配置**：`.env*` 无需改（折扣是 DB 管理的系统设置，非环境变量）；
- **README**：「管理后台运营能力」补充价格折扣说明 + 新接口 `GET /pricing/discount`；
- **语言文件**：前端 Badge 双语文案走现有 `text(zh, en)`；
- **外部 API 文档**：本仓库无独立 API doc 文件，新接口随 FastAPI OpenAPI 自动暴露并在 README 记录；
- **版本号**：`1.80.1 → 1.81.0`，同步 `pyproject.toml`、`src/pix/__init__.py`、`apps/web/package.json`，并补 `CHANGELOG.md`。

## 7. 影响面与风险

- 改动集中在配置层（系统设置）+ 计费入口（`jobs.py` 的价格函数）+ 一个只读接口 + 前端展示；
  不触碰冻结 / 消费 / 退款的底层 `credits.py`，回归风险低。
- 主要风险点：前后端取整规则一致性、`_normalize_value` 对 float 倍率的校验、批量 / 重试路径
  都走折后价。测试计划已覆盖。
