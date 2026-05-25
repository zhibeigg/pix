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

> 注意：Web 后端不仅依赖 `src/pix_web`，还依赖 `src/pix` 中的 `asset.py`、`pipeline.py`、`pixelize/*`、`grid/*`、`api/*`、`sprite.py` 等核心代码。

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

更多配置见 `.env.example`、`.env.production.example` 和 `config.example.toml`。

## 网站素材生成流水线

当前 `job_type = asset` 的网站直出流程是单图素材流水线，不再使用旧的“逐图补 64×64 / 32×32 outline”静态流程。

实际步骤：

1. `build_asset_prompt` 根据用户主体、素材类型、尺寸、颜色数和抠色容差构建 prompt。
2. 本地 prompt guard 只审核用户原始输入，不把服务端模板暴露给审核模型。
3. 使用 `gpt-image-2` 生成单张源图。
4. 默认 `skip_vl = true`，不走普通 VL 分析。
5. Pixel Grid extract：
   - `perfect_pixel` 网格对齐；
   - `remove_background` 去背景；
   - `auto_crop` / tight bbox 贴主体裁剪；
   - `transparent_canvas_pad` 补到预设尺寸档；
   - sample cells / cluster palette；
   - 渲染最终 PNG 与 `.grid.json`。

调试可视化阶段以 `fullflow-perfect-first-v2/step-preview-bg-first` 的顺序为准：

```text
01_source_raw.png
02_perfect_pixel_auto_detect.png
03_remove_background.png
04_auto_crop_tight_bbox.png
05_rounded_transparent_canvas.png
06_final_grid_asset.png
```

这些 `outputs/` 调试产物不入库。

## Prompt 构建规则

网站输入框只要求用户填写主体/描述，服务端再拼装完整素材 prompt。模板中的动态值必须来自用户或当前任务参数：

- `Canvas size must be exactly {width}x{height} pixels` 必须与用户实际选择的输出尺寸一致，例如 `16x16`、`32x32`、`64x64`。
- `{asset_kind_label}` / `{subject_kind_label}` / `{asset_usage_label}` / `{placement_context}` / `{forbidden_elements}` 由素材类型、主体类型选择自动填入；物品图标只出现物品/背包语义，UI 组件只出现界面组件语义，不能混写。
- `{max_colors}` / `{colors}` 使用用户实际选择的颜色数量上限，例如选择 12 色就写入 `no more than 12 visible subject colors`。
- `{key_tolerance}` 使用当前实际抠色最大色距容差，例如网站素材默认 48。
- 背景要求是“用于 chroma-key 移除的纯色背景，并与主体所有可见颜色保持足够色距”，不要固定写死为 `#FF00FF` 或任何单一 HEX。
- n-sample/contact-sheet 候选包装只引用完整 generation brief，不再额外写死 `inventory/UI use`；具体是物品还是 UI 只由 asset prompt 决定。

默认模板：

```text
Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} designed for {asset_usage_label}, not a painted digital illustration. Subject: {name}. Subject kind: {subject_kind_label}. Canvas size must be exactly {width}x{height} pixels, where each pixel is one square grid cell. Use large, chunky readable pixels, limited colors, and a simple silhouette. Use no more than {max_colors} visible subject colors; background color does not count. For human characters, make sure the face is flat and no shadow. The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and {placement_context}. Use a pure solid single-color background for chroma-key removal; choose a background color that is not close to any visible subject color, with color-distance greater than the removal tolerance ({key_tolerance} RGB Euclidean distance). No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. The output image should be pixel-perfect, each grid cell only contains one color. {forbidden_elements}
```

## 主页示例 icon 维护规则

- `homepage示例物品icon清单.md` 必须保留，它是 76 个题材 × 8 个物品的维护清单。
- 主页展示读取 `apps/web/public/homepage-examples/items/*.png` 中的最终 PNG。
- 尺寸 tag 应来自最终 PNG 的真实宽高；不要把清单里的 `64x64` 当成最终固定尺寸。
- 右键某个主页 icon 时，只复制主体 prompt 片段，例如“物品名 + 题材单个道具 + 可识别造型/材质特征”，不复制整组 prompt、尺寸或旧 64/32 说明。
- 新增或重生成主页素材时，必须走上方网站素材生成流水线。
- 主页示例 icon 默认不做额外边缘处理：`edge_style=hard`、`bg_feather=0`，不要使用 `outline` 描边或 `feather` 羽化。

## 版本与发布

当前版本：`1.40.113`。

版本号格式为 `A.B.C`：

- `A`：公开接口不兼容变更；
- `B`：功能更新；
- `C`：Bug 修复、兼容性修复。

完整变更记录见 `CHANGELOG.md`。
