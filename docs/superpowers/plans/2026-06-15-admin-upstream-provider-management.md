# 后台上游供应商统一管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让后台能统一查看、从预设目录单独新增、编辑/删除/启停/调优先级上游生图供应商，配置以数据库为单一真相源、改完即时生效不重启。

**Architecture:** 新增 `image_providers` 表（DB 为真相源）。`load_managed_pix_config`（worker/路由每任务 fresh 调用）在加载 base cfg 后，用 DB 供应商**整体替换** `cfg.image_providers` 并按 `priority` 排序 → 下一个任务即生效。首次启动从现有 `load_config()`（已合并 `config.toml`+`.env`）种子导入。后台新增 `routers/providers.py` 提供 CRUD + 预设目录；前端在 `AdminPanel` 加「上游供应商」标签。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · React + TypeScript (Vite) · Radix UI · 测试用 `unittest.TestCase` + 内存 SQLite（项目现有约定，用 `python -m pytest` 运行）。

**Spec:** `docs/superpowers/specs/2026-06-15-admin-upstream-provider-management-design.md`

---

## File Structure

**后端（新建）**
- `src/pix_web/provider_store.py` — DB↔`ImageProviderConfig` 转换、`image_providers_from_db`、`apply_db_image_providers`、`ensure_seeded_image_providers`。
- `src/pix_web/provider_presets.py` — 静态预设目录 `PROVIDER_PRESETS` + `preset_to_dict`。
- `src/pix_web/routers/providers.py` — `/admin/providers` CRUD + `/presets`。
- `migrations/versions/0017_image_providers.py` — 建表迁移。
- `tests/test_image_provider_store.py`、`tests/test_admin_providers.py` — 单测。

**后端（修改）**
- `src/pix_web/models.py` — 新增 `ImageProvider` ORM 模型（+ 确保 `Boolean` 已 import）。
- `src/pix_web/system_settings.py` — `load_managed_pix_config` 末尾叠加 DB 供应商。
- `src/pix_web/db.py` — `init_db` 追加 `ensure_seeded_image_providers(db)`。
- `src/pix_web/schemas.py` — 供应商 CRUD 的 Pydantic 模型。
- `src/pix_web/main.py` — 注册 `providers.router`。

**前端（修改）**
- `apps/web/src/types.ts` — 供应商/预设 TS 类型。
- `apps/web/src/api.ts` — `/admin/providers*` 调用。
- `apps/web/src/hooks/useAdminActions.ts` — 供应商 CRUD 回调。
- `apps/web/src/components/AdminPanel.tsx` — 新标签 + `ProviderManager` 子组件。
- `apps/web/src/pages/AdminPage.tsx` — 透传新 props（若 props 在此装配）。

**文档/版本（修改）**
- `config.example.toml`、`.env.example`、`.env.production.example`、`README.md`、`CHANGELOG.md`、`pyproject.toml`（+ `__version__` 源）。

---

## Task 1: `ImageProvider` ORM 模型 + Alembic 迁移

**Files:**
- Modify: `src/pix_web/models.py`
- Create: `migrations/versions/0017_image_providers.py`

- [ ] **Step 1: 在 `models.py` 新增模型**

确认顶部 import 含 `Boolean`（现有 import 行为 `from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint`）——若无 `Boolean` 则加上：

```python
from sqlalchemy import Boolean, JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
```

在文件末尾（其它模型之后）追加：

```python
class ImageProvider(Base):
    """后台可管理的上游生图供应商；DB 为真相源，运行时叠加进 AppConfig。"""

    __tablename__ = "image_providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    base_url: Mapped[str] = mapped_column(Text, default="")
    api_key: Mapped[str] = mapped_column(Text, default="")
    api_key_env: Mapped[str] = mapped_column(String(96), default="")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    protocols: Mapped[list[Any]] = mapped_column(JSON, default=list)
    discover_models: Mapped[bool] = mapped_column(Boolean, default=False)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    preset_key: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

- [ ] **Step 2: 写迁移 `0017_image_providers.py`**（镜像 `0016_job_provider.py` 风格）

```python
"""create image_providers table

Revision ID: 0017_image_providers
Revises: 0016_job_provider
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017_image_providers"
down_revision = "0016_job_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_providers",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("base_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("api_key_env", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("protocols", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("discover_models", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("models", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("preset_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("image_providers")
```

- [ ] **Step 3: 验证表能建**（内存 SQLite + create_all）

Run: `python -c "from sqlalchemy import create_engine; from pix_web.models import Base; e=create_engine('sqlite:///:memory:'); Base.metadata.create_all(e); print(sorted(t.name for t in Base.metadata.sorted_tables))"`
Expected: 输出含 `'image_providers'`，无异常。

- [ ] **Step 4: Commit**

```bash
git add src/pix_web/models.py migrations/versions/0017_image_providers.py
git commit -m "feat(db): add image_providers table + migration"
```

---

## Task 2: `provider_store.py` — DB↔config 转换、注入、种子

**Files:**
- Create: `src/pix_web/provider_store.py`
- Test: `tests/test_image_provider_store.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix.api.image_model_registry import TEXT_TO_IMAGE, candidates_for_model, provider_api_key
from pix.config import AppConfig
from pix_web.models import Base, ImageProvider
from pix_web.provider_store import (
    apply_db_image_providers,
    ensure_seeded_image_providers,
    image_providers_from_db,
)


class ProviderStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _row(self, **kw) -> ImageProvider:
        defaults = dict(
            id="p1", display_name="P1", enabled=True, base_url="https://p1.example",
            api_key="k1", api_key_env="", priority=10, discover_models=False,
            protocols=["openai_images"],
            models=[{"id": "gpt-image-2", "provider_model": "gpt-image-2",
                     "protocol": "openai_images", "operations": ["text_to_image", "image_to_image"]}],
        )
        defaults.update(kw)
        row = ImageProvider(**defaults)
        self.db.add(row)
        self.db.commit()
        return row

    def test_seed_imports_from_load_config_when_empty(self) -> None:
        with patch.dict(os.environ, {"PACKY_API_KEY": "pk-seed"}, clear=True):
            ensure_seeded_image_providers(self.db)
        ids = {r.id for r in self.db.scalars(select(ImageProvider))}
        self.assertIn("packy", ids)

    def test_seed_is_idempotent(self) -> None:
        with patch.dict(os.environ, {"PACKY_API_KEY": "pk-seed"}, clear=True):
            ensure_seeded_image_providers(self.db)
            first = self.db.scalar(select(ImageProvider.id).limit(1))
            ensure_seeded_image_providers(self.db)
        count = len(list(self.db.scalars(select(ImageProvider))))
        same = self.db.scalar(select(ImageProvider.id).limit(1))
        self.assertGreaterEqual(count, 1)
        self.assertEqual(first, same)

    def test_apply_replaces_and_sorts_by_priority(self) -> None:
        self._row(id="p2", display_name="P2", base_url="https://p2.example", api_key="k2", priority=5)
        self._row(id="p1", priority=20)
        cfg = AppConfig()
        cfg.image_providers = []  # base cfg may already contain env providers; replace expected
        apply_db_image_providers(cfg, self.db)
        self.assertEqual([p.id for p in cfg.image_providers], ["p2", "p1"])

    def test_apply_keeps_base_when_db_empty(self) -> None:
        cfg = AppConfig()
        before = list(cfg.image_providers)
        apply_db_image_providers(cfg, self.db)
        self.assertEqual([p.id for p in cfg.image_providers], [p.id for p in before])

    def test_api_key_env_fallback_after_injection(self) -> None:
        self._row(id="p1", api_key="", api_key_env="MY_PROVIDER_KEY")
        cfg = AppConfig()
        apply_db_image_providers(cfg, self.db)
        provider = next(p for p in cfg.image_providers if p.id == "p1")
        with patch.dict(os.environ, {"MY_PROVIDER_KEY": "from-env"}, clear=True):
            self.assertEqual(provider_api_key(provider), "from-env")

    def test_db_providers_flow_into_candidates(self) -> None:
        self._row(id="p1", priority=10)
        self._row(id="p2", display_name="P2", base_url="https://p2.example", api_key="k2", priority=20)
        cfg = AppConfig()
        cfg.image_gen.model = "gpt-image-2"
        apply_db_image_providers(cfg, self.db)
        candidates = candidates_for_model(cfg, "gpt-image-2", TEXT_TO_IMAGE)
        self.assertEqual([c.provider.id for c in candidates], ["p1", "p2"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_image_provider_store.py -q`
Expected: FAIL（`ModuleNotFoundError: pix_web.provider_store`）。

- [ ] **Step 3: 写实现 `provider_store.py`**

```python
"""数据库为准的上游供应商：DB↔配置转换、注入 AppConfig、首次种子。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pix.config import AppConfig, ImageProviderConfig, ImageProviderModelConfig, load_config
from pix_web.models import ImageProvider

_MODEL_STR_FIELDS = ("id", "provider_model", "label", "protocol", "endpoint", "edit_endpoint", "edit_mode")
_MODEL_LIST_FIELDS = ("operations", "sizes", "qualities", "output_formats")


def _model_from_dict(data: dict[str, Any]) -> ImageProviderModelConfig:
    model = ImageProviderModelConfig()
    for fld in _MODEL_STR_FIELDS:
        value = data.get(fld)
        if isinstance(value, str):
            setattr(model, fld, value)
    for fld in _MODEL_LIST_FIELDS:
        value = data.get(fld)
        if isinstance(value, list):
            setattr(model, fld, [str(item) for item in value])
    if isinstance(data.get("supports_n"), bool):
        model.supports_n = data["supports_n"]
    if isinstance(data.get("requires_public_image_url"), bool):
        model.requires_public_image_url = data["requires_public_image_url"]
    if isinstance(data.get("extra"), dict):
        model.extra = dict(data["extra"])
    return model


def _model_to_dict(model: ImageProviderModelConfig) -> dict[str, Any]:
    return {
        "id": model.id,
        "provider_model": model.provider_model,
        "label": model.label,
        "protocol": model.protocol,
        "operations": list(model.operations),
        "sizes": list(model.sizes),
        "qualities": list(model.qualities),
        "output_formats": list(model.output_formats),
        "edit_mode": model.edit_mode,
        "extra": dict(model.extra),
    }


def _config_from_row(row: ImageProvider) -> ImageProviderConfig:
    return ImageProviderConfig(
        id=row.id,
        display_name=row.display_name or row.id,
        enabled=bool(row.enabled),
        base_url=row.base_url or "",
        api_key_env=row.api_key_env or "",
        api_key=row.api_key or None,
        priority=int(row.priority or 100),
        discover_models=bool(row.discover_models),
        protocols=[str(p) for p in (row.protocols or [])] or ["openai_images"],
        models=[_model_from_dict(m) for m in (row.models or []) if isinstance(m, dict)],
    )


def image_providers_from_db(db: Session) -> list[ImageProviderConfig]:
    rows = db.scalars(select(ImageProvider)).all()
    return [_config_from_row(row) for row in rows]


def apply_db_image_providers(cfg: AppConfig, db: Session) -> AppConfig:
    """DB 有供应商时整体替换 cfg.image_providers（DB 为唯一真相源），按 priority 排序。"""
    providers = image_providers_from_db(db)
    if providers:
        providers.sort(key=lambda item: int(item.priority or 100))
        cfg.image_providers = providers
    return cfg


def ensure_seeded_image_providers(db: Session) -> None:
    """首次启动：表为空时，从 load_config()（已合并 config.toml + .env）导入供应商做种子。幂等。"""
    if db.scalar(select(ImageProvider).limit(1)) is not None:
        return
    cfg = load_config()
    for provider in cfg.image_providers:
        if not provider.id:
            continue
        db.add(
            ImageProvider(
                id=provider.id,
                display_name=provider.display_name or provider.id,
                enabled=bool(provider.enabled),
                base_url=provider.base_url or "",
                api_key=provider.api_key or "",
                api_key_env=provider.api_key_env or "",
                priority=int(provider.priority or 100),
                discover_models=bool(provider.discover_models),
                protocols=list(provider.protocols or []),
                models=[_model_to_dict(m) for m in (provider.models or [])],
                preset_key=provider.id,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # 并发启动时另一进程已种子，安全忽略
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_image_provider_store.py -q`
Expected: PASS（6 项）。

- [ ] **Step 5: Commit**

```bash
git add src/pix_web/provider_store.py tests/test_image_provider_store.py
git commit -m "feat(providers): DB-backed provider store (load/inject/seed)"
```

---

## Task 3: 接线 — `load_managed_pix_config` 叠加 + `init_db` 种子

**Files:**
- Modify: `src/pix_web/system_settings.py:555-556`
- Modify: `src/pix_web/db.py:26-33`
- Test: `tests/test_image_provider_store.py`（追加接线测试）

- [ ] **Step 1: 追加失败测试**（验证 `load_managed_pix_config` 用了 DB 供应商）

在 `tests/test_image_provider_store.py` 追加：

```python
class LoadManagedConfigWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_load_managed_pix_config_uses_db_providers(self) -> None:
        from types import SimpleNamespace
        from pix_web.system_settings import load_managed_pix_config

        self.db.add(ImageProvider(
            id="only-db", display_name="OnlyDB", enabled=True, base_url="https://db.example",
            api_key="kk", api_key_env="", priority=1, discover_models=False,
            protocols=["openai_images"], models=[],
        ))
        self.db.commit()
        settings = SimpleNamespace(pix_config_file=None)
        with patch.dict(os.environ, {}, clear=True):
            cfg = load_managed_pix_config(self.db, settings)
        self.assertIn("only-db", [p.id for p in cfg.image_providers])
        self.assertEqual(cfg.image_providers[0].id, "only-db")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_image_provider_store.py::LoadManagedConfigWiringTests -q`
Expected: FAIL（DB 供应商未被叠加）。

- [ ] **Step 3: 改 `system_settings.py`**

顶部 import 区加：

```python
from pix_web.provider_store import apply_db_image_providers
```

把 `load_managed_pix_config`（约 555-556 行）改为：

```python
def load_managed_pix_config(db: Session, settings: WebSettings) -> AppConfig:
    cfg = load_config(config_file=settings.pix_config_file, overrides=managed_pix_overrides_from_db(db))
    return apply_db_image_providers(cfg, db)
```

> 注：`provider_store` 仅依赖 `pix.config` 与 `pix_web.models`，不 import `system_settings`，无循环依赖。

- [ ] **Step 4: 改 `db.py` 的 `init_db`**

顶部 import 加：

```python
from pix_web.provider_store import ensure_seeded_image_providers
```

`init_db` 内最后追加一行：

```python
def init_db(engine: Engine, *, create_schema: bool = True) -> None:
    if create_schema:
        Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        ensure_default_pricing(db)
        ensure_default_system_settings(db)
        ensure_default_packages(db)
        ensure_seeded_image_providers(db)
```

- [ ] **Step 5: 运行测试确认通过 + 跑全量回归**

Run: `python -m pytest tests/test_image_provider_store.py tests/test_image_providers.py -q`
Expected: PASS（含新接线测试）。

- [ ] **Step 6: Commit**

```bash
git add src/pix_web/system_settings.py src/pix_web/db.py tests/test_image_provider_store.py
git commit -m "feat(providers): wire DB providers into managed config + seed on init_db"
```

---

## Task 4: 预设目录 `provider_presets.py`

**Files:**
- Create: `src/pix_web/provider_presets.py`
- Test: `tests/test_image_provider_store.py`（追加预设测试）

- [ ] **Step 1: 追加失败测试**

```python
class ProviderPresetTests(unittest.TestCase):
    def test_presets_are_well_formed(self) -> None:
        from pix_web.provider_presets import PROVIDER_PRESETS, preset_to_dict

        keys = [p.key for p in PROVIDER_PRESETS]
        self.assertIn("shengsuanyun", keys)
        self.assertIn("custom", keys)
        whitelist = {"openai_images", "midjourney", "ideogram", "fal", "kling", "gemini_native", "shengsuanyun"}
        for preset in PROVIDER_PRESETS:
            data = preset_to_dict(preset)
            self.assertTrue(data["display_name"])
            self.assertTrue(data["protocols"])
            for proto in data["protocols"]:
                self.assertIn(proto, whitelist)
            self.assertIsInstance(data["models"], list)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_image_provider_store.py::ProviderPresetTests -q`
Expected: FAIL（无 `provider_presets`）。

- [ ] **Step 3: 写实现**（取值与 `src/pix/config.py` 的 env 注入函数保持一致）

```python
"""后台「新增供应商」可选的预设目录。取值与 config.py 的 env 注入默认保持一致。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_GPT_IMAGE_SIZES = ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x1024", "1024x2048"]
_QUALITIES = ["auto", "low", "medium", "high"]
_FORMATS = ["png", "jpeg", "webp"]


@dataclass(frozen=True)
class ProviderPreset:
    key: str
    display_name: str
    protocols: tuple[str, ...]
    base_url: str
    api_key_env: str
    discover_models: bool = False
    models: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    note: str = ""


def _gpt_image_model(model_id: str, provider_model: str, protocol: str, *, edit_mode: str = "multipart") -> dict[str, Any]:
    return {
        "id": model_id,
        "provider_model": provider_model,
        "label": "GPT Image 2",
        "protocol": protocol,
        "operations": ["text_to_image", "image_to_image"],
        "sizes": list(_GPT_IMAGE_SIZES),
        "qualities": list(_QUALITIES),
        "output_formats": list(_FORMATS),
        "edit_mode": edit_mode,
    }


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="packy", display_name="Packy", protocols=("openai_images",),
        base_url="https://www.packyapi.com", api_key_env="PACKY_API_KEY",
        models=(_gpt_image_model("gpt-image-2", "gpt-image-2", "openai_images"),),
        note="OpenAI 兼容同步生图。",
    ),
    ProviderPreset(
        key="shengsuanyun", display_name="ShengSuanYun（胜算云）", protocols=("shengsuanyun",),
        base_url="https://router.shengsuanyun.com", api_key_env="SHENGSUANYUN_API_KEY",
        models=(_gpt_image_model("gpt-image-2", "openai/gpt-image-2", "shengsuanyun", edit_mode="image_input"),),
        note="OpenAI 风格请求体 + 异步任务轮询。",
    ),
    ProviderPreset(
        key="crazyrouter", display_name="Crazyrouter",
        protocols=("openai_images", "midjourney", "ideogram", "fal", "kling", "gemini_native"),
        base_url="https://crazyrouter.com", api_key_env="CRAZYROUTER_API_KEY",
        discover_models=True, models=(),
        note="多协议聚合，支持模型自动发现（需开启全局模型发现）。",
    ),
    ProviderPreset(
        key="openai", display_name="OpenAI", protocols=("openai_images",),
        base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY",
        models=(_gpt_image_model("gpt-image-1", "gpt-image-1", "openai_images"),),
        note="OpenAI 官方 Images API。",
    ),
    ProviderPreset(
        key="midjourney", display_name="Midjourney", protocols=("midjourney",),
        base_url="", api_key_env="", models=(), note="异步轮询协议，填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="ideogram", display_name="Ideogram", protocols=("ideogram",),
        base_url="", api_key_env="", models=(), note="填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="fal", display_name="Fal", protocols=("fal",),
        base_url="", api_key_env="", models=(), note="填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="kling", display_name="Kling", protocols=("kling",),
        base_url="", api_key_env="", models=(), note="异步轮询协议，填写你的中转 base_url。",
    ),
    ProviderPreset(
        key="custom", display_name="自定义（OpenAI 兼容）", protocols=("openai_images",),
        base_url="", api_key_env="", models=(), note="接任意 OpenAI 兼容上游，base_url 与模型自行填写。",
    ),
)


def preset_to_dict(preset: ProviderPreset) -> dict[str, Any]:
    return {
        "key": preset.key,
        "display_name": preset.display_name,
        "protocols": list(preset.protocols),
        "base_url": preset.base_url,
        "api_key_env": preset.api_key_env,
        "discover_models": preset.discover_models,
        "models": [dict(m) for m in preset.models],
        "note": preset.note,
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_image_provider_store.py::ProviderPresetTests -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/pix_web/provider_presets.py tests/test_image_provider_store.py
git commit -m "feat(providers): static provider preset catalog"
```

---

## Task 5: Pydantic schemas

**Files:**
- Modify: `src/pix_web/schemas.py`

- [ ] **Step 1: 追加 schemas**（Pydantic v2，风格同 `CreditPackageCreateRequest`）

在 `schemas.py` 末尾追加：

```python
class ImageProviderModelPayload(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    provider_model: str = ""
    label: str = ""
    protocol: str = "openai_images"
    operations: list[str] = Field(default_factory=lambda: ["text_to_image", "image_to_image"])
    sizes: list[str] = Field(default_factory=list)
    qualities: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=list)
    edit_mode: str = "multipart"


class ImageProviderCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(default="", max_length=128)
    enabled: bool = True
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = Field(default="", max_length=96)
    priority: int = 100
    discover_models: bool = False
    protocols: list[str] = Field(default_factory=lambda: ["openai_images"])
    models: list[ImageProviderModelPayload] = Field(default_factory=list)
    preset_key: str | None = None


class ImageProviderUpdateRequest(BaseModel):
    display_name: str = ""
    enabled: bool = True
    base_url: str = ""
    api_key: str = ""           # 空=保留原值（写入式更新）
    clear_api_key: bool = False
    api_key_env: str = Field(default="", max_length=96)
    priority: int = 100
    discover_models: bool = False
    protocols: list[str] = Field(default_factory=lambda: ["openai_images"])
    models: list[ImageProviderModelPayload] = Field(default_factory=list)


class ImageProviderResponse(BaseModel):
    id: str
    display_name: str
    enabled: bool
    base_url: str
    has_api_key: bool
    api_key_env: str
    priority: int
    discover_models: bool
    protocols: list[str]
    models: list[ImageProviderModelPayload]
    preset_key: str | None = None


class ImageProviderPresetResponse(BaseModel):
    key: str
    display_name: str
    protocols: list[str]
    base_url: str
    api_key_env: str
    discover_models: bool
    models: list[ImageProviderModelPayload]
    note: str = ""
```

- [ ] **Step 2: 导入自检**

Run: `python -c "import pix_web.schemas as s; print(s.ImageProviderCreateRequest, s.ImageProviderResponse, s.ImageProviderPresetResponse)"`
Expected: 三个类打印出来，无异常。

- [ ] **Step 3: Commit**

```bash
git add src/pix_web/schemas.py
git commit -m "feat(providers): pydantic schemas for provider CRUD"
```

---

## Task 6: `routers/providers.py` CRUD + 注册

**Files:**
- Create: `src/pix_web/routers/providers.py`
- Modify: `src/pix_web/main.py`
- Test: `tests/test_admin_providers.py`

- [ ] **Step 1: 写失败测试**（直接调用路由函数，镜像 `test_admin_batch_credits.py`）

```python
from __future__ import annotations

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pix_web.models import Base, ImageProvider, User
from pix_web.routers.providers import (
    create_provider,
    delete_provider,
    list_presets,
    list_providers,
    update_provider,
)
from pix_web.schemas import ImageProviderCreateRequest, ImageProviderUpdateRequest


def _create_req(**kw) -> ImageProviderCreateRequest:
    defaults = dict(id="p1", display_name="P1", base_url="https://p1.example",
                    api_key="k1", protocols=["openai_images"], models=[])
    defaults.update(kw)
    return ImageProviderCreateRequest(**defaults)


def _update_req(**kw) -> ImageProviderUpdateRequest:
    defaults = dict(display_name="P1", base_url="https://p1.example", protocols=["openai_images"], models=[])
    defaults.update(kw)
    return ImageProviderUpdateRequest(**defaults)


class AdminProvidersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db: Session = sessionmaker(bind=self.engine)()
        self.admin = User(email="admin@example.com", password_hash="x", display_name="admin", role="admin", status="active")
        self.db.add(self.admin)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_create_and_list_masks_key(self) -> None:
        created = create_provider(_create_req(), _admin=self.admin, db=self.db)
        self.assertTrue(created.has_api_key)
        self.assertFalse(hasattr(created, "api_key"))
        rows = list_providers(_admin=self.admin, db=self.db)
        self.assertEqual([r.id for r in rows], ["p1"])
        self.assertTrue(rows[0].has_api_key)

    def test_create_duplicate_returns_409(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            create_provider(_create_req(), _admin=self.admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_unknown_protocol_returns_422(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_provider(_create_req(protocols=["nope"]), _admin=self.admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_empty_base_url_returns_422(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_provider(_create_req(base_url="  "), _admin=self.admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_update_keeps_key_when_blank(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        update_provider("p1", _update_req(api_key=""), _admin=self.admin, db=self.db)
        self.assertEqual(self.db.get(ImageProvider, "p1").api_key, "k1")

    def test_update_overwrites_key_and_clears(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        update_provider("p1", _update_req(api_key="k2"), _admin=self.admin, db=self.db)
        self.assertEqual(self.db.get(ImageProvider, "p1").api_key, "k2")
        update_provider("p1", _update_req(clear_api_key=True), _admin=self.admin, db=self.db)
        self.assertEqual(self.db.get(ImageProvider, "p1").api_key, "")

    def test_delete(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        out = delete_provider("p1", _admin=self.admin, db=self.db)
        self.assertEqual(out, {"deleted": True})
        self.assertIsNone(self.db.get(ImageProvider, "p1"))

    def test_presets_available(self) -> None:
        presets = list_presets(_admin=self.admin)
        self.assertIn("shengsuanyun", [p.key for p in presets])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_admin_providers.py -q`
Expected: FAIL（无 `routers.providers`）。

- [ ] **Step 3: 写实现 `routers/providers.py`**

```python
"""管理员：上游生图供应商 CRUD + 预设目录。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import ImageProvider, User
from pix_web.provider_presets import PROVIDER_PRESETS, preset_to_dict
from pix_web.schemas import (
    ImageProviderCreateRequest,
    ImageProviderModelPayload,
    ImageProviderPresetResponse,
    ImageProviderResponse,
    ImageProviderUpdateRequest,
)
from pix_web.security import get_db, require_admin

router = APIRouter(prefix="/admin/providers", tags=["admin"])

PROTOCOL_WHITELIST = {"openai_images", "midjourney", "ideogram", "fal", "kling", "gemini_native", "shengsuanyun"}


def _to_response(row: ImageProvider) -> ImageProviderResponse:
    return ImageProviderResponse(
        id=row.id,
        display_name=row.display_name or row.id,
        enabled=bool(row.enabled),
        base_url=row.base_url or "",
        has_api_key=bool(row.api_key),
        api_key_env=row.api_key_env or "",
        priority=int(row.priority or 100),
        discover_models=bool(row.discover_models),
        protocols=[str(p) for p in (row.protocols or [])],
        models=[ImageProviderModelPayload(**m) for m in (row.models or []) if isinstance(m, dict)],
        preset_key=row.preset_key,
    )


def _validate(protocols: list[str], base_url: str) -> None:
    if not protocols:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="至少选择一个协议")
    for proto in protocols:
        if proto not in PROTOCOL_WHITELIST:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"未知协议：{proto}")
    if not base_url.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="base_url 不能为空")


@router.get("", response_model=list[ImageProviderResponse])
def list_providers(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[ImageProviderResponse]:
    rows = db.scalars(select(ImageProvider).order_by(ImageProvider.priority.asc(), ImageProvider.id.asc())).all()
    return [_to_response(row) for row in rows]


@router.get("/presets", response_model=list[ImageProviderPresetResponse])
def list_presets(_admin: User = Depends(require_admin)) -> list[ImageProviderPresetResponse]:
    return [ImageProviderPresetResponse(**preset_to_dict(preset)) for preset in PROVIDER_PRESETS]


@router.post("", response_model=ImageProviderResponse)
def create_provider(
    req: ImageProviderCreateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImageProviderResponse:
    if db.get(ImageProvider, req.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="供应商已存在")
    _validate(req.protocols, req.base_url)
    row = ImageProvider(
        id=req.id,
        display_name=req.display_name or req.id,
        enabled=req.enabled,
        base_url=req.base_url.strip(),
        api_key=req.api_key,
        api_key_env=req.api_key_env,
        priority=req.priority,
        discover_models=req.discover_models,
        protocols=list(req.protocols),
        models=[m.model_dump() for m in req.models],
        preset_key=req.preset_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{provider_id}", response_model=ImageProviderResponse)
def update_provider(
    provider_id: str,
    req: ImageProviderUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImageProviderResponse:
    row = db.get(ImageProvider, provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    _validate(req.protocols, req.base_url)
    row.display_name = req.display_name or provider_id
    row.enabled = req.enabled
    row.base_url = req.base_url.strip()
    row.api_key_env = req.api_key_env
    row.priority = req.priority
    row.discover_models = req.discover_models
    row.protocols = list(req.protocols)
    row.models = [m.model_dump() for m in req.models]
    if req.clear_api_key:
        row.api_key = ""
    elif req.api_key:
        row.api_key = req.api_key
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    row = db.get(ImageProvider, provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="供应商不存在")
    db.delete(row)
    db.commit()
    return {"deleted": True}
```

- [ ] **Step 4: 注册路由（`main.py`）**

把 `providers` 加入 routers import（与 `auth, credits, ...` 同处），并在 `admin.router` 之后追加：

```python
    app.include_router(providers.router)
```

（import 行示例：`from pix_web.routers import (auth, ..., admin, providers)`，按现有风格补 `providers`。）

- [ ] **Step 5: 运行测试 + 应用导入自检**

Run: `python -m pytest tests/test_admin_providers.py -q && python -c "from pix_web.main import create_app; print('app ok')"`
Expected: 测试全 PASS；`app ok`。

- [ ] **Step 6: Commit**

```bash
git add src/pix_web/routers/providers.py src/pix_web/main.py tests/test_admin_providers.py
git commit -m "feat(providers): admin CRUD router + presets endpoint"
```

---

## Task 7: 前端类型 + API 调用

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`

- [ ] **Step 1: 加 TS 类型（`types.ts`）**

```typescript
export interface ImageProviderModelPayload {
  id: string
  provider_model: string
  label: string
  protocol: string
  operations: string[]
  sizes: string[]
  qualities: string[]
  output_formats: string[]
  edit_mode: string
}

export interface ImageProvider {
  id: string
  display_name: string
  enabled: boolean
  base_url: string
  has_api_key: boolean
  api_key_env: string
  priority: number
  discover_models: boolean
  protocols: string[]
  models: ImageProviderModelPayload[]
  preset_key: string | null
}

export interface ImageProviderPreset {
  key: string
  display_name: string
  protocols: string[]
  base_url: string
  api_key_env: string
  discover_models: boolean
  models: ImageProviderModelPayload[]
  note: string
}

export interface ImageProviderCreatePayload {
  id: string
  display_name: string
  enabled: boolean
  base_url: string
  api_key: string
  api_key_env: string
  priority: number
  discover_models: boolean
  protocols: string[]
  models: ImageProviderModelPayload[]
  preset_key: string | null
}

export interface ImageProviderUpdatePayload {
  display_name: string
  enabled: boolean
  base_url: string
  api_key: string
  clear_api_key: boolean
  api_key_env: string
  priority: number
  discover_models: boolean
  protocols: string[]
  models: ImageProviderModelPayload[]
}
```

- [ ] **Step 2: 加 API 方法（`api.ts`，风格同 `adminAnnouncements`）**

```typescript
  adminProviders(token: string) {
    return request<ImageProvider[]>('/admin/providers', {}, token)
  },
  adminProviderPresets(token: string) {
    return request<ImageProviderPreset[]>('/admin/providers/presets', {}, token)
  },
  createAdminProvider(token: string, payload: ImageProviderCreatePayload) {
    return request<ImageProvider>('/admin/providers', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateAdminProvider(token: string, id: string, payload: ImageProviderUpdatePayload) {
    return request<ImageProvider>(`/admin/providers/${id}`, { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  deleteAdminProvider(token: string, id: string) {
    return request<{ deleted: boolean }>(`/admin/providers/${id}`, { method: 'DELETE' }, token)
  },
```

（在 `api.ts` 顶部 import 区补上新类型；若 `api.ts` 已 `import type { ... } from './types'`，把这些类型名加进去。）

- [ ] **Step 3: 类型检查**

Run: `cd apps/web && npm run build`（或项目约定的 typecheck，如 `npx tsc --noEmit`；先看 `apps/web/package.json` 的 scripts）
Expected: 编译通过（此时类型已被引用，无 unused 报错）。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts
git commit -m "feat(web): provider admin types + api client"
```

---

## Task 8: `useAdminActions` 供应商回调 + 装配

**Files:**
- Modify: `apps/web/src/hooks/useAdminActions.ts`
- Modify: `apps/web/src/pages/AdminPage.tsx`（若 props 在此装配；否则在调用 `AdminPanel` 的父层）

- [ ] **Step 1: 在 `useAdminActions` 加回调**（镜像 `createAnnouncement` 等）

```typescript
  const listProviders = useCallback(async () => {
    if (!token) return []
    return api.adminProviders(token)
  }, [token])

  const listProviderPresets = useCallback(async () => {
    if (!token) return []
    return api.adminProviderPresets(token)
  }, [token])

  const createProvider = useCallback(async (payload: ImageProviderCreatePayload) => {
    if (!token) return
    await api.createAdminProvider(token, payload)
    setMessage(text('供应商已新增', 'Provider created'))
  }, [token, setMessage, text])

  const updateProvider = useCallback(async (id: string, payload: ImageProviderUpdatePayload) => {
    if (!token) return
    await api.updateAdminProvider(token, id, payload)
    setMessage(text('供应商已更新', 'Provider updated'))
  }, [token, setMessage, text])

  const deleteProvider = useCallback(async (id: string) => {
    if (!token) return
    await api.deleteAdminProvider(token, id)
    setMessage(text('供应商已删除', 'Provider deleted'))
  }, [token, setMessage, text])
```

把这 5 个加入 hook 的 `return { ... }`。补上 `import type` 的新类型。

- [ ] **Step 2: 透传到 `AdminPanel`**

在装配 `AdminPanel` props 的位置（`AdminPage.tsx` 或其父），把 `listProviders / listProviderPresets / createProvider / updateProvider / deleteProvider` 传下去。

- [ ] **Step 3: 类型检查**

Run: `cd apps/web && npm run build`
Expected: 通过（新回调被 Task 9 引用前，先确保 hook 与装配处类型自洽；如暂时 unused 触发报错，可在 Task 9 完成后一并验证 —— 建议 Task 8/9 连续完成再跑 build）。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/hooks/useAdminActions.ts apps/web/src/pages/AdminPage.tsx
git commit -m "feat(web): admin provider CRUD actions + wiring"
```

---

## Task 9: `AdminPanel` 新标签 + `ProviderManager` 组件

**Files:**
- Modify: `apps/web/src/components/AdminPanel.tsx`

- [ ] **Step 1: `AdminPanel` props 增加供应商回调**

在 `Props` 类型加：

```typescript
  onListProviders?: () => Promise<ImageProvider[]>
  onListProviderPresets?: () => Promise<ImageProviderPreset[]>
  onCreateProvider?: (payload: ImageProviderCreatePayload) => Promise<void>
  onUpdateProvider?: (id: string, payload: ImageProviderUpdatePayload) => Promise<void>
  onDeleteProvider?: (id: string) => Promise<void>
```

并在 `AdminPanel({ ... })` 解构。补 import 类型。

- [ ] **Step 2: 加标签与渲染**

在 `<TabsTrigger value="packages">充值套餐</TabsTrigger>` 附近加：

```tsx
            <TabsTrigger value="providers">上游供应商</TabsTrigger>
```

在 `{tab === 'packages' && ...}` 附近加：

```tsx
        {tab === 'providers' && (
          <ProviderManager
            onList={onListProviders}
            onListPresets={onListProviderPresets}
            onCreate={onCreateProvider}
            onUpdate={onUpdateProvider}
            onDelete={onDeleteProvider}
          />
        )}
```

- [ ] **Step 3: 实现 `ProviderManager` 子组件**（镜像 `AnnouncementEditor` 的自加载列表 + 内联表单 + `useConfirm` 删除）

要点（完整实现照此结构写）：
- 用 `useState` 存 `providers: ImageProvider[]`、`presets: ImageProviderPreset[]`、`showForm`、`editing: ImageProvider | null`、表单字段（`id/display_name/base_url/apiKey/apiKeyEnv/priority/enabled/discoverModels/protocols/models`）、`presetKey`、`saving`、`notice`。
- `loadList()`（`useCallback` + `useEffect`）调用 `onList()` 填 `providers`；首次也调用 `onListPresets()` 填 `presets`（镜像 `AnnouncementEditor.loadList`，含「请求竞态保护 + 失败保留旧列表」）。
- **新增流程**：点「新增供应商」→ 弹出表单，顶部一个 `Select` 选预设；`onValueChange` 时用所选 `preset` 预填 `display_name/base_url/apiKey_env/protocols/models/discoverModels`，`id` 默认填 `preset.key`（可改）。选 `custom` 则清空可编辑。
- **编辑流程**：`startEdit(item)` 把行数据灌进表单，`id` 只读，`apiKey` 输入框留空且带「清空当前值」勾选（写入式更新：留空=保留，勾清空=置空）。Key 状态用 `item.has_api_key ? '已配置' : '未配置'` 展示。
- **保存**：组装 payload；新增走 `onCreate`，编辑走 `onUpdate(editing.id, { ..., api_key: apiKey, clear_api_key: clearKey })`；成功后 `await loadList()` 刷新、关表单。
- **删除**：`useConfirm()` 确认后 `onDelete(item.id)` → `loadList()`（镜像 `AnnouncementEditor.removeItem`）。
- **启停/优先级**：行内开关调用 `onUpdate(item.id, { ...当前值, enabled: !item.enabled })`；优先级用数字输入 + 保存，或在编辑表单里改。
- 列表每行展示：`display_name`（+`id`）、`protocols`（Badge）、`priority`、`enabled`（开关）、Key 状态、`preset_key || '自定义'` 来源；操作按钮：编辑 / 上线下线 / 删除。
- UI 控件全部复用 `./ui/`（`Button/Input/Select/Checkbox/Textarea/Badge/Alert`）与 `PixField`；可用 `./ui/dialog` 的 `Dialog` 承载表单，或像 `AnnouncementEditor` 一样用条件渲染的 `<form>`。
- `models` 编辑（自定义供应商）：最简实现用一个 `Textarea` 编辑 JSON（逻辑名/上游模型名/operations），保存时 `JSON.parse` 容错（解析失败给 `Alert` 提示）；预设供应商默认带 models，无需手填。

> 参考实现：`AnnouncementEditor`（列表+表单+删除）与 `PackageEditor`（create/update 回调）已在本文件，结构照搬即可。

- [ ] **Step 4: 类型检查 + 构建**

Run: `cd apps/web && npm run build`
Expected: 构建通过，无类型错误。

- [ ] **Step 5: 手动验证**（启动后端 + 前端，登录 admin）

参考项目 `run`/README 启动方式：后端 `uvicorn`（或 `scripts`）、前端 `npm run dev`。验证：
1. 后台出现「上游供应商」标签，列出种子导入的 packy/shengsuanyun/crazyrouter（视 `.env` 而定）。
2. 「新增供应商」选预设「胜算云」→ 填 Key → 保存 → 列表出现、Key 显示「已配置」。
3. 改优先级/启停/删除生效。
4. 不重启情况下发起一个生图任务，确认新供应商参与候选（看任务 `provider` 或日志）。

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/AdminPanel.tsx
git commit -m "feat(web): upstream provider management tab"
```

---

## Task 10: 同步文档 + 版本号

**Files:**
- Modify: `config.example.toml`、`.env.example`、`.env.production.example`、`README.md`、`CHANGELOG.md`、`pyproject.toml`、`__version__` 源

- [ ] **Step 1: 定位版本号源**

Run: `grep -rn "__version__" src/pix_web | head` 与 `grep -n "^version" pyproject.toml`
确认 `__version__` 定义位置（`main.py` 用到它）。

- [ ] **Step 2: 改版本 `1.75.0 → 1.76.0`**

`pyproject.toml` 的 `version = "1.76.0"`；同步 `__version__` 源。

- [ ] **Step 3: 配置/示例/文档**

- `config.example.toml`：在 `[[image_providers]]` 区块上方加注释：「供应商现以后台『上游供应商』管理为准；本段仅在数据库 `image_providers` 表为空时作为首次种子导入。」
- `.env.example` / `.env.production.example`：各家 KEY 处加注：「首次启动导入数据库后，以后台供应商管理为准；之后改这里不再影响已种子的供应商（除非清空 image_providers 表）。」
- `README.md`：新增「后台上游供应商管理」小节，写明：从预设新增/填 Key、编辑/删除/启停/调优先级、DB 为真相源、改完即时生效不重启、Key 写入式更新与遮罩、种子来源。
- `CHANGELOG.md`：在顶部加 `1.76.0` 条目（新增后台上游供应商统一管理）。
- 外部 API 文档（若有 docs 下的 API 说明文件）：补 `/admin/providers`、`/admin/providers/presets` 端点。

- [ ] **Step 4: 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add config.example.toml .env.example .env.production.example README.md CHANGELOG.md pyproject.toml src/pix_web
git commit -m "docs(providers): sync config/env/README/CHANGELOG + bump 1.76.0"
```

---

## 完成标准

- [ ] `python -m pytest tests/ -q` 全绿。
- [ ] `cd apps/web && npm run build` 通过。
- [ ] 后台「上游供应商」标签可列出/新增（预设+自定义）/编辑/删除/启停/调优先级。
- [ ] 新增供应商后**不重启**，下一个生图任务即纳入候选与故障切换。
- [ ] 种子幂等：空表导入现有 `.env`/`config.toml` 供应商；非空不重复。
- [ ] Key 遮罩 + 写入式更新（留空保留、勾清空置空）。
- [ ] 版本 `1.76.0`，配置/示例/README/CHANGELOG 已同步。
