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

到 [Releases](https://github.com/zhibeigg/pix/releases/latest) 页面下载对应平台的压缩包，解压即用。

| 平台 | 文件 |
|---|---|
| Windows x64 | `pix-vX.Y.Z-windows-x64.zip` → 解压后双击 `pix.exe` |
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
pix batch ./photos ./pixelized --workers 8 --preset pico8    # 批量：一个目录进、一个目录出
pix presets                                                  # 列出所有预设
pix gui                                                      # 启动图形界面
```

常用参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `--pixel-size WxH` | 目标像素图尺寸 | `128x128` |
| `--colors N` | 调色板颜色数 (2–256) | `16` |
| `--dither none\|ordered\|floyd_steinberg` | 抖动算法 | `floyd_steinberg` |
| `--preset auto\|gameboy\|nes\|modern_pixel\|pico8` | 风格预设；`auto` = 由 VL 推荐 | `auto` |
| `--vl-model` | 视觉模型名 | 从配置读 |
| `--no-vl` | 跳过多模态分析（纯 Python 兜底） | `false` |
| `--no-cache` / `--refresh` | 禁用缓存 / 忽略命中强刷 | `false` |
| `--image-size WxH` | 生图尺寸（遵循 Packy 限制） | `1024x1024` |
| `--image-quality low\|medium\|high\|auto` | 生图质量 | `high` |

---

## 🖥️ GUI

```bash
pix gui
```

GUI 提供：

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
model          = "claude-sonnet-4-5"
temperature    = 0.2

[pixelize]
output_size    = [128, 128]
colors         = 16
dither         = "floyd_steinberg"
preset         = "auto"

[cache]
enabled        = true
dir            = ".pix_cache"

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
pytest                          # 全量测试（当前 179 条）
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
