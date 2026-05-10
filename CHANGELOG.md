# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **像素对齐（smart downsample）**：自动探测输入图片的原生像素格大小，先按整数倍 BOX 聚合再缩到目标尺寸，硬边不再被 BICUBIC 糊化。新增 `--resample smart|box|bicubic|lanczos|nearest` 与 `--snap/--no-snap` 参数。
- **自动抠背景**：`--remove-bg` 通过四角 flood-fill 把纯色底抠成透明 PNG，带 `--bg-tolerance` 颜色容差与 `--bg-feather` 边缘羽化保护。
- GUI 参数面板：新增下采样策略下拉、"对齐像素格"勾选、"自动抠背景"勾选 + 容差/羽化两个 spin；9 种语言文案同步。
- `pix batch <input-dir> <output-dir>`：目录级批量像素化，支持并发与失败重试。
- CI 接入 `ruff` lint 任务；GitHub Actions 全部升级到支持 Node 24 的版本。
- Dependabot 依赖升级自动化。
- CONTRIBUTING / ISSUE / PR 模板。

### Fixed

- `remove_background` 内部距离计算用 `int16` 会溢出（255² > 32767），改成 `int32`，否则主体会被误判为背景全部抠空。

### Changed

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

[Unreleased]: https://github.com/zhibeigg/pix/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zhibeigg/pix/releases/tag/v0.1.0
