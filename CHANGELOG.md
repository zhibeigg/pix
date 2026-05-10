# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `pix batch <input-dir> <output-dir>`：目录级批量像素化，支持并发与失败重试。
- CI 接入 `ruff` lint 任务；GitHub Actions 全部升级到支持 Node 24 的版本。
- Dependabot 依赖升级自动化。
- CONTRIBUTING / ISSUE / PR 模板。

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
