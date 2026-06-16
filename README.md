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
| `CRAZYROUTER_API_KEY` | 推荐的生图 Provider API key；支持 GPT Image、Qwen、Doubao、Nano Banana、Midjourney、Ideogram、Kling/FAL 等多协议模型。 |
| `CRAZYROUTER_BASE_URL` | Crazyrouter API Base URL，默认 `https://crazyrouter.com`。 |
| `SHENGSUANYUN_API_KEY` | 胜算云（ShengSuanYun）生图 Provider API key，异步任务协议、承载 `gpt-image-2`；provider priority 第二（介于 Packy 与 Crazyrouter 之间），自动参与失败切换。 |
| `SHENGSUANYUN_BASE_URL` | 胜算云 API Base URL，默认 `https://router.shengsuanyun.com`。 |
| `PIX_IMAGE_DEFAULT_MODEL` | 默认 logical 生图模型，例如 `gpt-image-2`。 |
| `PIX_IMAGE_PROVIDERS_JSON` | 可选：用 JSON 覆盖/补充多 Provider 配置，适合容器密钥管理场景。 |
| `PACKY_API_KEY` | Packy 兼容旧部署 / fallback Provider 的生图 API key，需支持 `gpt-image-2`。 |
| `PACKY_VL_API_KEY` | 视觉模型 API key，可与 `PACKY_API_KEY` 共用。 |
| `PACKY_BASE_URL` | Packy API Base URL，默认 `https://www.packyapi.com`。 |
| `PIX_WEB_DATABASE_URL` | 后端数据库连接。开发可用 SQLite，生产建议 PostgreSQL。 |
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
| `PIX_WEB_TURNSTILE_ENABLED` | 是否在注册发送验证码前要求 Cloudflare Turnstile 校验，默认关闭。 |
| `PIX_WEB_TURNSTILE_SITE_KEY` | Turnstile Site Key，前端可见。 |
| `PIX_WEB_TURNSTILE_SECRET_KEY` | Turnstile Secret Key，仅后端校验使用，建议放密钥管理。 |

更多配置见 `.env.example`、`.env.production.example` 和 `config.example.toml`。

## 系统公告与邮件通知

管理员在后台「系统公告」面板发布启用的新公告时，后端会为当前所有 `active` 用户邮箱排队发送一封 HTML 卡片邮件。邮件会展示公告标题、正文、发布时间和“打开 Pix 网站”按钮；按钮链接优先读取 `PIX_WEB_FRONTEND_BASE_URL`，未配置时会从 `PIX_WEB_PUBLIC_BASE_URL` 去掉 `/api` 后推导。相同标题和正文重复保存不会再次群发，下线公告或保存草稿也不会发送邮件。

公告邮件复用注册验证码的邮件配置：开发环境 `PIX_WEB_EMAIL_PROVIDER=console` 时只写入日志；生产环境请配置 `smtp`、`PIX_WEB_SMTP_HOST`、`PIX_WEB_SMTP_FROM`、TLS/SSL 和认证信息。

## 网站素材生成流水线

当前 `job_type = asset` 的网站直出流程是单图素材流水线，不再使用旧的“逐图补 64×64 / 32×32 outline”静态流程。

实际步骤：

1. `build_asset_prompt` 根据用户主体、素材类型、尺寸、颜色数和抠色容差构建 prompt。
2. 本地 prompt guard 只审核用户原始输入，不把服务端模板暴露给审核模型；“直接复刻/抄袭参考图”类请求会在创建任务前拒绝，不入队、不冻结点数，并写入策略审计事件供后台统计。
3. 使用当前配置的 logical 生图模型生成单张源图；同一模型可由 Crazyrouter、Packy 等多个 Provider 承载并自动失败切换。
4. 默认 `skip_vl = true`，不走普通 VL 分析。
5. Pixel Grid extract：
   - `perfect_pixel` 网格对齐，并保存 `02_perfect_pixel_preprocess.png`；
   - `remove_background` 去背景；默认使用参考项目 `pixel_bg` 方法：边框中位数探测 key 色，按 `t_core/t_grow` 双阈值连通域生长生成背景 mask，去 key 色溢色并输出硬边二值 alpha；
   - 序列帧任务（mosaic 单图模式）：1 次 API 调用直接产出 rows×cols 网格 sprite sheet（rows/cols 各最大 8）。后端会先按 rows×cols 与目标帧尺寸自动计算适合的 API 渲染分辨率（不再继承通用 `image_gen.size=1024x1024`；例如 4×8、64×64 会渲染到 3072×1536，4×8、48×64 会渲染到 3072×2048，满足最大边 ≤3840、16 倍数、长短边比 ≤3:1、总像素 ≤8.3M 等约束），让每个像素艺术像素至少占 8×8 / 6×6 渲染像素。生成后按格切图（基于前景投影找最佳切分线，避免主体溢出邻列）+ 复用 `perfectPixel` + 显式 key 色的 pixel_bg 双阈值 alpha + 共享调色板等成熟后处理流程，最终输出横向 `sprite_sheet.png`（兼容预览）+ 原版 `sprite_mosaic.png`（保留 rows×cols 排版可下载）+ `sequence.json`。多行 mosaic（rows>1）会额外输出 `sprite_sheet_grid.png`（rows×cols 二维网格预览）以及 `row_sheets/row_NN.png` + `previews/row_NN.gif`（每行一张横向 sheet + 一个独立动画 GIF），让 4×8 行走表这种「每行一个动作」的素材直接拿到 4 个独立动画。提供「角色参考图」时切换到 `edit_image`，让每个 cell 复用同一角色设计。作品库可打开「调整」编辑器：逐帧拖动主体、滚轮缩放、查看上一帧半透明影子并实时预览，保存时仅本地重合成（含 fps 与每帧 offset/scale），不重新生图也不额外扣点；
   - `auto_crop` / tight bbox 贴主体裁剪；
   - `transparent_canvas_pad` 补到预设尺寸档；
   - sample cells / cluster palette；
   - 渲染最终 PNG 与 `.grid.json`。

## 管理后台运营能力

管理后台「用户与点数」支持单用户调整、当前用户列表多选、全选当前列表，以及通过 `POST /admin/users/adjust-credits-batch` 对全部 active 用户批量补点 / 扣点。批量操作会为每个目标用户写入独立 `adjustment` 点数流水，并在提交前显示目标范围、每人点数变化与备注，便于运营补偿或活动发放。

管理后台「任务与作品」支持按作品库视角查看最新全站任务：管理员可按状态、用户、任务 ID / prompt / 批次 / 用户邮箱筛选，并直接预览、下载任务产物；同页保留操作列表用于重试失败任务、取消排队 / 运行任务并退款、标记失败并退款。后端 `GET /admin/jobs?limit=500` 返回 `JobResponse[]`，其中 `user_id` 暴露任务归属，`outputs` 继续包含受保护文件 URL；管理员前端使用自己的登录 token 调用 `/files` 打开这些产物。

管理后台「性能监控」面板提供生图任务的实时可观测：成功率、活跃并发、任务量与成功率时间序列、各 provider（胜算云 / Packy / Crazyrouter）成功率对比、失败分类与最近任务流，可在 `1h / 24h / 7d` 范围间切换，前端每 8 秒轮询刷新。数据来自后端 `GET /admin/performance-metrics` 聚合接口；`generation_jobs.provider` 列（迁移 `0016`）由 worker 在任务落库时写入最终生效 provider，因此 provider 维度只覆盖该列上线后的新任务，历史任务归入「未知」。

管理后台「上游供应商」面板统一管理生图上游：从内置预设（胜算云 / Packy / Crazyrouter / OpenAI / Midjourney / Ideogram / Fal / Kling）或「自定义（OpenAI 兼容）」一键新增供应商，填入 API Key 即可；支持编辑、删除、启停与调整 `priority`。供应商配置以数据库 `image_providers` 表为单一真相源（迁移 `0017`），后端 `GET/POST/PUT/DELETE /admin/providers` 提供增删改查、`GET /admin/providers/presets` 返回预设目录。首次启动会把 `config.toml` 的 `[[image_providers]]` 与 `.env` 各家 Key 导入数据库做种子；之后改动即时生效、无需重启（worker 每个任务都通过 `load_managed_pix_config` 重新加载有效配置并叠加数据库供应商）。API Key 写入后仅展示「已配置 / 未配置」状态、提交空值保持不变，与其它密钥设置一致。

## 通用生图 Provider 调用规范

Pix 现在通过 logical model → provider candidates 的方式调用生图上游。默认可配置 Packy、胜算云（ShengSuanYun）与 Crazyrouter 三类 Provider：同一个模型（如 `gpt-image-2`）可以同时映射到多家 Provider，运行时按 `priority` 排序（默认 Packy=10 → 胜算云=20 → Crazyrouter=30）；网络错误、超时、429/5xx、空响应、响应结构异常、Provider 临时不可用、鉴权/余额类错误会按 `image_gen.failover_on` 自动切换下一家。

OpenAI Images 兼容模型走 `/v1/images/generations` / `/v1/images/edits` 或 `image_input` payload；Midjourney、Kling 这类异步协议会提交任务后轮询查询端点；胜算云（`shengsuanyun` 协议）用 OpenAI gpt-image 兼容请求体走异步任务流程（`POST /api/v1/tasks/generations` 提交、`GET /api/v1/tasks/generations/{id}` 轮询，图生图复用同端点仅多传 `image` 字段，结果只返回图片 URL）；Ideogram/FAL 使用各自专用路径。默认优先要求返回 `b64_json` 并直接落盘；如果上游只返回临时 `url`，才作为兼容兜底下载。为控制上游成本，素材任务默认关闭多候选图；仅在后台或配置显式开启 `image_gen.contact_sheet_enabled` 时，才会按 `n_sample_count` 发起多候选请求。

候选 VL 评分未显式配置 `candidate_vl_ranking_model` 时固定使用 `claude-opus-4-8`，评分时直接以 multipart 文件上传候选图片给模型，不再把候选图编码成 chat `image_url` / 网格占位结构。`local_pixelize` 本地重处理会整体按生成图源图处理：重新走 perfect pixel、去背景、裁切等后处理，并在 perfect pixel 成功时采用自动检测出的真实像素尺寸，而不是强制沿用原任务的固定目标尺寸。

模型能力会控制兼容参数：例如 `gpt-image-2` 当前不发送 `input_fidelity`，只有模型配置 `extra.supports_input_fidelity = true`（或内置判定支持）时图生图请求才会附带该字段，避免上游返回 `invalid_input_fidelity_model`。Crazyrouter 模型发现只会把明确可推断为图片能力的模型暴露给生图；普通文本模型（如 Doubao Lite 32K）不会再误入序列帧 / 生图候选。

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

作品库卡片支持“参数”快览：展开作品后可以查看任务提交时的 prompt、输入图、模型、像素化、素材直出、序列帧、计费快照和输出文件路径；快览里的完整 JSON 可一键复制，用于复现生成或排查问题。

普通作品库默认保留最新 10 张未入素材包的成功作品；用户可在作品库中花费 60 点扩容 10 个保留格。保存进素材包的作品不占用普通作品库格子，仍按素材包规则长期保留。

## Prompt 构建规则

网站输入框只要求用户填写主体/描述，服务端再拼装完整素材 prompt。模板中的动态值必须来自用户或当前任务参数：

- `Canvas size must be exactly {width}x{height} pixels` 必须与用户实际选择的输出尺寸一致，例如 `16x16`、`32x32`、`64x64`。
- `{asset_kind_label}` / `{subject_kind_label}` / `{asset_usage_label}` / `{placement_context}` / `{forbidden_elements}` 由素材类型、主体类型选择自动填入；物品图标只出现物品/背包语义，UI 组件只出现界面组件语义，平铺纹理只出现无缝铺满语义，游戏 Logo 只出现标题页/菜单品牌标识语义，不能混写。
- `{max_colors}` / `{colors}` 使用用户实际选择的颜色数量上限，例如选择 8 色就写入 `no more than 8 visible subject colors`。
- `{key_tolerance}` 使用当前实际抠色最大色距容差，例如网站素材默认 48。
- 背景要求是“用于 chroma-key 移除的纯色背景，并与主体所有可见颜色保持足够色距”，不要固定写死为 `#FF00FF` 或任何单一 HEX。
- n-sample/contact-sheet 候选包装只引用完整 generation brief，不再额外写死 `inventory/UI use`；具体是物品还是 UI 只由 asset prompt 决定。

默认 asset 模板：

```text
Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} designed for {asset_usage_label}, not a painted digital illustration. Subject: {name}. Subject kind: {subject_kind_label}. Canvas size must be exactly {width}x{height} pixels, where each pixel is one square grid cell. Use large, chunky readable pixels, limited colors, and a simple silhouette. Use no more than {max_colors} visible subject colors; background color does not count. For human characters, make sure the face is flat and no shadow. The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and {placement_context}. Use a pure solid single-color background for chroma-key removal; choose a background color that is not close to any visible subject color, with color-distance greater than the removal tolerance ({key_tolerance} RGB Euclidean distance). No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. The output image should be pixel-perfect, each grid cell only contains one color. {forbidden_elements}
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

默认 sprite 模板使用 `mosaic_prompt_template` / `mosaic_reference_prompt_template`：1 次 API 调用产出 rows×cols 整张 sheet（`rows × cols ≤ 64`），prompt 中包含 `Layout by Row` 段落 + 行级动作描述 + 整图尺寸契约。后端会为 sprite mosaic 独立选择 API 渲染尺寸，而不是复用通用 `image_gen.size`；内部先按 `target_frame_size × rows×cols × 8` 估算理想渲染画布，再按 API 约束（最大边 ≤3840、16 倍数、长短边比 ≤3:1、总像素 655,360—8,294,400）缩放到合法尺寸。fallback prompt 还会显式告诉模型每个 cell 的 render pixel 尺寸与 pixel-art 像素块大小（`render_width/render_height/cell_render_width/cell_render_height/upscale` 占位符），减少低分辨率生成造成的 perfectPixel 检测漂移。提供参考图时自动套用 `mosaic_reference_prompt_template`，让每个 cell 复用同一角色设计。后端单帧后处理链路固定为「切分每一帧 → perfect pixel → 显式 key_rgb 的 pixel_bg 双阈值 alpha → alpha bbox 裁剪」，不再复用全局 Color-to-Alpha，也不会从 cell 四角重新采样背景色，避免多行 mosaic 中主体越界 cell 边界时四角采样到主体色而抠不干净。最终保留原版 `sprite_mosaic.png` + 横向 `sprite_sheet.png`，多行模式额外输出 `sprite_sheet_grid.png` + `row_sheets/` + `previews/`，作品库预览组件读 `sprite_sheet.png + sequence.json` 逐帧播放。多动作作品在作品库卡片选中某个动作后，「下载图片」可选「当前动作图」（该行 `row_sheets/row_NN.png`）或「所有动作打包」（后端 `GET /jobs/{job_id}/sprite-actions.zip` 把每行各一张横向图打包），文件统一命名 `{作品名}_action{NN}_{动作名}.png`。切图时还会用前景投影自动检测实际网格行 / 列数，纠正模型「少画 / 多画一行一列」导致的空帧 / 错位。

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

当前版本：`1.73.0`。

版本号格式为 `A.B.C`：

- `A`：公开接口不兼容变更；
- `B`：功能更新；
- `C`：Bug 修复、兼容性修复。

完整变更记录见 `CHANGELOG.md`。
