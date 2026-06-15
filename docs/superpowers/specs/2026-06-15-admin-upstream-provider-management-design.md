# 后台上游供应商统一管理 — 设计文档

- 日期：2026-06-15
- 状态：已与用户确认设计，准备进入实现计划
- 建议分支：`feat/admin-provider-management`
- 版本号：`1.75.0 → 1.76.0`（B 位：新增功能）

## 1. 背景与目标

Pix 通过 `logical model → provider candidates` 调用多个生图上游，按 `priority` 自动失败切换
（详见 `src/pix/api/image_dispatcher.py:dispatch_image_request`，已实现）。但**上游供应商的配置
本身散在三处、后台无法统一管理**：

- `.env`：各家 API Key（`CRAZYROUTER_API_KEY`、`SHENGSUANYUN_API_KEY`、`PACKY_API_KEY` …）。
- `config.toml` 的 `[[image_providers]]`：provider 的 `id`/`base_url`/`priority`/`protocols`/`models`。
- 数据库 `system_settings` 表：仅有零散的旧 Packy 参数（`pix.api.image_api_key` 等）。

后台「模型与 API」标签页只能改旧 Packy key 和通用超时/重试，**既看不到全部供应商，也不能新增供应商**
（`src/pix_web/routers/admin.py` 无任何 `/providers` 增删改查）。新增/调整供应商必须改文件并重启。

**目标**：后台提供「上游供应商」统一管理页——查看所有供应商、从预设目录单独新增、编辑/删除/启停/调
优先级，**改完即时生效、不重启**，并把三处分散配置收敛为以数据库为单一真相源。

## 2. 已确认的设计决策

| 决策点 | 结论 |
|---|---|
| 配置真相源 | **数据库为准**。新建 `image_providers` 表；首次启动把现有 `config.toml` + `.env` 的供应商导入做种子；之后一切以 DB 为准。 |
| 新增体验 | **预设目录为主 + 自定义兜底**。内置已支持供应商预设，选一个自动带出协议/base_url/推荐模型，只填 Key 即可；另含「自定义（OpenAI 兼容）」入口接其它上游。 |
| 模型管理 | **预设自带推荐模型**；自定义供应商可勾「自动发现」（复用 `discover_models`）或手填简单清单（逻辑名 / 上游模型名 / 支持操作）。不做逐模型 sizes/qualities 重型编辑。 |
| 密钥存储 | **沿用项目现有 secret 约定**：明文入库 + API 响应遮罩 + 写入式更新（提交空=不改），与 SMTP/支付宝密钥一致。不引入加密层。 |
| 热更新 | 复用 `load_managed_pix_config` 的 per-job/per-request 加载路径，DB 改动下一个任务即生效，**无需缓存失效、无需重启**。 |

## 3. 数据模型 — 新表 `image_providers`

单表 + JSON 列，贴合现有 `ImageProviderConfig` dataclass，注入路径也与现成的
`_apply_providers_json` 一致。新增 Alembic 迁移 `0017_image_providers.py`（接 `0016_job_provider`）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | String(64) PK | 供应商唯一标识（如 `shengsuanyun`） |
| `display_name` | String(128) | 显示名 |
| `enabled` | Boolean default true | 启用开关 |
| `base_url` | Text | 上游 API 基址 |
| `api_key` | Text default "" | 凭证（明文入库，响应遮罩，写入式更新） |
| `api_key_env` | String(96) default "" | 可选：环境变量名，`api_key` 为空时回退读取 |
| `priority` | Integer default 100 | 故障切换顺序，越小越先 |
| `protocols` | JSON（list[str]） | 支持的协议；必须是 `_PROVIDER_BY_PROTOCOL` 已知协议 |
| `discover_models` | Boolean default false | 是否运行时自动发现模型 |
| `models` | JSON（list[dict]） | 模型清单，每项见下 |
| `preset_key` | String(64) nullable | 来自哪个预设（自定义为 null） |
| `created_at` / `updated_at` | DateTime(tz) | `onupdate=utcnow` |

`models` 列每项的简单 schema（其余字段按协议给默认）：

```json
{ "id": "gpt-image-2", "provider_model": "openai/gpt-image-2",
  "protocol": "shengsuanyun", "operations": ["text_to_image", "image_to_image"] }
```

> 不拆 models 子表（YAGNI）：不需要按模型做关系查询，JSON 列够用且注入更简单。

SQLAlchemy 模型加在 `src/pix_web/models.py`（与 `SystemSetting` 同风格）。

## 4. 配置注入 & 热更新（核心）

**关键支点（已核实）**：`process_job()` 每个任务都 fresh 调用
`cfg = load_managed_pix_config(db, settings)`（`src/pix_web/worker.py:81`），生图设置路由
（`src/pix_web/routers/settings.py:47`）同理。只要让该函数把 DB 供应商叠进 `AppConfig`，
**每个新任务自动读到最新供应商 → 改完即时生效，无需任何缓存失效或重启**。

实现：

- 新增 `image_providers_from_db(db) -> list[ImageProviderConfig]`（放 `src/pix_web/system_settings.py`
  或新模块 `src/pix_web/provider_store.py`）：读 `image_providers` 表 → 转 provider 配置列表（含 models）。
- 扩展 `load_managed_pix_config(db, settings)`：`load_config()` 返回的 base cfg 里，
  `_normalize_image_providers`（`src/pix/config.py`）**已把 `.env` 派生的 crazyrouter/shengsuanyun/packy
  追加进 `cfg.image_providers` 了**。因此当 DB 有供应商时，**整体替换（清空后重设）`cfg.image_providers`**，
  而不是用 `_set_or_append_provider` 往已填充的列表里追加（否则会与 env 注入项重复/冲突）；替换后按
  `priority` 排序。`_apply_providers_json` 仅作「如何把 dict 转 provider 配置」的实现参考。
- **Key 解析**：无需新写回退逻辑——dispatch 层现成的 `provider_api_key`（`src/pix/api/image_model_registry.py:62`）
  已实现「`api_key` 优先、为空回退 `api_key_env` 环境变量」。只需把 `api_key`（可选 `api_key_env`）
  原样存进 provider 配置，运行时回退即生效（保留「用环境变量管 Key」的工作流，便于平滑迁移）。

## 5. 首次启动种子迁移

- 新增 `ensure_seeded_image_providers(db)`，在 `init_db()`（`src/pix_web/db.py`，已集中调用
  `ensure_default_pricing`/`ensure_default_system_settings`/`ensure_default_packages`，且被
  `main.py` 与 `worker.py` 共同调用）里追加调用一次。**幂等**：仅当表为空时执行。
- 注意：`init_db` 的这些 `ensure_default_*` 仅在 `create_schema=settings.auto_create_db` 时运行；
  纯 Alembic 迁移部署（`auto_create_db=False`）会跳过自动种子——与现有所有 `ensure_default_*` 行为一致，
  此时由首次在后台保存或迁移脚本补齐（保持项目约定）。
- 种子来源：直接调用现成的 `load_config(config_file=settings.pix_config_file)`——它已把
  `config.toml` 的 `[[image_providers]]` + `.env` 的 KEY 注入合并好。把合并后的
  `cfg.image_providers`（含已解析的 `api_key`）逐条写入 DB。
- 并发安全：`id` 为主键，按「不存在才插入」处理（捕获 `IntegrityError`），Web/Worker 同时启动不会重复种子。
- 迁移后语义：DB 为准；之后 `.env`/`config.toml` 的供应商定义将被 DB 覆盖（**这是 DB-为准的明确取舍**，
  文档说明：如需重新从文件导入，清空该表即可）。旧 `system_settings` 里的 Packy 字段保留兼容、不删。

## 6. 预设目录（「可选现在支持的供应商」）

- 静态常量 `PROVIDER_PRESETS`（新模块 `src/pix_web/provider_presets.py`），每条：
  `{ key, display_name, protocols, base_url 默认, api_key_env 提示, 推荐 models[], 说明 }`。
- 覆盖：**胜算云 / Packy / Crazyrouter / OpenAI / Midjourney / Ideogram / Fal / Kling**
  + 一条 **「自定义（OpenAI 兼容）」**（`protocols=["openai_images"]`，base_url/models 留空手填）。
- `GET /admin/providers/presets` 返回目录 → 前端「新增」弹窗渲染下拉 → 选中预填表单 → `POST` 落库。
- 预设取值与现有 `config.example.toml`、`src/pix/config.py` 内的 env 注入函数保持一致（同一组默认）。

## 7. 模型管理

- 预设带推荐 models，开箱即用。
- 自定义供应商两种方式（二选一或都填）：
  - 勾「自动发现模型」→ provider 的 `discover_models=true`，运行时由 `discover_provider_models(cfg, provider)`
    （`src/pix/api/image_model_registry.py`）拉取；**还需全局 `pix.image_gen.model_discovery_enabled` 打开
    才生效**（需上游支持模型列表端点）。
  - 手填简单清单：逻辑名 / 上游模型名 / 勾选 operations（text_to_image、image_to_image）。
- 其余字段（sizes/qualities/output_formats/edit_mode）按 `protocol` 给默认，不在 UI 暴露。

## 8. 后端 API（新增 `src/pix_web/routers/providers.py`，挂现有 admin 鉴权）

| 方法 | 路由 | 说明 |
|---|---|---|
| GET | `/admin/providers` | 列表（`api_key` 遮罩为「已配置/未配置」状态） |
| GET | `/admin/providers/presets` | 预设目录 |
| POST | `/admin/providers` | 新增（校验 `id` 唯一、协议白名单、base_url 非空、priority 为整数） |
| PUT | `/admin/providers/{id}` | 修改（含 enabled/priority/models；`api_key` 提交空=保留原值，沿用 secret 写入式语义） |
| DELETE | `/admin/providers/{id}` | 删除 |

- Pydantic schema 加在 `src/pix_web/schemas.py`；响应模型对 `api_key` 只回状态不回明文。
- 校验失败返回 422，与 `system_settings.update_system_setting` 风格一致。

## 9. 前端后台页面

- `apps/web/src/components/AdminPanel.tsx` 新增「上游供应商」标签：
  - 列表：名称 / 协议 / 优先级 / 启用开关 / Key 状态 / 来源（预设或自定义）。
  - 行内操作：启停、调优先级、编辑、删除。
  - 「新增供应商」弹窗：先选预设（或自定义）→ 表单预填 → 填 Key → 保存。
- 旧「模型与 API」标签里的 Packy key 字段保留，但加注「已迁移到上游供应商管理」。
- 新增前端 API 调用封装（与现有 admin settings 调用同处）。

## 10. 密钥安全

沿用项目现有 secret 约定（SMTP 密码、支付宝密钥同此）：**DB 存明文 + API 响应遮罩 + 写入式更新
（提交空=不改）**。不新引入加密层，以与全项目其它密钥一致。种子迁移会把 `.env` 里已解析的 Key
写入 DB（明文），这是 DB-为准的既定取舍。

## 11. 数据流

```
后台「新增供应商」
  └─ GET /admin/providers/presets → 选预设 → 预填
  └─ POST /admin/providers → 写入 image_providers 表
                                 │
生图任务 process_job(db, job)     │ (下一个任务，无需重启)
  └─ load_managed_pix_config(db) ─┘
        ├─ load_config(file+env)               # base
        ├─ image_providers_from_db(db) 替换 cfg.image_providers
        └─ 按 priority 排序
  └─ dispatch_image_request(cfg, ...) 按候选 + 失败切换调用上游
```

## 12. 错误处理 & 边界

- 新增重复 `id` → 422「供应商已存在」。
- 协议不在 `_PROVIDER_BY_PROTOCOL` 白名单 → 422。
- 删除当前默认模型唯一可用供应商 → 允许删除，但任务届时会得到现有
  `unsupported_model`/`provider_unavailable` 错误（不在本功能内做额外保护，保持与现状一致）。
- DB 表为空（理论上种子后不会）→ `load_managed_pix_config` 退回 base cfg 的 file/env 供应商（兜底）。
- 并发种子 → `IntegrityError` 吞掉（幂等）。

## 13. 同步更新（遵循 CLAUDE.md「新增功能必须同步更新配置/示例/README/语言/外部 API 文档」）

- `config.example.toml`：补充说明「供应商现以后台管理为准，`[[image_providers]]` 仅作首次种子」。
- `.env.example` / `.env.production.example`：保留各家 KEY，注明「首次启动导入数据库后以后台为准」。
- `README.md`：新增「后台上游供应商管理」章节（新增/编辑/优先级/即时生效说明）。
- 语言文件 / 前端文案：新标签与弹窗的中文文案。
- 外部 API 文档：新增 `/admin/providers*` 端点说明。
- `pyproject.toml`：版本 `1.76.0`；`CHANGELOG.md`：新增条目。

## 14. 验证策略（pytest，镜像 `tests/test_image_providers.py` 与 `tests/test_admin_batch_credits.py`）

- 单测：
  - 种子迁移：空表 → 从 `load_config()` 导入；非空表 → 不重复种子（幂等）。
  - 注入：DB 有供应商时 `load_managed_pix_config` 用 DB 替换 `cfg.image_providers` 并按 priority 排序。
  - Key 解析：`api_key` 优先；为空且 `api_key_env` 命中时回退环境变量。
  - 写入式更新：PUT 提交空 `api_key` 保留原值；提交新值覆盖。
  - 预设实例化：选预设 + 填 Key → 落库后字段正确。
  - API 校验：重复 id / 未知协议 / 空 base_url 返回 422。
- 集成：新增一个供应商后，`dispatch_image_request` 能把它纳入候选并参与故障切换。

## 15. 不做（YAGNI）

- 不拆 models 子表、不做逐模型全参数 UI。
- 不做按用户/分组的供应商路由。
- 不做供应商级用量计费（已有 `generation_jobs.provider` 历史记录）。
- 不引入密钥加密层（与现有约定保持一致）。
- 不删除旧 `system_settings` 的 Packy 兼容字段（保留兜底）。
