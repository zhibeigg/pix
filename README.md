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

2. 修改 `.env.production` 中的数据库密码、JWT secret、Packy API key、邮件与支付配置。
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
| `PACKY_API_KEY` | 生图 API key，需支持 `gpt-image-2`。 |
| `PACKY_VL_API_KEY` | 视觉模型 API key，可与 `PACKY_API_KEY` 共用。 |
| `PACKY_BASE_URL` | Packy API Base URL，默认 `https://www.packyapi.com`。 |
| `PIX_WEB_DATABASE_URL` | 后端数据库连接。开发可用 SQLite，生产建议 PostgreSQL。 |
| `PIX_WEB_JWT_SECRET` | 登录 token 签名密钥，生产必须替换为长随机值。 |
| `PIX_WEB_STORAGE_ROOT` | 用户上传、生成结果和任务文件根目录，默认 `web_outputs`。 |
| `PIX_WEB_QUEUE_BACKEND` | `database` 或 `rq`。生产推荐 `rq`。 |
| `PIX_WEB_REDIS_URL` | RQ/Redis 连接。 |
| `PIX_WEB_PIX_CONFIG` | 可选：让 Web worker 加载指定 `config.toml`。 |
| `PIX_WEB_CORS_ORIGINS` | 前后端不同源部署时填写允许的 Origin，多个用逗号分隔。 |
| `PIX_WEB_TURNSTILE_ENABLED` | 是否在注册发送验证码前要求 Cloudflare Turnstile 校验，默认关闭。 |
| `PIX_WEB_TURNSTILE_SITE_KEY` | Turnstile Site Key，前端可见。 |
| `PIX_WEB_TURNSTILE_SECRET_KEY` | Turnstile Secret Key，仅后端校验使用，建议放密钥管理。 |

更多配置见 `.env.example`、`.env.production.example` 和 `config.example.toml`。

## 网站素材生成流水线

当前 `job_type = asset` 的网站直出流程是单图素材流水线，不再使用旧的“逐图补 64×64 / 32×32 outline”静态流程。

实际步骤：

1. `build_asset_prompt` 根据用户主体、素材类型、尺寸、颜色数和抠色容差构建 prompt。
2. 本地 prompt guard 只审核用户原始输入，不把服务端模板暴露给审核模型。
3. 使用 `gpt-image-2` 生成单张源图。
4. 默认 `skip_vl = true`，不走普通 VL 分析。
5. Pixel Grid extract：
   - `perfect_pixel` 网格对齐，并保存 `02_perfect_pixel_preprocess.png`；
   - `remove_background` 去背景；默认固定使用四角纯色作为 key 的 GIMP Color-to-Alpha 风格算法，不再回退 flood-fill；
   - 序列帧任务（mosaic 单图模式）：1 次 API 调用直接产出 rows×cols 网格 sprite sheet（rows/cols 各最大 8）。后端会先按 rows×cols 与目标帧尺寸自动计算适合的 API 渲染分辨率（不再继承通用 `image_gen.size=1024x1024`；例如 4×8、64×64 会渲染到 3072×1536，4×8、48×64 会渲染到 3072×2048，满足最大边 ≤3840、16 倍数、长短边比 ≤3:1、总像素 ≤8.3M 等约束），让每个像素艺术像素至少占 8×8 / 6×6 渲染像素。生成后按格切图（基于前景投影找最佳切分线，避免主体溢出邻列）+ 复用 `perfectPixel` + Color-to-Alpha + 共享调色板等成熟后处理流程，最终输出横向 `sprite_sheet.png`（兼容预览）+ 原版 `sprite_mosaic.png`（保留 rows×cols 排版可下载）+ `sequence.json`。多行 mosaic（rows>1）会额外输出 `sprite_sheet_grid.png`（rows×cols 二维网格预览）以及 `row_sheets/row_NN.png` + `previews/row_NN.gif`（每行一张横向 sheet + 一个独立动画 GIF），让 4×8 行走表这种「每行一个动作」的素材直接拿到 4 个独立动画。提供「角色参考图」时切换到 `edit_image`，让每个 cell 复用同一角色设计。作品库可打开「调整」编辑器：逐帧拖动主体、滚轮缩放、查看上一帧半透明影子并实时预览，保存时仅本地重合成（含 fps 与每帧 offset/scale），不重新生图也不额外扣点；
   - `auto_crop` / tight bbox 贴主体裁剪；
   - `transparent_canvas_pad` 补到预设尺寸档；
   - sample cells / cluster palette；
   - 渲染最终 PNG 与 `.grid.json`。

调试可视化阶段以 `fullflow-perfect-first-v2/step-preview-bg-first` 的顺序为准：

```text
01_source_raw.png
02_perfect_pixel_auto_detect.png
03_color_to_alpha_remove_background.png
04_auto_crop_tight_bbox.png
05_rounded_transparent_canvas.png
06_final_grid_asset.png
```

这些 `outputs/` 调试产物不入库。

作品库卡片支持“参数”快览：展开作品后可以查看任务提交时的 prompt、输入图、模型、像素化、素材直出、序列帧、计费快照和输出文件路径；快览里的完整 JSON 可一键复制，用于复现生成或排查问题。

## Prompt 构建规则

网站输入框只要求用户填写主体/描述，服务端再拼装完整素材 prompt。模板中的动态值必须来自用户或当前任务参数：

- `Canvas size must be exactly {width}x{height} pixels` 必须与用户实际选择的输出尺寸一致，例如 `16x16`、`32x32`、`64x64`。
- `{asset_kind_label}` / `{subject_kind_label}` / `{asset_usage_label}` / `{placement_context}` / `{forbidden_elements}` 由素材类型、主体类型选择自动填入；物品图标只出现物品/背包语义，UI 组件只出现界面组件语义，不能混写。
- `{max_colors}` / `{colors}` 使用用户实际选择的颜色数量上限，例如选择 12 色就写入 `no more than 12 visible subject colors`。
- `{key_tolerance}` 使用当前实际抠色最大色距容差，例如网站素材默认 48。
- 背景要求是“用于 chroma-key 移除的纯色背景，并与主体所有可见颜色保持足够色距”，不要固定写死为 `#FF00FF` 或任何单一 HEX。
- n-sample/contact-sheet 候选包装只引用完整 generation brief，不再额外写死 `inventory/UI use`；具体是物品还是 UI 只由 asset prompt 决定。

默认 asset 模板：

```text
Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} designed for {asset_usage_label}, not a painted digital illustration. Subject: {name}. Subject kind: {subject_kind_label}. Canvas size must be exactly {width}x{height} pixels, where each pixel is one square grid cell. Use large, chunky readable pixels, limited colors, and a simple silhouette. Use no more than {max_colors} visible subject colors; background color does not count. For human characters, make sure the face is flat and no shadow. The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and {placement_context}. Use a pure solid single-color background for chroma-key removal; choose a background color that is not close to any visible subject color, with color-distance greater than the removal tolerance ({key_tolerance} RGB Euclidean distance). No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. The output image should be pixel-perfect, each grid cell only contains one color. {forbidden_elements}
```

### 平铺纹理（tile_texture）

素材类型选择「平铺纹理」时，prompt 切到专用模板，**强制图案铺满整个画布、四边无缝拼接、不留透明背景**：

- 不再要求"主体居中 + 留白"，而是"every pixel of the {width}x{height} canvas is part of the texture"
- 不需要 chroma-key key color；后端 pipeline 也跳过抠透明、auto_crop、grid extract、共享调色板与 VL 评分
- 仅做完美像素对齐（perfect_pixel）后落盘，输出 `01_source.png`（生图原图）+ `03_pixelized.png`（按目标尺寸完美像素化的最终图）
- 价格规则等同 `asset` 任务（一次 API 一张图）

适合场景：地砖、木板、草地、墙面、地毯等需要在游戏地图里反复平铺的纹理素材。

默认 sprite 模板使用 `mosaic_prompt_template` / `mosaic_reference_prompt_template`：1 次 API 调用产出 rows×cols 整张 sheet（`rows × cols ≤ 64`），prompt 中包含 `Layout by Row` 段落 + 行级动作描述 + 整图尺寸契约。后端会为 sprite mosaic 独立选择 API 渲染尺寸，而不是复用通用 `image_gen.size`；内部先按 `target_frame_size × rows×cols × 8` 估算理想渲染画布，再按 API 约束（最大边 ≤3840、16 倍数、长短边比 ≤3:1、总像素 655,360—8,294,400）缩放到合法尺寸。fallback prompt 还会显式告诉模型每个 cell 的 render pixel 尺寸与 pixel-art 像素块大小（`render_width/render_height/cell_render_width/cell_render_height/upscale` 占位符），减少低分辨率生成造成的 perfectPixel 检测漂移。提供参考图时自动套用 `mosaic_reference_prompt_template`，让每个 cell 复用同一角色设计。后端单帧后处理链路固定为「切分每一帧 → perfect pixel → 显式 key_rgb 的 Color-to-Alpha → alpha bbox 裁剪」，不再复用带距离阈值硬抠/halo 清理的 icon 路径，也不会从 cell 四角重新采样背景色，避免多行 mosaic 中主体越界 cell 边界时四角采样到主体色而抠不干净。最终保留原版 `sprite_mosaic.png` + 横向 `sprite_sheet.png`，多行模式额外输出 `sprite_sheet_grid.png` + `row_sheets/` + `previews/`，作品库预览组件读 `sprite_sheet.png + sequence.json` 逐帧播放。

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
- `apps/web/public/site.webmanifest`、`icon-192.png`、`icon-512.png`、`apple-touch-icon.png`：PWA 与移动端图标。
- `apps/web/src/lib/seo.ts`：前端路由与语言切换时同步更新 `document.title`、`description` 和分享 meta。由于当前使用 hash 路由，登录后的工作台/作品库等内页不写入 sitemap；若后续希望内页收录，需要预渲染或 SSR。

## 版本与发布

当前版本：`1.57.1`。

版本号格式为 `A.B.C`：

- `A`：公开接口不兼容变更；
- `B`：功能更新；
- `C`：Bug 修复、兼容性修复。

完整变更记录见 `CHANGELOG.md`。
