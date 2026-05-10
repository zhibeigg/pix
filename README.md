# pix

<p align="center">
  <strong>从一句话到像素画 — 由 Packy API 驱动的端到端工具链</strong>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#cli-用法">CLI</a> ·
  <a href="#gui">GUI</a> ·
  <a href="#配置">配置</a> ·
  <a href="#faq">FAQ</a>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776ab.svg">
  <img alt="qt" src="https://img.shields.io/badge/GUI-PySide6-41cd52.svg">
  <img alt="CI" src="https://github.com/zhibeigg/pix/actions/workflows/ci.yml/badge.svg">
  <a href="https://github.com/zhibeigg/pix/releases/latest"><img alt="release" src="https://img.shields.io/github/v/release/zhibeigg/pix?include_prereleases"></a>
</p>

---

`pix` 把「想象 → 生图 → 理解 → 像素化」串成一条流水线：

1. 你写一句 prompt（或丢一张图进来）
2. `gpt-image-2` 按 prompt 生图
3. Claude / Gemini / GPT-4o 读图，输出**结构化 JSON**（调色板、主体 ROI、语义区域）
4. Python 根据 JSON 生成**真正的像素画**：锁定调色板、语义区域调色、抖动、风格预设

全程产物落盘，随时回看；缓存按内容哈希，重复 prompt 不烧第二次钱。CLI 与 GUI 共用同一套管线。

---

## ✨ 特性

- **两种起点**：一句 prompt 从头生图，或直接丢一张现成图片进来
- **像素对齐 & 透明背景**：`smart` 下采样自动探测输入像素格并吸附，边缘不再糊；一键 `--remove-bg` 把纯色底抠成透明 PNG
- **结构化 JSON**：VL 模型不是一句描述就完事，而是输出调色板、主体位置、语义区域建议，严格经 Pydantic 校验，失败自动带修正提示重试
- **四套内置预设**：`gameboy` · `nes` · `modern_pixel` · `pico8`，支持自定义 TOML
- **可配置所有参数**：尺寸、色数、抖动、主体锐化、饱和度、VL 模型、预设……CLI 和 GUI 共享同一套
- **9 语言 GUI**：简中 / 繁中 / English / 日本語 / 한국어 / Français / Deutsch / Español / Русский
- **QGraphicsView 预览**：左键平移、滚轮缩放、双击复位、右键复制 / 另存 / 打开所在目录
- **按内容缓存**：同样的 prompt 只烧一次钱；`--refresh` / `--no-cache` 可绕过
- **产物全落盘**：每次运行独立目录，包含原图、JSON、像素图、meta（模型、参数、耗时）
- **166 条测试**，核心业务覆盖率 ≥ 90%

---

## 🧭 工作流

```
┌──────────┐   prompt    ┌──────────────┐    PNG     ┌──────────────┐
│ CLI / GUI│────────────▶│ gpt-image-2  │───────────▶│ 01_source.png│
│ 输入适配 │             │   (Packy)    │            └──────┬───────┘
└────┬─────┘             └──────────────┘                   │
     │ image path                                           │ base64
     └──────────────────────────────────┬──────────────────┘
                                        ▼
                           ┌────────────────────────┐
                           │ Vision (Claude/Gemini) │
                           │  → 02_analysis.json    │  ← Pydantic 校验 + 重试
                           └──────────┬─────────────┘
                                      │
                                      ▼
                     ┌───────────────────────────────┐
                     │ pixelize.core                 │
                     │  · 风格预设 → 默认参数        │
                     │  · palette：JSON 优先 + k-means│
                     │  · ROI 锐化 · 语义区域调色    │
                     │  · Floyd-Steinberg / Ordered  │
                     └──────────┬────────────────────┘
                                ▼
                    03_pixelized.png + meta.json
```

每一次运行的产物目录结构：

```
outputs/20260509-142359-a1b2c3d4/
├── 00_input.txt            # 输入（prompt 或图片路径）
├── 01_source.png           # 原图（生成或上传）
├── 02_analysis.json        # VL 结构化分析
├── 03_pixelized.png        # 最终像素图
└── meta.json               # 模型、参数、耗时、哪步命中缓存
```

---

## 🚀 快速开始

### 方式一：下载预编译版本（免安装 Python）

到 [Releases](https://github.com/zhibeigg/pix/releases/latest) 页面下载对应平台的压缩包，解压即用。Windows 版是单文件 `pix.exe`，可以复制到任意目录运行；打包程序会使用内置 Pix 项目图标（Windows `.ico` / macOS `.icns` / GUI PNG）。

| 平台 | 文件 |
|---|---|
| Windows x64 | `pix-vX.Y.Z-windows-x64.zip` → 解压得到单文件 `pix.exe`，可移动到任意目录运行 |
| macOS Apple Silicon | `pix-vX.Y.Z-macos-arm64.tar.gz` → 解压后双击 `pix.app` |
| macOS Intel | `pix-vX.Y.Z-macos-x86_64.tar.gz` → 同上 |
| Linux x86_64 | `pix-vX.Y.Z-linux-x86_64.tar.gz` → 解压后运行 `./pix/pix` |

CLI 用法同源码版：`pix.exe gen "一只橘猫"`、`./pix/pix pixelize img.png --preset gameboy` 等。

> macOS 首次运行若被 Gatekeeper 拦截，右键 → 打开，或 `xattr -cr pix.app` 解除隔离。

### 方式二：从源码运行

环境要求：

- Python **3.10+**
- Windows / macOS / Linux（GUI 依赖 PySide6）
- [Packy API](https://www.packyapi.com) 账号（或任意 OpenAI 兼容端点）

### 安装

```bash
git clone https://github.com/zhibeigg/pix
cd pix

# 创建虚拟环境（可选但推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 安装依赖 + 开发模式安装
pip install -r requirements.txt
pip install -e .
```

### 配置 API key

推荐通过 GUI 一键配置：

```bash
pix gui
# 菜单 → 文件 → 设置…  填入 Base URL、生图 key、视觉 key，保存
```

也可以手动写 `.env`：

```bash
cp .env.example .env
# 编辑 .env，填入：
# PACKY_API_KEY=sk-xxxxxxxxxx       （sora 分组令牌，用于 gpt-image-2）
# PACKY_VL_API_KEY=sk-xxxxxxxxxx    （default 分组令牌，用于视觉模型，可与上面共用）
```

### 第一次跑

```bash
# 最快的验证：不依赖网络，纯本地像素化一张图
pix pixelize ./your_photo.png --preset gameboy

# 从 prompt 一路到底
pix gen "一只像素风橘猫戴着橙色围巾，温暖插画"

# 打开图形界面
pix gui
```

---

## 💻 CLI 用法

```
pix gen "一只像素风橘猫戴着橙色围巾" \
    --image-size 1024x1024 --image-quality high \
    --pixel-size 128x128 --colors 16 --dither floyd_steinberg \
    --preset auto

pix run my_photo.png --pixel-size 64x64 --preset gameboy    # 已有图 → 分析 → 像素化
pix pixelize my_photo.png --colors 8 --preset pico8          # 只做像素化（不走网络）
pix analyze my_photo.png --model claude-sonnet-4-5           # 只做 VL 分析
pix gen-only "一只像素风橘猫"                                 # 只做文生图
pix asset "血气灵玉" --out 图片/血气灵玉.png                    # 游戏素材直出：生图 → Grid JSON → 16x16 透明 PNG
pix grid-extract source.png --pixel-size 16x16 --colors 12 --out item.grid.json --render item.png
pix grid-render item.grid.json --out 图片/item.png              # Grid JSON → 精确 PNG
pix validate 图片/血气灵玉.png --pixel-size 16x16 --max-colors 16 # 检查素材是否可直接进游戏
pix history --query 血气 --limit 20                         # 查询 outputs 历史记录
pix batch ./photos ./pixelized --workers 8 --preset pico8    # 批量：一个目录进、一个目录出
pix presets                                                  # 列出所有预设
pix gui                                                      # 启动图形界面
```

常用参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `--pixel-size WxH` | 目标像素图尺寸；GUI 内置 `16/32/48/64/96/128/256` 快速预设，也可手输 | `128x128` |
| `--colors N` | 调色板颜色数 (2–256) | `16` |
| `--dither none\|ordered\|floyd_steinberg` | 抖动算法 | `floyd_steinberg` |
| `--preset auto\|gameboy\|nes\|modern_pixel\|pico8` | 风格预设；`auto` = 不强制套预设，保留用户参数 | `auto` |
| `--resample smart\|box\|bicubic\|lanczos\|nearest` | 下采样策略；`smart` 会自动对齐输入像素格 | `smart` |
| `--snap / --no-snap` | smart 模式下是否探测输入像素格并吸附 | `--snap` |
| `--remove-bg` | 自动抠背景（四角 flood-fill），输出透明 PNG | 关 |
| `--bg-tolerance N` | 背景颜色容差（0-128，越大抠越狠） | `12` |
| `--edge-style hard\|feather\|outline` | 互斥边缘风格：硬边 / alpha 羽化 / 外侧描边 | `hard` |
| `--bg-feather N` | 边缘强度：`feather` 时为羽化半径，`outline` 时为描边宽度 | `0` |
| `--auto-crop / --no-auto-crop` | 先识别主体 bbox 并裁剪，再缩到目标像素尺寸 | `false` |
| `--crop-padding N` | 自动裁剪外扩比例 | `0.12` |
| `--crop-square / --no-crop-square` | 自动裁剪时保持正方形 | `true` |
| `--vl-model` | 视觉模型名 | 从配置读 |
| `--no-vl` | 跳过多模态分析（纯 Python 兜底） | `false` |
| `--no-cache` / `--refresh` | 禁用缓存 / 忽略命中强刷 | `false` |
| `--image-size WxH` | 生图尺寸（遵循 Packy 限制） | `1024x1024` |
| `--image-quality low\|medium\|high\|auto` | 生图质量 | `high` |

### 游戏素材直出

`pix asset` 是面向游戏资源目录的快捷生产线，默认参数按 16×16 物品图标优化：12 色、自动裁剪主体、自动抠透明背景，并默认启用 **Pixel Grid JSON 工程图**。最终 PNG 不是直接 resize 的伪像素图，而是先提取 `pixels[y][x]` 与 `palette`，再由 Python 精确渲染。

```bash
pix asset "血气灵玉" --out 图片/血气灵玉.png
pix asset "幽香腐骨菇" --extra-prompt "purple poisonous mushroom, green spores" --overwrite
pix asset "紫髓铁" --out 图片/紫髓铁.png --grid-review     # 额外让 AI 审核/修正 Grid JSON
pix validate 图片/血气灵玉.png --pixel-size 16x16 --max-colors 16
```

默认会额外保留：

```text
图片/血气灵玉_source.png     # 原始高清生图源文件，便于对比和重新提取 Grid
图片/血气灵玉.grid.json      # 像素工程图：调色板 + XY 网格
图片/血气灵玉_preview.png    # nearest 放大预览
图片/血气灵玉.asset.json     # 生产元数据
```

默认中间产物仍保存到 `outputs/{timestamp}-{hash}/`。如需回到旧式 resize/quantize 流程，可加 `--no-grid-mode`；默认只做 Grid 清噪，若需要更统一、更厚的深色轮廓，可加 `--grid-outline`；如需关闭清噪，可加 `--no-grid-cleanup`；如需视觉模型参与调色和区域分析，可加 `--use-vl`；如需 AI 审核 Grid JSON，可加 `--grid-review`。

### 边缘风格

`描边` 和 `羽化` 是互斥风格，不会同时叠加：

```bash
pix pixelize source.png --remove-bg --edge-style hard --bg-feather 0      # 硬边透明
pix pixelize source.png --remove-bg --edge-style feather --bg-feather 1   # alpha 羽化
pix pixelize source.png --remove-bg --edge-style outline --bg-feather 1   # 外侧深色描边
```

GUI 中对应：

```text
边缘风格：硬边 / 羽化 / 描边
边缘强度：羽化半径或描边宽度
```

### 历史查询

所有 `gen` / `run` / GUI 管线都会在 `outputs/{timestamp}-{hash}/meta.json` 写入历史元数据。可以用 CLI 查询：

```bash
pix history
pix history --query 血气 --limit 20
pix history --root outputs --json
```

GUI 中可通过：

```text
顶部菜单「历史记录」 或  Ctrl+H
```

打开历史查询窗口，按 prompt / 模型 / 目录名搜索，选中记录后可加载原图、JSON、像素图并回填主要参数。

### Pixel Grid JSON 工程图

可单独使用 Grid 命令调试和批量处理：

```bash
# 伪像素图 → Grid JSON，可选同时渲染 PNG
pix grid-extract source.png --pixel-size 16x16 --colors 12 --out item.grid.json --render item.png --preview-scale 12

# Grid JSON → 最终 PNG
pix grid-render item.grid.json --out 图片/item.png --preview-scale 12

# Grid JSON 后处理：清理孤立噪点、统一深色轮廓、整理调色板
pix grid-polish item.grid.json --out item.polished.grid.json --render item.polished.png --preview-scale 12

# AI 只审核/修正 JSON，不直接画图
pix grid-review item.grid.json --out item.reviewed.grid.json --render item.reviewed.png
```

Grid JSON 结构示例：

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
  "metadata": { "source_cell_size": [48.0, 48.0], "grid_confidence": 0.82 }
}
```

---

## 🖥️ GUI

```bash
pix gui
```

GUI 提供：

- **Pix 项目图标**：窗口、任务栏和打包应用统一使用内置 `pix_logo_64` 图标
- **三联预览**（原图 / JSON / 像素图），每个支持左键拖拽、滚轮缩放、双击适屏、右键菜单
- **参数面板**（尺寸、色数、抖动、预设、VL 模型、缓存开关）
- **设置对话框**：提供商切换（Packy / OpenAI / 自定义）、API key 管理、默认模型、连接测试、**9 语言**实时切换
- **首次启动**无 key 时主动引导配置
- **状态栏**实时显示 Base URL 和 key 配置状态
- **右键菜单**：复制图片到剪贴板、另存为（PNG/JPEG/BMP/WebP）、复制文件路径、在资源管理器中显示、重置视图、1:1 原始大小

> 截图位：`docs/screenshot-main.png`、`docs/screenshot-settings.png`

---

## 🎨 风格预设

| 名称 | 尺寸 | 色数 | 调色板 | 适用 |
|---|---|---|---|---|
| `auto` | 按用户 / VL 推荐 | – | – | 不确定时交给 VL 判断 |
| `gameboy` | 160×144 | 4 | DMG 绿调 | 复古掌机 |
| `nes` | 256×240 | 16 | 自适应 | 8-bit 游戏 |
| `modern_pixel` | 256×256 | 32 | 自适应 | 精细像素插画 |
| `pico8` | 128×128 | 16 | [PICO-8 官方调色板](https://www.lexaloffle.com/pico-8.php) | Fantasy Console |

预设文件在 `assets/presets/*.toml`，可以随手加一个：

```toml
# assets/presets/my_preset.toml
name           = "my_preset"
description    = "某款独特风格"
output_size    = [96, 96]
colors         = 12
palette_lock   = ["#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75"]
dither         = "ordered"
edge_enhance   = 0.12
saturation     = 1.05
```

---

## 🔧 配置

复制 `config.example.toml` 为 `config.toml` 即可被自动加载。优先级：

```
默认值 < config.toml < .env < 环境变量 < CLI / GUI 显式参数
```

关键小节：

```toml
[api]
base_url       = "https://www.packyapi.com"
timeout        = 180.0
max_retries    = 3

[image_gen]
model          = "gpt-image-2"
size           = "1024x1024"
quality        = "high"

[vision]
model          = "claude-opus-4-7"
temperature    = 0.2

[pixelize]
output_size    = [128, 128]
colors         = 16
dither         = "floyd_steinberg"
preset         = "auto"
auto_crop      = false
crop_padding   = 0.12
crop_square    = true
edge_style     = "hard" # hard | feather | outline，三者互斥
bg_feather     = 0      # feather=羽化半径；outline=描边宽度；hard=不生效

[asset]
output_dir     = "图片"
pixel_size     = [16, 16]
colors         = 12
dither         = "none"
source_copy    = true
image_quality  = "low"
skip_vl        = true
remove_bg      = true
auto_crop      = true
grid_mode      = true
grid_review    = false
grid_json      = true
grid_cleanup   = true
grid_outline   = false   # 默认保守：清噪；需要更强统一轮廓时可用 --grid-outline
grid_outline_strength = 1
grid_min_neighbors = 1
prompt_template = "A single fantasy pixel game inventory item icon of {name}. ..."

[cache]
enabled        = true
dir            = ".pix_cache"

[output]
root           = "outputs"

[history]
max_items      = 200

[ui]
language       = "zh-CN"    # zh-CN | zh-TW | en | ja | ko | fr | de | es | ru
```

> API key 不会被写进 `config.toml`，只写入 `.env` 或环境变量，避免意外提交。

---

## 📄 PixAnalysis JSON Schema

VL 模型按这个结构输出，之后由 Python 严格校验：

```jsonc
{
  "description": "一只橘猫戴着橙色围巾，暖色插画",
  "style": {
    "style_tags": ["chibi", "warm"],
    "recommended_preset": "modern_pixel",
    "target_color_count": 16,
    "suggested_dither": "floyd_steinberg",
    "contrast_level": "mid"
  },
  "palette": [
    { "hex": "#F0B070", "weight": 0.30, "role": "primary" },
    { "hex": "#FF8844", "weight": 0.20, "role": "accent"  }
  ],
  "main_subjects": [
    {
      "label": "cat",
      "bbox_norm": { "x": 0.1, "y": 0.2, "w": 0.6, "h": 0.6 },
      "importance": 0.9,
      "sharpness_hint": "sharp"
    }
  ],
  "semantic_regions": [
    {
      "label": "background",
      "bbox_norm": { "x": 0, "y": 0, "w": 1, "h": 1 },
      "palette_hint": ["#5C3A21"]
    }
  ]
}
```

你可以手改完 `02_analysis.json` 后重跑像素化：

```bash
pix pixelize source.png --analysis 02_analysis.json
```

---

## 🧪 开发 / 测试

```bash
pip install -e ".[dev]"
pytest                          # 全量测试（当前 193 条）
pytest --cov=pix                # 带覆盖率
pytest tests/test_pipeline.py   # 只跑单个模块
ruff check .                    # 代码风格检查
```

想贡献代码？请先读 [CONTRIBUTING.md](./CONTRIBUTING.md)，里面有编码规范、提交前自检清单、commit 风格。

测试覆盖：schema 校验、预设加载、像素化管线、批量处理、缓存、配置合并、API mock（image_gen / vision）、pipeline 集成、CLI、GUI 构造、i18n、右键菜单。

---

## ❓ FAQ

**Q：能用其它 AI 服务而不是 Packy 吗？**
可以。Base URL 指向任何 OpenAI 兼容端点即可。在 GUI 设置里选择"自定义端点"，填你的地址和 key。

**Q：不想调 VL 分析也能用吗？**
可以。加 `--no-vl` 或 GUI 勾上"跳过多模态分析"。管线会降级到纯 k-means 调色 + 默认预设，不依赖网络。

**Q：生图失败提示 `宽高必须是 16 的倍数` 怎么办？**
Packy `gpt-image-2` 要求每边长 ≤ 3840 且是 16 的倍数，总像素 655,360 ~ 8,294,400，长短边比 ≤ 3:1。`pix` 在请求前会前置校验并给出友好提示。改 `--image-size 1024x1024` 这种合法值即可。

**Q：能在 CI / 无 GUI 环境里跑吗？**
能。`pix gen`、`pix run`、`pix pixelize`、`pix analyze` 这些 CLI 命令完全不依赖 PySide6。如果不想装 PySide6，`pip install -e . --no-deps` 然后单独装其它依赖也行。

**Q：JSON 视图里显示"本次未生成 JSON 分析"？**
有三种情况：(1) 你勾了"跳过多模态分析"；(2) 视觉 API key 无效或网络失败；(3) 模型返回的内容无法严格解析成 schema 且重试也失败。看日志里的原因。

**Q：为什么像素图和放大预览只有一个标签？**
之前的"放大预览"是固定 4× 放大的静态图；现在像素图标签本身支持任意倍数缩放（带最近邻插值，放多大都锐利），两者完全等价，所以合并了。

---

## 🗺️ Roadmap

- [x] 跨平台自动构建与发布（Windows / macOS Intel / Apple Silicon / Linux）
- [x] 批量模式：一个目录进、一个目录出（`pix batch`）
- [ ] PyInstaller 打包体积优化 + 可选的单文件构建
- [ ] 用户自定义风格预设的 GUI 编辑器
- [ ] 视觉模型可复用本地小模型（offline 模式）
- [ ] sprite sheet 输出（多姿势 / 多表情批处理）

欢迎在 [Issues](https://github.com/zhibeigg/pix/issues) 里点单，或在 [Discussions](https://github.com/zhibeigg/pix/discussions) 交流。

---

## 🛠️ 版本号

`A.B.C` 三段：

- `A` — 公开接口不兼容变更
- `B` — 新功能
- `C` — bug 修复 / 兼容性修复

---

## 📝 License

MIT © 2026 [纸杯 (zhibeigg)](https://github.com/zhibeigg)

See [LICENSE](./LICENSE) for details.

---

## 🙏 致谢

- [Packy API](https://docs.packyapi.com) 提供 `gpt-image-2` 与 Claude / Gemini 视觉模型访问
- [Pillow](https://github.com/python-pillow/Pillow) 处理所有图像操作
- [PySide6](https://doc.qt.io/qtforpython-6/) 驱动 GUI
- [Typer](https://typer.tiangolo.com/) 驱动 CLI
- [Pydantic](https://docs.pydantic.dev/) 让 VL 输出严格可信
- 配色灵感：[PICO-8](https://www.lexaloffle.com/pico-8.php)、[Lospec Palette List](https://lospec.com/palette-list)
