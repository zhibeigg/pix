# Pix Web

Pix 是一个面向网站的像素素材生成服务：React 前端 + FastAPI 后端 + `src/pix` 素材生成核心。当前仓库只保留网站运行所需内容；历史 CLI、桌面 GUI、旧素材、测试与临时输出已移除。

## 仓库结构

```text
apps/web/                         # React/Vite 前端
apps/web/public/homepage-examples/ # 主页示例物品 icon 静态资源
migrations/                       # Alembic 数据库迁移
src/pix/                          # 网站后端依赖的素材生成核心
src/pix_web/                      # FastAPI API、worker、账号/计费/任务系统
assets/presets/                   # 像素化预设，后端运行时会读取
homepage示例物品icon清单.md        # 主页 608 个示例 icon 的维护清单
config.example.toml               # Pix 核心可选配置示例
.env.example                      # 本地后端环境变量示例
.env.production.example           # Docker/生产环境变量示例
Dockerfile / docker-compose.yml    # 后端镜像与整站编排
```

> 注意：Web 后端不仅依赖 `src/pix_web`，还依赖 `src/pix` 中的 `asset.py`、`pipeline.py`、`pixelize/*`、`grid/*`、`api/*`、`sprite_mosaic.py`（序列帧 pipeline）、`sprite.py`（序列帧通用工具与数据类）等核心代码。

## 本地开发

### 后端

```bash
py -m venv .venv
. .venv/Scripts/activate
pip install -e .
cp .env.example .env
pix-web-api
```

常用后端命令：

```bash
pix-web-api           # 启动 FastAPI 开发服务，默认 127.0.0.1:8000
pix-web-worker        # 数据库队列 worker
pix-web-rq-worker     # Redis/RQ worker
pix-web-check         # 后端配置/环境检查
```

### 前端

```bash
cd apps/web
npm install
npm run dev
```

主页「范例图鉴」包含物品图标、用户公开分享、真实上游实测样例、平铺纹理和序列帧五个展示区。用户在作品库公开成功作品后会进入「用户分享」tab，按点赞数排序展示；其他用户可直接下载公开产物、点赞并查看安全的生成参数快照。实测样例会展示本地真实流程生成的 Logo / 技能书结果，并在卡片和筛选器中标注使用的生成模型（如 `image2`、`gemini-3.1-flash-image-preview`），静态图片位于 `apps/web/public/homepage-examples/showcase/`。

前端构建：

```bash
cd apps/web
npm run build
```

## Docker 部署

1. 复制生产环境变量：

   ```bash
   cp .env.production.example .env.production
   ```

2. 修改 `.env.production` 中的数据库密码、JWT secret、生图 Provider API key（推荐 Crazyrouter，可保留 Packy fallback）、邮件与支付配置。
3. 启动：

   ```bash
   docker compose up --build
   ```

默认服务：

- `web`：Nginx 托管前端，默认宿主机 `8080`。
- `api`：FastAPI 后端。
- `worker`：RQ 生成任务 worker。
- `postgres` / `redis`：生产编排依赖。

## 关键环境变量

| 变量 | 用途 |
|---|---|
| `CRAZYROUTER_API_KEY` | 推荐的生图 Provider API key；当前生图模型选择收敛为 `image2`、`gemini-3.1-flash-image-preview`、`gemini-3-pro-image-preview`。 |
| `CRAZYROUTER_BASE_URL` | Crazyrouter API Base URL，默认 `https://crazyrouter.com`。 |
| `SHENGSUANYUN_API_KEY` | 胜算云（ShengSuanYun）生图 Provider API key，异步任务协议、承载 `image2`（上游 `openai/gpt-image-2`）；provider priority 第二（介于 Packy 与 Crazyrouter 之间），自动参与失败切换。 |
| `SHENGSUANYUN_BASE_URL` | 胜算云 API Base URL，默认 `https://router.shengsuanyun.com`。 |
| `PIX_IMAGE_DEFAULT_MODEL` | 默认 logical 生图模型，建议 `image2`；可选值仅为 `image2`、`gemini-3.1-flash-image-preview`、`gemini-3-pro-image-preview`。 |
| `PIX_IMAGE_PROVIDERS_JSON` | 可选：用 JSON 覆盖/补充多 Provider 配置，适合容器密钥管理场景。 |
| `PACKY_API_KEY` | Packy 老部署兼容 / 首次导入「上游供应商」种子 / fallback Provider 的生图 API key；新部署请优先在后台「上游供应商」配置。 |
| `PACKY_VL_API_KEY` | 视觉模型旧变量，老部署兼容 / 首次导入用，可与 `PACKY_API_KEY` 共用。 |
| `PACKY_BASE_URL` | Packy 旧 Base URL，老部署兼容 / 首次导入用，默认 `https://www.packyapi.com`。 |
| `PIX_WEB_DATABASE_URL` | 后端数据库连接。开发可用 SQLite，生产建议 PostgreSQL。 |
| `PIX_WEB_DB_POOL_SIZE` | PostgreSQL 连接池常驻连接数，默认 10（SQLite 忽略）。 |
| `PIX_WEB_DB_MAX_OVERFLOW` | 连接池允许的临时溢出连接数，默认 20；峰值连接上限 = size + overflow。 |
| `PIX_WEB_DB_POOL_TIMEOUT` | 取连接的最大等待秒数，默认 30；超时即报错而非无限堆积。 |
| `PIX_WEB_DB_POOL_RECYCLE` | 连接最大存活秒数，默认 1800，超过即回收，配合 pre_ping 防服务端空闲断连。 |
| `PIX_WEB_JWT_SECRET` | 登录 token 签名密钥，生产必须替换为长随机值。 |
| `PIX_WEB_STORAGE_ROOT` | 用户上传、生成结果和任务文件根目录，默认 `web_outputs`。 |
| `PIX_WEB_QUEUE_BACKEND` | `database` 或 `rq`。生产推荐 `rq`。 |
| `PIX_WEB_WORKER_CONCURRENCY` | Worker 并发任务数。 |
| `PIX_WEB_RUNNING_JOB_TIMEOUT_MINUTES` | running 任务自动清理阈值，默认 60 分钟；超时会标记失败并退款。 |
| `PIX_WEB_RUNNING_JOB_CLEANUP_INTERVAL_SECONDS` | Worker 扫描超时 running 任务的间隔，默认 60 秒。 |
| `PIX_WEB_REDIS_URL` | RQ/Redis 连接。 |
| `PIX_WEB_PIX_CONFIG` | 可选：让 Web worker 加载指定 `config.toml`。 |
| `PIX_WEB_PUBLIC_BASE_URL` | 后端公开 URL，例如 `https://example.com/api`；支付回调和链接推导会使用。 |
| `PIX_WEB_FRONTEND_BASE_URL` | 前端公开 URL；公告邮件按钮优先使用它，留空时从 `PIX_WEB_PUBLIC_BASE_URL` 推导。 |
| `PIX_WEB_CORS_ORIGINS` | 前后端不同源部署时填写允许的 Origin，多个用逗号分隔。 |
| `PIX_WEB_EMAIL_PROVIDER` | 邮件发送方式，开发可用 `console`，生产公告通知和验证码建议使用 `smtp`。 |
| `PIX_WEB_SMTP_HOST` / `PIX_WEB_SMTP_PORT` / `PIX_WEB_SMTP_FROM` | SMTP 投递配置；系统公告邮件和注册验证码共用。 |
| `PIX_WEB_TURNSTILE_ENABLED` | 是否启用 Cloudflare Turnstile 自适应反刷码；启用后仅同邮箱 / 同 IP 频繁请求验证码时触发，默认关闭。 |
| `PIX_WEB_TURNSTILE_SITE_KEY` | Turnstile Site Key，前端可见。 |
| `PIX_WEB_TURNSTILE_SECRET_KEY` | Turnstile Secret Key，仅后端校验使用，建议放密钥管理。 |
| `PIX_WEB_TURNSTILE_EMAIL_WINDOW_SECONDS` / `PIX_WEB_TURNSTILE_EMAIL_MAX_WITHOUT_CHALLENGE` | 同邮箱验证码请求触发 Turnstile 的统计窗口和免校验次数，默认 `3600` 秒 / `2` 次。 |
| `PIX_WEB_TURNSTILE_IP_WINDOW_SECONDS` / `PIX_WEB_TURNSTILE_IP_MAX_WITHOUT_CHALLENGE` | 同 IP 验证码请求触发 Turnstile 的统计窗口和免校验次数，默认 `3600` 秒 / `5` 次。 |

更多配置见 `.env.example`、`.env.production.example` 和 `config.example.toml`。

### 输入长度限制配置

后台「素材默认值」和「序列帧」现支持调整 Web 表单与外部 API 共用的描述长度限制：`pix.asset.subject_max_chars`、`pix.asset.extra_prompt_max_chars`、`pix.sprite.subject_max_chars`、`pix.sprite.row_prompt_max_chars`。同名字段也可写入 `config.toml` 的 `[asset]` / `[sprite]` 段。公开接口 `GET /settings/image-models` 与外部 API `GET /external/v1/models` 会在 `limits` 中返回当前生效值，前端据此显示字数计数、超限提示并禁用提交；后端创建任务、批量创建和失败重试也会按同一配置二次校验。

### 公开分享作品

作品库中的成功作品可点击「公开分享 +1 点」加入首页「用户分享」池。公开时后端会固化安全参数快照和下载清单，只展示用户可填写/选择的参数（提示词、素材类型、像素尺寸、颜色数、序列帧 FPS 等），不会公开邮箱、内部 `run_dir`、诊断信息、系统 prompt 或密钥。公开作品默认不会被普通作品库容量清理；用户手动删除作品时会同步将分享记录标记为 `deleted`，避免首页残留失效链接。

分享奖励由后台「作品分享」系统设置管理：`share.reward_enabled` 控制是否奖励，`share.reward_credits` 控制每个作品首次公开返还点数（默认 1），`share.daily_reward_limit` 控制每用户每日最多获得多少次分享奖励（0 表示不限制）。同一作品反复下架/重新公开不会重复返还。

公开分享 API：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/shares?limit=48&offset=0&asset_kind=item_icon` | 匿名可访问的公开作品列表，默认按点赞数、发布时间排序；带 Bearer token 时返回 `liked_by_me`。 |
| `POST` | `/shares/jobs/{job_id}/publish` | 当前用户公开自己的成功作品，首次公开按设置返还点数。 |
| `POST` | `/shares/{share_id}/unpublish` | 作者或管理员下架分享作品。 |
| `POST` / `DELETE` | `/shares/{share_id}/like` | 登录用户点赞 / 取消点赞，后端幂等维护 `like_count`。 |
| `GET` | `/shares/{share_id}/download/{kind}` | 根据公开时固化的下载清单下载文件，不暴露任意 `/files?path=`。 |

> 老部署注意：后台「模型与 API」已移除旧 Packy / Gemini / VL 密钥入口，供应商密钥统一迁移到「上游供应商」。升级前请阅读 [`docs/deployment/legacy-provider-settings-migration.md`](docs/deployment/legacy-provider-settings-migration.md)。

## 系统公告与邮件通知

管理员在后台「系统公告」面板发布启用的新公告时，后端会为当前所有 `active` 用户邮箱排队发送一封 HTML 卡片邮件。邮件会展示公告标题、正文、发布时间和“打开 Pix 网站”按钮；按钮链接优先读取 `PIX_WEB_FRONTEND_BASE_URL`，未配置时会从 `PIX_WEB_PUBLIC_BASE_URL` 去掉 `/api` 后推导。相同标题和正文重复保存不会再次群发，下线公告或保存草稿也不会发送邮件。

公告邮件复用注册验证码的邮件配置：开发环境 `PIX_WEB_EMAIL_PROVIDER=console` 时只写入日志；生产环境请配置 `smtp`、`PIX_WEB_SMTP_HOST`、`PIX_WEB_SMTP_FROM`、TLS/SSL 和认证信息。

## 网站素材生成流水线

当前 `job_type = asset` 的网站直出流程是单图素材流水线，不再使用旧的“逐图补 64×64 / 32×32 outline”静态流程。

实际步骤：

1. `build_asset_prompt` 根据用户主体、素材类型、尺寸、颜色数和抠色容差构建 prompt。
2. 本地 prompt guard 只审核用户原始输入，不把服务端模板暴露给审核模型；“直接复刻/抄袭参考图”类请求会在创建任务前拒绝，不入队、不冻结点数，并写入策略审计事件供后台统计。
3. 使用当前配置的 logical 生图模型生成单张源图；同一模型可由 Crazyrouter、Packy 等多个 Provider 承载并自动失败切换。普通素材上传参考图时仍走 `job_type=asset` 的素材直出链路（按图生图价格计费）：后端先要求模型把参考图理解 / 转译为 TRUE pixel-art，再套用素材模板中的尺寸、颜色数、纯色背景、禁文字等约束重绘，避免退化成简单处理上传图。
4. 默认 `skip_vl = true`，不走普通 VL 分析。
5. Pixel Grid extract：
   - `perfect_pixel` 网格对齐，并保存 `02_perfect_pixel_preprocess.png`；
   - `remove_background` 去背景；默认使用参考项目 `pixel_bg` 方法：边框中位数探测 key 色，按 `t_core/t_grow` 双阈值连通域生长生成背景 mask，去 key 色溢色并输出硬边二值 alpha；也可选择 `color_to_alpha`，按背景 key 色距离生成软 alpha，适合高清原图保留抗锯齿边；
   - 序列帧任务（mosaic 单图模式）：1 次 API 调用直接产出 rows×cols 网格 sprite sheet（rows/cols 各最大 8）。后端会先按 rows×cols 与目标帧尺寸自动计算适合的 API 渲染分辨率（不再继承通用 `image_gen.size=1024x1024`；例如 4×8、64×64 会渲染到 3072×1536，4×8、48×64 会渲染到 3072×2048，满足最大边 ≤3840、16 倍数、长短边比 ≤3:1、总像素 ≤8.3M 等约束），让每个像素艺术像素至少占 8×8 / 6×6 渲染像素。生成后按格切图（基于前景投影找最佳切分线，避免主体溢出邻列）+ 复用 `perfectPixel` + 显式 key 色的 pixel_bg 双阈值 alpha + 共享调色板等成熟后处理流程，最终输出横向 `sprite_sheet.png`（兼容预览）+ 原版 `sprite_mosaic.png`（保留 rows×cols 排版可下载）+ `sequence.json`。多行 mosaic（rows>1）会额外输出 `sprite_sheet_grid.png`（rows×cols 二维网格预览）以及 `row_sheets/row_NN.png` + `previews/row_NN.gif`（每行一张横向 sheet + 一个独立动画 GIF），让 4×8 行走表这种「每行一个动作」的素材直接拿到 4 个独立动画。提供「角色参考图」时切换到 `edit_image`，让每个 cell 复用同一角色设计。作品库可打开「调整」编辑器：逐帧拖动主体、滚轮缩放、查看上一帧半透明影子并实时预览，保存时仅本地重合成（含 fps 与每帧 offset/scale），不重新生图也不额外扣点；
   - `auto_crop` / tight bbox 贴主体裁剪；
   - `transparent_canvas_pad` 补到预设尺寸档；
   - sample cells / cluster palette；
   - 渲染最终 PNG 与 `.grid.json`。

> 参考图微调（`job_type=image_to_image` 且会进入像素化的任务，如作品库「AI 微调」）现在与素材直出共用同一套像素风 prompt：复用 `build_asset_prompt` + 参考图 appendix，把上传图当参考图、按 TRUE pixel-art 重绘（不再把用户原文直接发给模型），并声明上传图即「图1」，用户可在提示词用「图1」指代参考图（如「把图1重绘成像素风戏台」）。作品库「AI 微调」会沿用原作品的素材类型（物品图标 / UI 组件 / Logo / 平铺纹理）重绘，外部 API 也可在 `asset.asset_kind` 指定，缺省按物品图标处理。可用 `[image_gen].image_to_image_pixel_prompt = false` 回退原始 prompt 直传；`source_only` 的原生大图（参考图直出 1024 大图）不受影响。
>
> `job_type=local_bg_remove` 提供纯本地去背景，不调用 AI、不做像素化。`pixelize.bg_removal_algorithm="pixel_bg"` 对应前端「像素」算法（与像素直出当前抠色一致），`"color_to_alpha"` 对应「高清」算法（Color-to-Alpha 软边）。输出仍通过 `pixelized` 下载通道返回透明 PNG。

## 管理后台运营能力

管理后台「概览」展示今日任务、成功 / 失败、订单充值、今日消费、今日新增用户、DAU、今日付费用户、今日新订单、付费订单、上传量和失败诊断等核心运营指标。其中「订单充值」只汇总今日已支付订单的点数，不再把注册赠送或管理员补点计入充值数据；DAU 以今日注册、创建任务、上传或创建 / 支付订单的去重用户数统计。「今日新订单」按 `created_at` 统计（含未支付 `pending`），「付费订单」按 `paid_at` 只统计已支付，两者并列便于发现支付回调未到的订单。所有「今日」指标按**站点时区**（系统设置 `site.timezone`，默认 `Asia/Shanghai` = UTC+8）切分自然日，避免 UTC+8 用户凌晨—早 8 点的订单被算到前一天；概览在「概览」标签页每 30s 自动刷新，不再需要手动点「刷新」。

管理后台「用户与点数」支持单用户调整、当前用户列表多选、全选当前列表，以及通过 `POST /admin/users/adjust-credits-batch` 对全部 active 用户批量补点 / 扣点。批量操作会为每个目标用户写入独立 `adjustment` 点数流水，并在提交前显示目标范围、每人点数变化与备注，便于运营补偿或活动发放。

管理后台「价格折扣」可开启全局点数折扣：设置 `pricing.discount_enabled` 开关、`pricing.discount_rate` 倍率（0~1，如 0.8 = 8 折，0 = 限免）与可选 `pricing.discount_label` 促销文案。折扣只作用于生成任务（asset / 文生图 / 图生图 / 序列帧），按「先算总价再打折、向下取整、原价>0 保底 1 点」扣点，并在创建任务时锁定；作品库 / 素材包扩容不受影响。前端通过公开接口 `GET /pricing/discount`（返回 `{active, rate, label}`）展示原价划线 + 折后价 + 折扣标签。折扣实扣点数会写入任务计费快照（`billing.original_total_points` / `total_points` / `discount`）。

管理后台「任务与作品」支持按作品库视角查看最新全站任务：管理员可按状态、用户、任务 ID / prompt / 批次 / 用户邮箱筛选，并直接预览、下载任务产物；同页保留操作列表用于重试失败任务、取消排队 / 运行任务并退款、标记失败并退款。后端 `GET /admin/jobs?limit=500` 返回 `JobResponse[]`，其中 `user_id` 暴露任务归属，`outputs` 继续包含受保护文件 URL；管理员前端使用自己的登录 token 调用 `/files` 打开这些产物。

管理后台「性能监控」面板提供生图任务的实时可观测：成功率、活跃并发、任务量与成功率时间序列、提供商成功率对比、失败分类与最近任务流，可在 `1h / 24h / 7d` 范围间切换，前端每 8 秒轮询刷新。数据来自后端 `GET /admin/performance-metrics` 聚合接口；提供商成功率以后台已添加的 `image_providers` 为基准，优先读取任务 meta / diagnostics 中的 provider 尝试历史，因此 fallback 中前置失败供应商和最终成功供应商都会计入各自统计。

管理后台「上游供应商」面板统一管理生图上游：从内置预设（胜算云 / Packy / Crazyrouter / OpenAI / Midjourney / Ideogram / Fal / Kling）或「自定义（OpenAI 兼容）」一键新增供应商，填入 API Key 即可；支持编辑、删除、启停与调整 `priority`。供应商配置以数据库 `image_providers` 表为单一真相源（迁移 `0017`），后端 `GET/POST/PUT/DELETE /admin/providers` 提供增删改查、`GET /admin/providers/presets` 返回预设目录。首次启动会把 `config.toml` 的 `[[image_providers]]` 与 `.env` 各家 Key 导入数据库做种子；之后改动即时生效、无需重启（worker 每个任务都通过 `load_managed_pix_config` 重新加载有效配置并叠加数据库供应商）。API Key 写入后仅展示「已配置 / 未配置」状态、提交空值保持不变，与其它密钥设置一致。

## 对外 API

普通用户登录后可在网站「API」页面创建、停用或删除长期 API Key，并查看详细调用文档与 `curl` 示例。页面内置类似 sub2api 的令牌生成器：先在浏览器生成 `pix_live_` + 32 字节随机 hex 的候选令牌，提交创建后才生效；后端会校验格式与唯一性，数据库只保存 hash 与 prefix。API Key 明文只在创建成功时展示一次；列表页只展示名称、prefix、scope、创建时间、最后使用时间和撤销时间。外部程序使用 `Authorization: Bearer <api_key>` 调用 `/external/v1/...`，任务仍归属该 key 对应用户，并复用现有任务创建、扣点预留、队列入队、作品权限和文件下载逻辑。API 页面已覆盖认证、账号 / 余额 / 模型查询、上传参考图、素材直出、图生图、序列帧、轮询分页和下载输出等接入步骤。

`JobCreateRequest` 可选 `style_profile` 项目风格档案：`project_name`、`palette`、`line_style`、`lighting`、`view_rule`、`avoid_elements`。这些字段会由后端统一编译为 prompt 补充约束，用于素材直出、平铺纹理、双瓦片和序列帧；它不会替换像素尺寸、纯色背景、无缝瓦片或序列帧布局等硬约束。站内用户还可调用 `POST /jobs/prompt-preview` 在扣点前查看真实合成后的 prompt（外部 API 创建任务仍走 `/external/v1/jobs`）。

可分配的 scope：

- `jobs:create`：创建素材直出、文生图、图生图、本地像素化、本地去背景、重新像素化、序列帧等任务；
- `jobs:read`：查询自己的任务列表与任务详情；
- `files:read`：下载自己的任务输出或序列帧动作 zip；
- `uploads:create`：上传参考图 / 输入图，供后续任务 payload 使用。

常用调用示例：

```bash
# 创建任务（Idempotency-Key 可选；相同 key 会复用同一任务）
curl -X POST "https://example.com/api/external/v1/jobs" \
  -H "Authorization: Bearer pix_live_xxx" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: sword-001" \
  -d '{
    "job_type": "asset",
    "asset": {"name": "blue magic sword", "asset_kind": "item_icon"},
    "style_profile": {
      "project_name": "Crystal Dungeon",
      "palette": "cyan, violet, deep navy",
      "line_style": "thin bright outline",
      "avoid_elements": "modern guns, watermark, text"
    },
    "pixelize": {"output_size": [32, 32], "colors": 8, "remove_bg": true},
    "skip_vl": true
  }'

# 查询任务
curl "https://example.com/api/external/v1/jobs/{job_id}" \
  -H "Authorization: Bearer pix_live_xxx"

# 上传参考图 / 本地输入图
curl -X POST "https://example.com/api/external/v1/uploads" \
  -H "Authorization: Bearer pix_live_xxx" \
  -F "file=@reference.png"

# 创建本地去背景任务（algorithm: pixel_bg=像素；color_to_alpha=高清）
curl -X POST "https://example.com/api/external/v1/jobs" \
  -H "Authorization: Bearer pix_live_xxx" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: bg-remove-001" \
  -d '{
    "job_type": "local_bg_remove",
    "input_image_path": "把上传接口返回的 path 填在这里",
    "pixelize": {"remove_bg": true, "bg_removal_algorithm": "color_to_alpha"}
  }'

# 下载任务输出（kind 可用 final、source、sprite_sheet、sprite_mosaic、grid 等）
curl -L "https://example.com/api/external/v1/jobs/{job_id}/outputs/final" \
  -H "Authorization: Bearer pix_live_xxx" \
  -o output.png

# 下载多行动作序列帧 zip
curl -L "https://example.com/api/external/v1/jobs/{job_id}/sprite-actions.zip" \
  -H "Authorization: Bearer pix_live_xxx" \
  -o sprite-actions.zip
```

## 通用生图 Provider 调用规范

Pix 现在通过 logical model → provider candidates 的方式调用生图上游。前端和 `/settings/image-models` 只开放 3 个 logical model：`image2`、`gemini-3.1-flash-image-preview`、`gemini-3-pro-image-preview`；旧配置中的 `gpt-image-2` 会自动归一为 `image2`，但上游真实 `provider_model` 仍可保持 `gpt-image-2` / `openai/gpt-image-2`。同一个模型可以同时映射到多家 Provider，运行时按 `priority` 排序（默认 Packy=10 → 胜算云=20 → Crazyrouter=30）；网络错误、超时、429/5xx、空响应、响应结构异常、Provider 临时不可用、鉴权/余额类错误会自动切换下一家，直到没有其它可用 Provider。策略拦截、非法请求或不支持的模型/操作不会切换，避免浪费额度或绕过安全策略。普通用户只看到安全简短失败提示；管理员后台可查看脱敏后的 Provider 尝试历史、失败分类和 traceback。

OpenAI Images 兼容模型走 `/v1/images/generations` / `/v1/images/edits` 或 `image_input` payload；Midjourney、Kling 这类异步协议会提交任务后轮询查询端点；胜算云（`shengsuanyun` 协议）用 OpenAI gpt-image 兼容请求体走异步任务流程（`POST /api/v1/tasks/generations` 提交、`GET /api/v1/tasks/generations/{id}` 轮询，图生图复用同端点仅多传 `image` 字段，结果只返回图片 URL）；Ideogram/FAL 使用各自专用路径。默认优先要求返回 `b64_json` 并直接落盘；如果上游只返回临时 `url`，才作为兼容兜底下载。为控制上游成本，素材任务默认关闭多候选图；仅在后台或配置显式开启 `image_gen.contact_sheet_enabled` 时，才会按 `n_sample_count` 发起多候选请求。

候选 VL 评分未显式配置 `candidate_vl_ranking_model` 时固定使用 `claude-opus-4-8`，评分时直接以 multipart 文件上传候选图片给模型，不再把候选图编码成 chat `image_url` / 网格占位结构。`local_pixelize` 本地重处理会整体按生成图源图处理：重新走 perfect pixel、去背景、裁切等后处理，并在 perfect pixel 成功时采用自动检测出的真实像素尺寸，而不是强制沿用原任务的固定目标尺寸；前端本地像素化已移除尺寸选择器，统一按检测到的真实像素网格输出。`local_bg_remove` 则只做本地去背景，前端可在「像素 / 高清」间切换算法，分别映射到 `pixel_bg` 与 `color_to_alpha`。

模型能力会控制兼容参数：例如 `image2`（上游 `gpt-image-2`）当前不发送 `input_fidelity`，只有模型配置 `extra.supports_input_fidelity = true`（或内置判定支持）时图生图请求才会附带该字段，避免上游返回 `invalid_input_fidelity_model`。Crazyrouter 模型发现结果会继续经过 allowlist 过滤，只暴露 `image2` 与两个 Gemini Image Preview 模型；Doubao、Qwen、Midjourney、Ideogram、FAL、Kling 等模型不会再出现在生图下拉候选中。

前端通过 `GET /settings/image-models` 获取结构化模型能力：`models` 字符串数组保留给旧前端兼容，新前端读取 `items[]` 中的 `operations`、`sizes`、`qualities`、`providers` 和 `provider_count` 来决定模型列表、图生图入口和参数选项。

调试可视化阶段以 `fullflow-perfect-first-v2/step-preview-bg-first` 的顺序为准：

```text
01_source_raw.png
02_perfect_pixel_auto_detect.png
03_pixel_bg_remove_background.png
04_auto_crop_tight_bbox.png
05_rounded_transparent_canvas.png
06_final_grid_asset.png
```

这些 `outputs/` 调试产物不入库。

作品库卡片支持“参数”快览与“复用”：展开作品后可以查看任务提交时的 prompt、输入图、模型、像素化、素材直出、序列帧、计费快照和输出文件路径；快览里的完整 JSON 可一键复制，用于复现生成或排查问题；点击“复用”会回到生产工作台并自动填充原任务的提示词、素材 / 序列帧参数、像素尺寸、颜色数、模型与可复用参考图路径，适合长 prompt 快速再生成。

作品库支持“多选”批量操作：进入多选后可跨页勾选已完成作品、选择本页、清空选择，并通过一次确认批量删除。批量删除会同步移除素材包引用、清理输出文件并保留点数流水记录；生产中作品不可选择删除。

普通作品库默认保留最新 10 张未入素材包的成功作品；用户可在作品库中花费 60 点扩容 10 个保留格。保存进素材包的作品不占用普通作品库格子，仍按素材包规则长期保留。

## Prompt 构建规则

网站输入框只要求用户填写主体/描述，服务端再拼装完整素材 prompt。模板中的动态值必须来自用户或当前任务参数：

- `Canvas size must be exactly {width}x{height} pixels` 必须与用户实际选择的输出尺寸一致，例如 `16x16`、`32x32`、`64x64`。
- `{asset_kind_label}` / `{subject_kind_label}` / `{asset_usage_label}` / `{placement_context}` / `{forbidden_elements}` 由素材类型、主体类型选择自动填入；物品图标只出现物品/背包语义，UI 组件只出现界面组件语义，平铺纹理只出现无缝铺满语义，游戏 Logo 只出现标题页/菜单品牌标识语义，不能混写。
- `{max_colors}` / `{colors}` 使用用户实际选择的颜色数量上限，例如选择 8 色就写入 `no more than 8 visible subject colors`。
- `{key_tolerance}` 使用当前实际抠色最大色距容差，例如网站素材默认 48。
- 背景要求是“用于 chroma-key 移除的纯色背景”：模型须先确定主体完整调色板，再选一个与**主体所有可见颜色**的 RGB 欧氏距离中**最小值最大化**（maximin）的背景色，优先主体完全没用到的高饱和互补/对立色相；该最小距离须远大于抠色容差 `{key_tolerance}`，目标 ≥150 RGB 欧氏距离，避免背景与主体撞色或抠图误伤。不要固定写死为 `#FF00FF` 或任何单一 HEX。
- n-sample/contact-sheet 候选包装只引用完整 generation brief，不再额外写死 `inventory/UI use`；具体是物品还是 UI 只由 asset prompt 决定。

默认 asset 模板：

```text
Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} designed for {asset_usage_label}, not a painted digital illustration. Subject: {name}. Subject kind: {subject_kind_label}. Canvas size must be exactly {width}x{height} pixels, where each pixel is one square cell of a conceptual pixel grid — do NOT draw any visible grid lines, gridlines, graph-paper or checkerboard pattern. Use large, chunky readable pixels, limited colors, and a simple silhouette. Use no more than {max_colors} visible subject colors; background color does not count. For human characters, make sure the face is flat and no shadow. The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and {placement_context}. Fill the ENTIRE canvas edge to edge with one single flat uniform background color for chroma-key removal: the background must be perfectly solid with NO gradient, NO vignette, NO lighting or shading, NO drawn grid lines or graph paper, and NO border or frame; it must reach all four image edges. First decide the subject's full color palette, THEN choose the background color: pick a single flat color that MAXIMIZES the MINIMUM RGB Euclidean distance to EVERY visible subject color (a maximin choice), strongly preferring a saturated opposite or complementary hue that the subject does not use at all. This minimum distance must be far greater than the removal tolerance ({key_tolerance} RGB Euclidean distance), targeting at least 150 RGB Euclidean distance, so the background never blends with the subject and keys out cleanly. No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the conceptual pixel grid. The output image should be pixel-perfect, each cell only contains one color. {forbidden_elements}
```

### 物品图标（item_icon）

素材类型选择「物品图标」时，默认走 16×16 小图标直出，面向背包、掉落物、技能/道具栏等使用场景：

- 前端默认颜色数为 8 色，便于保持小尺寸图标的高识别度与统一色板。
- 默认开启透明背景，但不做额外边缘处理：`edge_style=hard`、`bg_feather=0`，不再自动添加 outline 描边。
- 如确实需要描边或羽化，可在「边缘处理」里手动切换。

### UI 组件（ui_component）

素材类型选择「UI 组件」时，前端单张与批量任务会显式提交 `image_size=auto`，后端也会对旧前端漏传尺寸的 UI 组件兜底为 `auto`：

- 目标像素尺寸仍由「像素尺寸」控制，默认 `32x32`，颜色数默认 12 色。
- 源图尺寸交给 Provider / 模型自动选择，避免复杂 UI 边框、面板或多空位布局被固定正方形源图过度裁切或留白。
- 默认开启透明背景并使用 `edge_style=outline`，方便把 UI 边框或面板叠到游戏界面中。

### 尺寸重试（size-match retry）

生产工作台的主体类素材直出（物品图标 / UI 组件 / Logo 等，平铺纹理与双瓦片除外）可选开启「尺寸重试」：每次尝试都会先按正常素材流程生成源图，再由 perfectPixel 检测真实像素网格，最后把像素成品**透明居中填充到最近的 2 的幂尺寸**（32 / 64 / 128 / 256 …）。尺寸重试比较的是这个填充后的最终 PNG 尺寸与用户在像素参数中选择的 `pixelize.output_size`，不再比较 AI 原始画布尺寸；原始生图页（`source_only=true`）不提供尺寸重试。

- 停止条件二选一：`size_retry_mode=attempts`（最大尝试次数，含首次，上限 `[image_gen].size_retry_max_attempts_limit`，默认 8）或 `size_retry_mode=credits`（最大点数预算，后端按单次单价折算成次数）。
- 交付与选择：所有尝试都会保留独立产物并写入 `image_gen.size_retry.attempts`，API 同时在 `JobOutputResponse.candidates` 暴露为可选候选。命中目标时交付第一张命中的尝试；耗尽仍未命中时交付最后一次尝试。作品库中点击任意尺寸重试尝试会直接切换当前卡片预览与下载目标，不再重新创建本地像素化任务；普通多候选图仍可按原流程进入本地像素化。
- 计费：开启时每次尝试按标准价 **6 折**（`[image_gen].size_retry_discount_rate`，默认 0.6）计费，并与全局促销折扣「取更优价」；下单按「单价 × 最大次数」预扣，任务成功后按**实际尝试次数**结算并退还差额。用户最终选择哪张候选不改变已发生尝试次数的计费。
- 成品填充：`[pixelize].pad_to_power_of_two = true`（默认）会在不缩放像素图的前提下透明填充到最近 2 的幂尺寸，并在 `pixelize.pad_to_power_of_two` 记录原始尺寸、最终尺寸与 offset。关闭该配置会禁用自动 2 幂填充，也会让尺寸重试更难命中目标。
- 自动失效（静默按普通任务计费，不打 6 折）：任务不是主体类素材生产流程、属于平铺纹理/双瓦片、处于多候选模式，或目标像素尺寸非法；前端会提示目标尺寸建议使用 2 的幂尺寸，以便与自动填充后的标准成品尺寸匹配。
- **尺寸约束 prompt 工程**：当 `image_size` 为具体 `WxH` 时，后端仍会把强制输出尺寸的指令（绝对像素 + 宽高比 + 画幅方向 + `no padding/border/crop/letterbox` 等负面约束，用「output image file resolution」措辞以免与像素风格的「pixel grid」语义冲突）追加到生图 prompt，提升模型一次出对源图尺寸的概率。该行为对所有有明确尺寸的生图生效，可用 `[image_gen].size_directive_enabled = false` 回退。
- 外部 API：`JobCreateRequest` 使用 `size_retry_enabled` / `size_retry_mode` / `size_retry_max_attempts` / `size_retry_max_credits`；`JobOutputResponse.size_retry` 返回实际尝试次数、是否命中、目标/最终尺寸和 attempts 明细，`JobOutputResponse.candidates` 会包含每次尝试的可访问图片 URL。

### 游戏 Logo（game_logo）

素材类型选择「游戏 Logo」时，仍走普通素材直出链路，输出适合标题页、主菜单、启动页或 HUD 品牌区使用的透明 PNG：

- 前端默认尺寸为 `128x64`，并提供 `64x32`、`96x48`、`128x64`、`192x96`、`256x128` 等宽幅快捷尺寸。
- 默认开启透明背景、使用 24 色、不额外描边，避免字形或徽标边缘被自动 outline 污染。
- Prompt 允许使用用户输入的短标题、缩写或品牌名，但禁止模型自造额外文字、段落、小字、水印、mockup 场景或无关边框。
- Logo 支持可选参考图：后端仍以 `asset_kind=game_logo` 走素材直出图生图链路，保留参考图的徽章轮廓、主色调和字形气质，但最终文字只使用用户输入的 Logo 标题 / 品牌名；带参考图时按图生图价格计费。

### 平铺纹理（tile_texture）

素材类型选择「平铺纹理」时，prompt 切到专用模板，**强制图案铺满整个画布、四边无缝拼接、不留透明背景**：

- 不再要求"主体居中 + 留白"，而是"every pixel of the {width}x{height} canvas is part of the texture"
- 不需要 chroma-key key color；后端 pipeline 也跳过抠透明、auto_crop、grid extract、共享调色板与 VL 评分
- 仅做完美像素对齐（perfect_pixel）后落盘，输出 `01_source.png`（生图原图）+ `03_pixelized.png`（按目标尺寸完美像素化的最终图）
- 价格规则等同 `asset` 任务（一次 API 一张图）

适合场景：地砖、木板、草地、墙面、地毯等需要在游戏地图里反复平铺的纹理素材。

平铺纹理还支持 `asset.texture_kind` 细分常见像素游戏纹理类型；默认值为 `auto`，后端会按主题关键词推断，最终结果会写入 `meta.json` 的 `requested_texture_kind` / `resolved_texture_kind`：

| texture_kind | 类型 | Prompt 规则重点 |
|---|---|---|
| `auto` | 自动识别 | 根据主题和额外风格描述推断具体类型；未命中时回退通用纹理。 |
| `generic_texture` | 通用纹理 | 均匀可重复的地图材质，避免地标、徽章、主体物、水平线和明显中心。 |
| `terrain_ground` | 地表 / 地形 | 俯视 RPG 地表；草叶、泥点、砂砾、雪粒、苔藓等自然噪声均匀分布，避免树、石堆、墙面或道路边界。 |
| `path_floor` | 道路 / 地砖 | 俯视可行走路面；石板、砖缝、地砖、裂缝需跨边缘对齐，避免墙、门、地毯边框或中心徽章。 |
| `wall_surface` | 墙壁 / 岩壁 | 正面墙体或岩壁；统一左上光照、砖块/裂缝/岩层连续，避免地面透视、天空、窗门和完整建筑立面。 |
| `wood_planks` | 木板 / 树皮 | 木纹、节疤、裂缝和木板缝连续跨边；避免桌子、箱子、牌匾、画框或单根原木主体。 |
| `water_liquid` | 水面 / 液体 | 可做动画底帧的液体表面；小波纹、高光、泡沫、发光流线跨边连续，避免岸线、岛、船和瀑布。 |
| `foliage_canopy` | 树叶 / 草丛 | 连续树冠、灌木或草丛覆盖层；叶团和枝隙密集分布，避免树干、花束、单株植物图标和透明洞。 |
| `roof_tile` | 屋顶瓦片 | 瓦片、木瓦、茅草屋顶等重复行；行偏移跨边对齐，避免烟囱、天窗、屋顶轮廓或房屋剪影。 |
| `metal_panel` | 金属面板 | 工业/科幻面板；面板缝、铆钉、螺丝、划痕、通风口跨边对齐，避免可读文字、Logo、屏幕和单个机器部件。 |
| `fabric_carpet` | 布料 / 地毯 | 织物纹理、线迹、小纹样或几何重复跨边，避免外边框、流苏、中央大徽章、可读符号和布料物件轮廓。 |

### 双瓦片（dual_grid）

素材类型选择「双瓦片」（`asset_kind=dual_grid`）时，一次任务产出一**套**可无缝拼接的过渡瓦片，表达两种地形 A/B 的交界（草地↔泥土、草地↔水/空等），地图引擎按经典 dual-grid 规则即可自动平滑过渡。Web 前端入口位于「单张试做 → 游戏素材直出 → 素材类型：双瓦片」，可填写材质 A/B、A/B 纹理类型和过渡风格。后端先用 `tile_texture` 生图链路生成两张四边无缝材质 A、B，再用 16 个角掩码**确定性合成** 16 张瓦片拼成 4×4 图集 —— 无缝性由「边不变量」构造保证，而非交给模型直出整张图集。

字段写在 `asset` 块里：

- `material_a`（str，必填非空）：材质 A 描述（主体地形）。
- `material_b`（str，始终提供）：材质 B 描述；空串或 `"transparent"` 即**透明模式**（B 区透明，做地块孤岛 / 边缘），不报「缺失」错。
- `material_a_texture_kind` / `material_b_texture_kind`（默认 `auto`）：A / B 的纹理细分，复用上表 `tile_texture` 的 `texture_kind` 枚举；`asset` 现有的单数 `texture_kind` 在 dual_grid 下忽略。
- `transition_style`（`rounded` | `hard` | `outline`，默认 `rounded`）：A/B 交界画法。`rounded` 圆角过渡（最地道）、`hard` 象限硬边、`outline` 在 A 侧内缩 1px 描边（描边色取材质 A 最暗可见色）。**默认在所有模式下都为 `rounded`（含透明模式）；透明模式想给孤岛加 1px 防裸边描边时显式传 `outline`。**
- `pixelize.output_size` = **单张瓦片**尺寸，图集为其 4×4 排布（`4W × 4H`）；`pixelize.colors` 限色作用于材质。

JSON 示例：

```json
{
  "job_type": "asset",
  "asset": {
    "name": "草地泥土过渡",
    "asset_kind": "dual_grid",
    "material_a": "草地",
    "material_b": "泥土",
    "transition_style": "rounded"
  },
  "pixelize": { "output_size": [32, 32], "colors": 12 }
}
```

图集采用 `pix-dualgrid-v1` 约定：4×4 行优先排布，角位 `TL=bit0, TR=bit1, BL=bit2, BR=bit3`、地形 `A=1/B=0`、`idx = row*4 + col`。产物为 `dual_grid_atlas.png`（4×4 图集）、`dual_grid_preview.png`（确定性种子的应用预览）、`materials/material_a.png`(+`material_b.png`) 与含 `convention` / `mapping`（bitmask→cell 表）/ `preview_seed` 的 `meta.json`；外部 API 的 `JobOutputResponse` 额外暴露 `dual_grid_atlas_path/url`、`dual_grid_preview_path/url`。详细字段、bitmask→cell 映射表与引擎用法见 [`docs/dual-grid-rules.md`](docs/dual-grid-rules.md)。

默认 sprite 模板使用 `mosaic_prompt_template` / `mosaic_reference_prompt_template`：1 次 API 调用产出 rows×cols 整张 sheet（`rows × cols ≤ 64`），prompt 中包含 `Layout by Row` 段落 + 行级动作描述 + 整图尺寸契约。后端会为 sprite mosaic 独立选择 API 渲染尺寸，而不是复用通用 `image_gen.size`；内部先按 `target_frame_size × rows×cols × 8` 估算理想渲染画布，再按 API 约束（最大边 ≤3840、16 倍数、长短边比 ≤3:1、总像素 655,360—8,294,400）缩放到合法尺寸。fallback prompt 还会显式告诉模型每个 cell 的 render pixel 尺寸、真实可绘像素网格与 pixel-art 像素块大小（`render_width/render_height/cell_render_width/cell_render_height/upscale/cell_art_width/cell_art_height/anchor_text` 占位符），并要求主体按自然比例锚定单元格指定锚点、上方留白填背景键色，减少低分辨率生成造成的 perfectPixel 检测漂移。其中 `cell_art_width/cell_art_height = cell_render ÷ upscale` 始终与块大小自洽：横排方形帧（如 64×64 的 1×8）被 API ≤3:1 约束撑成竖长单元格（384×1024）时，不会再出现「单元格尺寸 vs 帧尺寸」自相矛盾、模型瞎猜帧高的问题。竖长主体（如站立角色）按「内容多高、帧就多高」自适应输出（如 64×128），`meta.json` / `sequence.json` 用 `delivered_frame_size` / `frame_size_adapted` 显式标注实际交付帧尺寸（不再是隐性 mismatch）。提供参考图时自动套用 `mosaic_reference_prompt_template`，让每个 cell 复用同一角色设计。后端单帧后处理链路为「切分每一帧 → perfect pixel → 显式 key_rgb 的 pixel_bg 双阈值 alpha → alpha bbox 裁剪 → 共享调色板统一限色 → 每帧可选描边/羽化（复用 pixelize 的 `edge_style`/`bg_feather`，描边前补透明边距、不会被自适应画布裁掉；前端「边缘处理」选项对序列帧已解禁）」，不再复用全局 Color-to-Alpha，也不会从 cell 四角重新采样背景色，避免多行 mosaic 中主体越界 cell 边界时四角采样到主体色而抠不干净。最终保留原版 `sprite_mosaic.png` + 横向 `sprite_sheet.png`，多行模式额外输出 `sprite_sheet_grid.png` + `row_sheets/` + `previews/`，作品库预览组件读 `sprite_sheet.png + sequence.json` 逐帧播放。多动作作品在作品库卡片选中某个动作后，「下载图片」可选「当前动作图」（该行 `row_sheets/row_NN.png`）或「所有动作打包」（后端 `GET /jobs/{job_id}/sprite-actions.zip` 把每行各一张横向图打包），文件统一命名 `{作品名}_action{NN}_{动作名}.png`。切图时还会用前景投影自动检测实际网格行 / 列数，纠正模型「少画 / 多画一行一列」导致的空帧 / 错位。

作品库支持「调整」编辑器：前端用 Canvas 叠加上一帧/闭环帧半透明影子，用户可拖动每帧主体、用滚轮缩放当前帧主体（绕帧中心），保存时本地重合成 alignment 版本（含 fps、每帧 offset 与 scale），不重新调用 AI，不额外扣点。序列帧作品不再提供「重新像素化」或「AI 微调」入口，避免把整张 sprite sheet 当普通单图再次处理；如需改帧位置使用「调整」，如需导出使用下载。

`sprite_sheet` 价格规则表示「单帧基础价」：总价 = `ceil(rows·cols / 9) × 单帧基础价`（如 8×8 = 40 点，1×8 = 5 点）。

## 主页示例 icon 维护规则

- `homepage示例物品icon清单.md` 必须保留，它是 76 个题材 × 8 个物品的维护清单。
- 主页展示读取 `apps/web/public/homepage-examples/items/*.png` 中的最终 PNG。
- 尺寸 tag 应来自最终 PNG 的真实宽高；不要把清单里的 `64x64` 当成最终固定尺寸。
- 右键某个主页 icon 时，只复制主体 prompt 片段，例如“物品名 + 题材单个道具 + 可识别造型/材质特征”，不复制整组 prompt、尺寸或旧 64/32 说明。
- 新增或重生成主页素材时，必须走上方网站素材生成流水线；生成模型返回图进入本地处理后，第一步必须是 perfect pixel 预处理，然后再做 key 色抠图、裁剪、采样和调色板聚类。
- 主页示例 icon 默认不做额外边缘处理：`edge_style=hard`、`bg_feather=0`，不要使用 `outline` 描边或 `feather` 羽化。

## 前端 SEO

前端是 React/Vite 客户端渲染单页应用，公开收录重点集中在首页。`apps/web/index.html` 维护搜索引擎可直接读取的标题、描述、Open Graph、Twitter Card、JSON-LD 结构化数据与 `<noscript>` 首屏兜底文案；`apps/web/public/robots.txt` 和 `apps/web/public/sitemap.xml` 使用生产域名 `https://www.mcwar.cn/`。

静态 SEO 资源说明：

- `apps/web/public/og-image.png`：1200×630 社交分享图，供 Open Graph / Twitter Card 使用。
- `apps/web/public/404.html`：独立静态 404 兜底页，供静态托管平台在真实路径不存在时直接返回，视觉与 React 内置 404 保持一致。
- `apps/web/public/site.webmanifest`、`icon-192.png`、`icon-512.png`、`apple-touch-icon.png`：PWA 与移动端图标。
- `apps/web/src/lib/seo.ts`：前端路由与语言切换时同步更新 `document.title`、`description` 和分享 meta。由于当前使用 hash 路由，登录后的工作台/作品库等内页不写入 sitemap；若后续希望内页收录，需要预渲染或 SSR。

## 版本与发布

当前版本：`1.86.1`。

版本号格式为 `A.B.C`：

- `A`：公开接口不兼容变更；
- `B`：功能更新；
- `C`：Bug 修复、兼容性修复。

完整变更记录见 `CHANGELOG.md`。
