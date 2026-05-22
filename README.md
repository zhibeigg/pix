# Pix

<p align="center">
  <strong>AI 像素素材生产线：从一句话、源图或批量清单，生成可进游戏的透明 PNG 与 Pixel Grid 工程图。</strong>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#游戏素材直出">素材直出</a> ·
  <a href="#web-工作台">Web 工作台</a> ·
  <a href="#配置">配置</a> ·
  <a href="#开发">开发</a>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776ab.svg">
  <img alt="version" src="https://img.shields.io/badge/version-1.24.46-6f42c1.svg">
  <img alt="tests" src="https://img.shields.io/badge/tests-386%20passed-2ea44f.svg">
</p>

---

## Pix 是什么？

Pix 不是普通的“AI 生图相册”。它是一条面向游戏素材生产的工程化流水线：

```text
Prompt / Image
    ↓
受控生图 / 图生图编辑 / 本地像素化
    ↓
候选生成与 VL 评分
    ↓
结构化图像理解 JSON
    ↓
Pixel Grid 提取 / 调色 / 后处理
    ↓
透明 PNG + .grid.json + preview + meta
```

Pix 的目标是让 AI 生成结果变成**可复用、可追溯、可批量交付**的游戏资产：图标、道具、UI、精灵表、动画 GIF、素材包。

---

## 为什么用 Pix？

| 问题 | Pix 的处理方式 |
|---|---|
| AI 图好看但不能进游戏 | 输出透明 PNG、固定尺寸、有限调色板、nearest 预览 |
| 小图标缩小后糊掉 | 使用 Pixel Grid JSON 中间表示，最终由 Python 精确渲染 |
| 一次生图结果不稳定 | n-sample / contact sheet 候选生成 + VL 自动评分选择 |
| 背景难抠、边缘脏 | 动态 key color、透明背景处理、低像素描边策略 |
| 生成过程不可追溯 | 每次运行写入 `meta.json`、`provenance.json`、源图与参数 |
| 网站化运营成本不可控 | Web 版支持账户、点数、队列、任务限制、批量包管理 |

---

## 核心能力

- **三种入口**
  - 文生图：一句 prompt 生成源图并像素化。
  - 图生图：上传图片 + 修改描述，先 AI 编辑再像素化。
  - 本地像素化：已有图片直接转像素图，不需要网络。

- **候选生成与评分**
  - 默认 `n_sample`：一次生成多张独立 full-res 候选。
  - 可切换 contact sheet：生成九宫格后自动切图。
  - VL 根据 prompt 符合度、轮廓、可读性、抠图质量评分。

- **Pixel Grid 工程图**
  - `.grid.json` 保存画布、调色板、像素矩阵、可读性元数据。
  - PNG 由确定性渲染器生成，避免“看起来像像素图但实际很糊”。

- **游戏素材直出**
  - `pix asset` 默认按 16×16 RPG 道具图标优化。
  - 白底单图 → extract Pixel Grid → auto/K-means 调色 → 透明 PNG。
  - 默认贴近早期稳定效果，不默认强制 ramp、outline、fit canvas。

- **动画精灵表**
  - `pix sprite` 让生图模型输出 3×3 连续动画关键帧。
  - 后端自动切出 9 帧、逐帧像素化、统一调色板，并输出 GIF 与横向精灵表 PNG。

- **Web 工作台**
  - FastAPI + React + Vite。
  - 支持注册登录、管理员初始化、点数账户、任务队列、素材包、批量生成、ZIP 导出。
  - 单张/批量入口可直接调用 `pix asset` 同款游戏素材直出策略，按素材名称生成透明 PNG 与 Pixel Grid。
  - 主页与登录后工作台严格对齐 `apps/web/DESIGN.md` 的 Notion 式视觉：深海军蓝 Hero、紫色主 CTA、真实 Workspace 侧边栏、浅色 Canvas/Surface 与 pastel feature cards；76 套题材范例支持悬浮查看拆分后的 8 个物品格、UI 展示图、中文 Prompt 和文件名。
  - 管理后台可配置模型/API、价格、充值套餐、运营保护和素材默认值。

- **可测试、可部署**
  - Python CLI、GUI、Web API、worker 共用同一套核心流水线。
  - 当前全量测试：`385 passed`。
  - 支持 Docker Compose 生产预览部署。

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+（仅 Web 前端需要）
- Packy API 或 OpenAI 兼容图像/视觉模型端点

### 2. 安装

```bash
git clone https://github.com/zhibeigg/pix
cd pix

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev,web,gui]"
```

如果只用 CLI，可安装核心依赖：

```bash
pip install -e .
```

### 3. 配置密钥

复制环境变量模板：

```bash
cp .env.example .env
```

至少配置：

```env
PACKY_API_KEY=sk-xxxxxxxxxx
PACKY_VL_API_KEY=sk-xxxxxxxxxx
```

也可以复制默认配置：

```bash
cp config.example.toml config.toml
```

> `config.toml` 和 `.env` 默认被忽略，不会提交到仓库。

### 4. 第一次运行

```bash
# 本地像素化，不走网络
pix pixelize ./your_image.png --pixel-size 64x64 --colors 16

# 文生图 → 分析 → 像素化
pix gen "一枚红色宝石戒指，像素风 RPG 道具图标"

# 游戏素材直出
pix asset "紫檀木" --out 图片/紫檀木.png

# 九宫格动画精灵表 → 9 帧 + GIF + 横向 PNG
pix sprite "暗黑骑士挥剑三段斩，紫色暗影拖尾" \
  --pixel-size 64x64 \
  --colors 16 \
  --duration-ms 120
```

---

## CLI

Pix 的 CLI 命令：

| 命令 | 用途 |
|---|---|
| `pix gen` | 文生图并完整跑完像素化流水线 |
| `pix run` | 图片输入；可选 prompt 时走图生图编辑 |
| `pix gen-only` | 只调用生图模型，保存候选/源图 |
| `pix sprite` | 生成 3×3 动画关键帧，输出 9 帧、GIF 和横向精灵表 |
| `pix analyze` | 只调用 VL，输出 PixAnalysis JSON |
| `pix pixelize` | 只做本地像素化，不依赖网络 |
| `pix asset` | 游戏素材直出：源图、Grid、透明 PNG、预览、元数据 |
| `pix grid-extract` | 从源图提取 Pixel Grid JSON |
| `pix grid-render` | 从 Pixel Grid JSON 渲染 PNG |
| `pix grid-polish` | 对 Grid 做清噪、轮廓、调色板整理 |
| `pix validate` | 检查素材尺寸、透明度、颜色数等 |
| `pix batch` | 批量处理目录 |
| `pix history` | 查询 `outputs/` 历史记录 |
| `pix presets` | 查看内置风格预设 |
| `pix gui` | 启动桌面 GUI |

常用示例：

```bash
# 文生图全流程
pix gen "一只橘猫戴着橙色围巾，温暖像素风" \
  --image-size 1024x1024 \
  --pixel-size 128x128 \
  --colors 16

# 图片 → 像素图
pix run ./source.png --pixel-size 64x64 --preset pico8

# 图片 + prompt → 图生图编辑 → 像素图
pix run ./sword.png \
  --prompt "保留剑的轮廓，改成冰蓝水晶材质" \
  --pixel-size 64x64

# 只做本地像素化
pix pixelize ./source.png \
  --pixel-size 32x32 \
  --colors 12 \
  --remove-bg \
  --edge-style outline

# 查询历史
pix history --query 紫檀 --limit 20
```

---

## 游戏素材直出

`pix asset` 是给游戏资源目录准备的快捷命令。默认目标是稳定生成 16×16/32×32 等小图标，而不是追求高清插画感。

```bash
pix asset "血气灵玉" --out 图片/血气灵玉.png
pix asset "幽香腐骨菇" --extra-prompt "purple poisonous mushroom, green spores" --overwrite
pix asset "青铜钥匙" --pixel-size 32x32 --colors 16
```

默认产物：

```text
图片/血气灵玉.png           # 最终透明 PNG
图片/血气灵玉_source.png    # 原始生图源文件
图片/血气灵玉.grid.json     # Pixel Grid 工程图
图片/血气灵玉_preview.png   # nearest 放大预览
图片/血气灵玉.asset.json    # 生产元数据
```

默认策略：

| 项 | 默认值 | 说明 |
|---|---|---|
| 最低尺寸 | 16×16 | 16×16 以下不再支持 |
| 生图背景 | plain white background | 更接近早期稳定素材效果 |
| Grid | 开启 | 先提取像素工程图，再渲染 PNG |
| 调色 | `auto` / K-means | 保留自然手感 |
| `grid_cleanup` | 关闭 | 需要清噪时显式开启 |
| `grid_outline` | 关闭 | 需要硬轮廓时显式开启 |
| `fit_canvas` | 关闭 | UI 条/按钮贴合画布时显式开启 |
| `palette_mode=ramp` | 关闭 | 需要色阶重映射时手动开启 |

常见增强：

```bash
# 清理孤立噪点
pix asset "毒蘑菇" --grid-cleanup

# 加强外轮廓
pix asset "铁剑" --grid-outline

# UI 条、按钮、面板贴合目标画布
pix asset "生命条" --pixel-size 64x16 --fit-canvas --fit-mode smart
```

---

## Pixel Grid JSON

Pixel Grid 是 Pix 的核心中间表示：

```jsonc
{
  "version": 1,
  "canvas": { "width": 16, "height": 16, "transparent_index": -1 },
  "axes": { "x": [0, 1, 2], "y": [0, 1, 2] },
  "palette": [
    { "id": 0, "hex": "#2A1115", "role": "outline" },
    { "id": 1, "hex": "#C93A45", "role": "primary" }
  ],
  "pixels": [
    [-1, -1, 0],
    [-1, 0, 1],
    [-1, -1, 0]
  ],
  "metadata": {
    "generator": "extract_grid",
    "readability": {}
  }
}
```

独立使用：

```bash
# 源图 → Grid JSON + PNG
pix grid-extract source.png \
  --pixel-size 16x16 \
  --colors 12 \
  --out item.grid.json \
  --render item.png \
  --preview-scale 12

# Grid JSON → PNG
pix grid-render item.grid.json --out item.png --preview-scale 12

# 后处理 Grid
pix grid-polish item.grid.json \
  --out item.polished.grid.json \
  --render item.polished.png
```

---

## Web 工作台

Pix Web 是一个可运营的素材生产工作台：

- 首次启动管理员初始化
- 邮箱验证码注册登录
- 点数账户与任务扣费/退款
- 游戏素材直出：输入素材名称，复用 `pix asset` 白底单图模板、Pixel Grid 提取和透明 PNG 输出
- 首页展示中文 prompt 全流程示例，鼠标悬浮或键盘聚焦物品格可展开源图 / Grid / 预览详情，并在动画卡片上播放 9 帧序列帧、显示横向精灵图
- 独立原始生图页：只保留提供商、模型、尺寸、质量、敏感度和生成数量等基础参数，提交后停留在中央画布查看 source 原图与候选缩略图
- 单图生成、图生图、本地像素化、动画精灵表
- 批量素材直出、批量 prompt / 批量图片任务
- 作品库最多保留每个账户最新 10 张成功作品，继续生成时会提示并自动清理最旧作品
- 作品库单任务失败重试、素材包失败项重试、ZIP 下载
- 前端国际化统一使用 `i18next` / `react-i18next` 翻译键；浅色/深色/跟随系统主题继续走 Tailwind `dark` class、Radix 组件和 CSS 变量 token，不引入分散特例写法
- 管理后台：模型/API、价格、充值套餐、运营保护、邮件配置
- 支付模型：mock pay、支付宝电脑网站支付（公钥模式 / 证书模式）、微信 Native 扫码支付

### 本地启动

安装 Web 依赖：

```bash
pip install -e ".[web]"
npm install --prefix apps/web
```

配置 `.env`：

```env
PIX_WEB_DATABASE_URL=sqlite:///pix_web.db
PIX_WEB_JWT_SECRET=change-me-to-a-long-random-secret
PIX_WEB_STORAGE_ROOT=web_outputs
PIX_WEB_AUTO_CREATE_DB=true
PIX_WEB_QUEUE_BACKEND=database
PIX_WEB_EMAIL_PROVIDER=console
```

启动 API：

```bash
pix-web-api
# 或
uvicorn pix_web.main:app --reload
```

启动 worker：

```bash
pix-web-worker
# 测试时只处理一个任务
pix-web-worker --once
```

启动前端：

```bash
npm run dev --prefix apps/web
```

默认访问：

```text
http://localhost:5173
```

本地访问时登录/注册面板会显示“使用本地测试账号”，点击后后端会创建/复用 `local-test@pix.example` 普通用户并补足 1000 点数；该入口与签发的 token 都只接受 `localhost` / `127.0.0.1` / `::1` 请求，也兼容本地 Docker/Nginx 反向代理，生产域名不会显示也不能调用。

Vite 默认把 `/api` 代理到 `http://localhost:8000`；从 `127.0.0.1` 打开前端时，浏览器端会自动改走 `localhost` 代理，避免 Windows 本地 loopback 绑定差异。若需改后端地址：

```bash
VITE_PIX_API_PROXY_TARGET=http://localhost:8000 npm run dev --prefix apps/web
```

### Docker Compose 预览部署

```bash
cp .env.production.example .env.production
# 编辑 .env.production，至少替换 PACKY_API_KEY、PIX_WEB_JWT_SECRET、POSTGRES_PASSWORD

docker compose --env-file .env.production run --rm migrate
docker compose --env-file .env.production up --build
```

默认访问：

```text
http://localhost:8080
```

上线前检查：

```bash
pix-web-check
```

生产建议：

```env
PIX_WEB_AUTO_CREATE_DB=false
PIX_WEB_QUEUE_BACKEND=rq
PIX_WEB_REDIS_URL=redis://localhost:6379/0
PIX_WEB_EMAIL_PROVIDER=smtp

# SMTP 465 implicit SSL（QQ/网易/企业邮箱等常见配置）
PIX_WEB_SMTP_HOST=smtp.example.com
PIX_WEB_SMTP_PORT=465
PIX_WEB_SMTP_USER=noreply@example.com
PIX_WEB_SMTP_PASSWORD=change-me
PIX_WEB_SMTP_FROM="Pix <noreply@example.com>"
PIX_WEB_SMTP_SSL=true
PIX_WEB_SMTP_TLS=false

# 支付宝证书模式；证书内容可直接放变量，也可用 *_PATH 指向 Secret 文件。
ALIPAY_MODE=certificate
ALIPAY_APP_ID=your-app-id
ALIPAY_PRIVATE_KEY=/run/secrets/alipay_private_key.pem
ALIPAY_APP_CERT_PATH=/run/secrets/alipay_app_cert.crt
ALIPAY_PUBLIC_CERT_PATH=/run/secrets/alipay_public_cert.crt
ALIPAY_ROOT_CERT_PATH=/run/secrets/alipay_root_cert.crt
```

如需使用 SMTP 587 STARTTLS，请设置 `PIX_WEB_SMTP_PORT=587`、`PIX_WEB_SMTP_SSL=false`、`PIX_WEB_SMTP_TLS=true`。支付宝公钥模式继续使用 `ALIPAY_PUBLIC_KEY`；`ALIPAY_MODE=auto` 会在检测到证书配置时自动切换到证书模式。

支付宝开放平台“应用网关”可配置为：

```text
https://你的域名/api/billing/webhook/alipay/app-gateway
```

该入口用于接收 `msg_method` / `biz_content` / `notify_id` 形式的开放平台消息通知，会复用支付宝公钥或证书配置验签，按 `notify_id` 幂等保存消息，并按支付宝要求返回纯文本 `success`。支付结果异步通知仍使用 `/billing/webhook/alipay`。

点数中心支持固定套餐和自定义点数充值。自定义充值金额由后端按当前启用基准套餐单价派生，并在创建订单时重新计算；前端只展示预计金额，不能传入或篡改最终支付金额。

---

## GUI

```bash
pix gui
```

GUI 适合本地调参和快速预览：

- 原图 / JSON / 像素图三联预览
- 鼠标拖拽、滚轮缩放、双击复位
- 右键复制图片、另存、打开所在目录
- 设置对话框管理 Base URL、模型、API key
- 支持 9 种语言界面

---

## 配置

配置优先级：

```text
默认值 < config.toml < .env < 环境变量 < CLI / GUI 显式参数
```

常用配置片段：

```toml
[api]
base_url = "https://www.packyapi.com"
timeout = 180.0
max_retries = 3

[image_gen]
model = "gpt-image-2"
size = "1024x1024"
quality = "high"
candidate_mode = "n_sample" # n_sample | contact_sheet
n_sample_count = 4
contact_sheet_enabled = true
prompt_guard_enabled = true
candidate_vl_ranking_enabled = true

[vision]
model = "claude-opus-4-7"
temperature = 0.2

[pixelize]
output_size = [128, 128]
colors = 16
dither = "floyd_steinberg"
preset = "auto"
resample = "smart"
snap_to_grid = true
palette_mode = "auto" # auto | ramp | kmeans

[asset]
output_dir = "图片"
pixel_size = [16, 16]
colors = 12
dither = "none"
source_copy = true
image_quality = "low"
skip_vl = true
remove_bg = true
auto_crop = true
grid_mode = true
grid_json = true
grid_cleanup = false
grid_outline = false
fit_canvas = false
palette_mode = "auto"
```

密钥建议只放 `.env` 或部署平台 Secret：

```env
PACKY_API_KEY=sk-...
PACKY_VL_API_KEY=sk-...
```

---

## 输出目录

一次完整运行会在 `outputs/` 下创建独立目录：

```text
outputs/20260514-120000-a1b2c3d4/
├── 00_input.txt
├── 01_source.png
├── 02_analysis.json
├── 03_pixelized.png
├── 03_pixelized.grid.json
├── 04_pixelized_preview.png
├── candidates/
├── candidate_outputs/
└── meta.json
```

首页示例图会额外记录：

```text
apps/web/public/homepage-examples/provenance.json
```

用于追踪示例图来自哪个 prompt、run directory、source、analysis 和 meta。

---

## 风格预设

内置预设：

| 预设 | 说明 |
|---|---|
| `auto` | 不强行套风格，保留用户参数与 VL 建议 |
| `gameboy` | 复古掌机绿调 |
| `nes` | 8-bit 游戏风格 |
| `modern_pixel` | 更精细的现代像素插画 |
| `pico8` | PICO-8 调色板 |

查看：

```bash
pix presets
```

---

## 开发

安装开发依赖：

```bash
pip install -e ".[dev,web,gui]"
npm install --prefix apps/web
```

常用命令：

```bash
py -m ruff check src tests scripts/generate_homepage_examples.py
py -m pytest
npm run build --prefix apps/web
```

当前验证基线：

```text
Ruff: all checks passed
Pytest: 382 passed
Web build: vite build passed
```

提交前建议：

```bash
git status --short
git diff --check
py -m ruff check src tests scripts/generate_homepage_examples.py
py -m pytest
npm run build --prefix apps/web
```

---

## 常见问题

### 不想调用 AI，可以只做本地像素化吗？

可以：

```bash
pix pixelize source.png --pixel-size 64x64 --colors 16
```

这条命令不依赖生图模型或 VL。

### 为什么 asset 默认不用 ramp？

小尺寸图标里，ramp 重映射可能改变材质手感。`pix asset` 默认使用经典 `auto` / K-means，是为了贴近早期白底单图的稳定效果。需要更强色阶时可改配置：

```toml
[asset]
palette_mode = "ramp"
```

### 8×8 还能生成吗？

当前 `pix asset` 最低支持 16×16。8×8 的 AI Grid 直绘路径已经删除，避免维护多套不稳定策略。

### Web 生产环境要注意什么？

至少确认：

- `PIX_WEB_JWT_SECRET` 已替换为强随机值。
- `PACKY_API_KEY` 已配置。
- `PIX_WEB_STORAGE_ROOT` 挂载到持久化卷。
- 生产环境关闭 `PIX_WEB_AUTO_CREATE_DB`，改用 Alembic 迁移。
- 邮件使用 SMTP，不使用开发用 `console`。
- Redis/RQ worker 正常运行。
- 支付密钥通过 Secret 管理，不写入仓库。

---

## 版本规则

版本格式：`A.B.C`

| 位 | 含义 | 递增时机 |
|---|---|---|
| `A` | API 变动 | 公开接口发生不兼容变更 |
| `B` | 功能更新 | 新增功能 |
| `C` | 修复 | Bug 修复、兼容性修复、清理 |

当前版本：`1.17.29`

---

## License

MIT © 2026 [纸杯 (zhibeigg)](https://github.com/zhibeigg)

See [LICENSE](./LICENSE) for details.

---

## 致谢

- [Packy API](https://www.packyapi.com) — 图像生成与视觉模型访问
- [Pillow](https://github.com/python-pillow/Pillow) — 图像处理
- [Pydantic](https://docs.pydantic.dev/) — 结构化模型校验
- [Typer](https://typer.tiangolo.com/) — CLI
- [FastAPI](https://fastapi.tiangolo.com/) — Web API
- [React](https://react.dev/) + [Vite](https://vite.dev/) — Web 前端
