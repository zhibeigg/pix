# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.4] - 2026-05-10

### Fixed

- 修复透明像素图右键复制后部分目标程序无法粘贴的问题：剪贴板同时写入标准图片数据和原始 PNG 数据。

## [0.2.3] - 2026-05-10

### Fixed

- 清理 Ruff 静态检查问题：移除未使用导入，并为 `zip()` 显式设置 `strict=True`。

## [0.2.2] - 2026-05-10

### Fixed

- 修复外描边在已有深色轮廓、斜边和凹角处二次膨胀，导致局部黑边过厚的问题。

## [0.2.1] - 2026-05-10

### Fixed

- 修复 GUI 历史记录窗口仍可能阻塞主窗口的问题：历史窗口改为普通独立顶层窗口，记录加载延迟到事件队列，并防止同一历史记录重复加载。

## [0.2.0] - 2026-05-10

### Added

- 正式 Pix 项目图标：新增 `pix_logo_64.png` / `pix_logo.ico` / `pix_logo.icns`，GUI 窗口和 PyInstaller 打包产物统一使用该 logo。
- Windows 单文件打包：新增 `build_tools/pix_onefile.spec`，Release Windows 包改为只包含可移动运行的 `pix.exe`。
- `pix asset`：面向游戏资源目录的素材直出命令，内置物品图标 prompt 模板，默认 16×16、12 色、无抖动、自动裁剪主体、自动透明背景，并通过 Pixel Grid JSON 工程图精确渲染最终 PNG；同时默认复制原始高清生图源文件为 `*_source.png`，方便对比和重新提取。
- Pixel Grid JSON 中间表示：新增 `pix grid-extract` / `pix grid-render` / `pix grid-polish` / `pix grid-review`，支持从高清伪像素图提取 XY 网格、限色调色板、清理孤立噪点、统一深色轮廓、AI 审核 JSON，再确定性渲染 PNG。
- `pix validate`：检查 PNG 是否适合作为像素游戏素材，包括尺寸、alpha、透明背景、颜色数、主体 bbox、半透明脏边与贴边提示。
- 历史查询：新增 `pix history` CLI 和 GUI「文件 → 历史记录…」窗口，可搜索 `outputs/*/meta.json`，加载历史原图、JSON、像素图并回填主要参数。
- **自动裁剪主体**：新增 `auto_crop` / `crop_padding` / `crop_square` 像素化参数，支持先按 alpha 或四角背景估计主体 bbox，再裁剪缩小，提升小图标可读性。
- **像素对齐（smart downsample）**：自动探测输入图片的原生像素格大小，先按整数倍 BOX 聚合再缩到目标尺寸，硬边不再被 BICUBIC 糊化。新增 `--resample smart|box|bicubic|lanczos|nearest` 与 `--snap/--no-snap` 参数。
- **自动抠背景**：`--remove-bg` 通过四角 flood-fill 把纯色底抠成透明 PNG，带 `--bg-tolerance` 颜色容差。
- 互斥边缘风格：新增 `edge_style = hard|feather|outline` / `--edge-style`，把硬边、alpha 羽化和外侧描边做成互斥预设；`bg_feather` 作为边缘强度复用。
- GUI 参数面板：新增下采样策略下拉、"对齐像素格"勾选、"自动抠背景"勾选 + 容差/边缘风格/边缘强度；生图尺寸与像素尺寸改为可编辑下拉预设；9 种语言文案同步。
- `pix batch <input-dir> <output-dir>`：目录级批量像素化，支持并发与失败重试。
- CI 接入 `ruff` lint 任务；GitHub Actions 全部升级到支持 Node 24 的版本。
- Dependabot 依赖升级自动化。
- CONTRIBUTING / ISSUE / PR 模板。

### Fixed

- 修复语义区域处理会丢失 RGBA alpha 的问题，避免透明素材在 VL 分析后被量化成大块浅色矩形背景。
- Packy OpenAI-compatible Claude 视觉端点拒绝 `system` role 时，改为把系统约束合并到首条 `user` 消息，避免 VL 分析直接 HTTP 400。
- 修复存在 VL `analysis` 时 `remove_bg` / `resample` / `snap_to_grid` 等像素化参数被静默重置的问题。
- `remove_background` 内部距离计算用 `int16` 会溢出（255² > 32767），改成 `int32`，否则主体会被误判为背景全部抠空。

### Changed

- 默认视觉模型调整为 `claude-opus-4-7`。
- 清理若干未使用的 import（`io_utils.py` / `image_gen.py` / `pipeline.py` / `settings.py`）。

## [0.1.0] - 2026-05-10

### Added

- 一句 prompt 到像素画的端到端流水线：`gpt-image-2` 生图 → Claude / Gemini / GPT-4o 分析 → Python 像素化。
- Typer CLI：`gen` / `run` / `pixelize` / `analyze` / `gen-only` / `presets` / `gui`。
- PySide6 GUI：三联预览（左键平移 / 滚轮缩放 / 双击复位 / 右键菜单）、参数面板、设置对话框。
- 设置对话框：提供商切换、API key 管理、默认模型、连接测试、9 语言实时切换。
- 四套内置风格预设：`gameboy` / `nes` / `modern_pixel` / `pico8`。
- 9 种界面语言：简中、繁中、English、日本語、한국어、Français、Deutsch、Español、Русский。
- 按内容哈希的幂等缓存；`--no-cache` / `--refresh` 可绕过。
- Pydantic 强校验的 `PixAnalysis` schema；失败自动带修正提示重试。
- 跨平台 CI/CD：push 触发多平台 pytest；tag `v*` 触发四平台 PyInstaller 构建并发布 Release。
- 166 条测试，核心业务覆盖率 ≥ 90%。

[Unreleased]: https://github.com/zhibeigg/pix/compare/v0.2.4...HEAD
[0.2.4]: https://github.com/zhibeigg/pix/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/zhibeigg/pix/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/zhibeigg/pix/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/zhibeigg/pix/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/zhibeigg/pix/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zhibeigg/pix/releases/tag/v0.1.0
