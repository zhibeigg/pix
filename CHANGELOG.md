# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.21.0] - 2026-05-10

### Added

- 新增 prompt 禁词配置和任务创建拦截，支持逗号、中文逗号、分号、换行分隔。
- 新增上传事件记录和每用户每日上传次数上限，管理员可在运营保护面板配置。

## [0.20.0] - 2026-05-10

### Added

- 新增充值套餐、支付订单和支付事件表，提供 `GET /billing/packages`、`POST /billing/orders`、`GET /billing/orders` 等接口。
- 新增管理员 mock pay 和 mock webhook 幂等到账流程，前端点数账户可创建订单并在管理员模式下模拟支付。

## [0.19.0] - 2026-05-10

### Added

- 新增运营保护系统设置：生成总开关、每用户 pending/running 上限、每用户每日任务上限。
- 管理员后台新增运营保护配置，任务创建、批量创建和失败项重试会在入队前执行限制检查。

## [0.18.0] - 2026-05-10

### Added

- 新增生产 Dockerfile、前端 Nginx 镜像配置、`docker-compose.yml` 和 `.env.production.example`。
- Compose 部署包含 Postgres、Redis、迁移任务、FastAPI API、RQ worker 和前端静态站点。

## [0.17.0] - 2026-05-10

### Added

- 新增可选 Redis/RQ 队列后端，`PIX_WEB_QUEUE_BACKEND=rq` 时任务创建后会推入 RQ 队列。
- 新增 `pix-web-rq-worker` 命令处理 RQ 任务；默认 `database` 队列后端仍保留数据库轮询 worker。

## [0.16.0] - 2026-05-10

### Added

- 新增 Alembic 迁移配置和初始 Web schema 迁移，覆盖用户、点数、价格、任务、输出和素材包表。
- Web 配置新增 `PIX_WEB_AUTO_CREATE_DB`，本地默认自动建表，生产可关闭后使用 `alembic upgrade head` 管理 schema。

## [0.15.0] - 2026-05-10

### Added

- 新增素材包管理接口：`PATCH /batches/{id}` 支持重命名与归档/恢复，`DELETE /batches/{id}` 支持删除空素材包。
- 前端素材包卡片新增重命名、归档/恢复和删除空包操作，归档素材包会弱化显示。

## [0.14.0] - 2026-05-10

### Added

- 新增素材包 ZIP 下载接口 `GET /batches/{id}/download`，打包成功任务的 source、pixelized、preview、analysis 和 meta 文件。
- 前端素材包卡片在存在成功任务时显示“下载素材包”按钮并触发浏览器下载。

## [0.13.0] - 2026-05-10

### Added

- 新增素材包失败项重试接口 `POST /batches/{id}/retry-failed`，失败任务会复制为新的 pending 任务并归入原素材包。
- 前端素材包卡片在存在失败任务时显示“重试失败项”按钮，并在重试后刷新素材包、余额和任务列表。

## [0.12.0] - 2026-05-10

### Added

- 前端素材包面板支持点击筛选，作品网格可切换为全部作品或指定素材包任务。
- 作品网格新增当前筛选提示，轮询会同步刷新素材包任务列表。

## [0.11.0] - 2026-05-10

### Added

- 新增素材包/批次模型，批量创建任务时会生成可命名素材包并关联新任务。
- 新增 `/batches` 与 `/batches/{id}/jobs` 接口，前端新增素材包摘要面板并在作品卡片显示所属素材包。

## [0.10.0] - 2026-05-10

### Added

- 新增原子批量创建接口 `POST /jobs/batch`，批量任务会一次性校验、冻结点数并提交，避免前端循环创建导致半批成功。
- 前端批量生产改用批量创建接口，提交后显示本批次冻结点数。

## [0.9.0] - 2026-05-10

### Added

- 批量生产面板新增批量文生图、批量图生图、批量本地像素化三种模式。
- 支持一次选择多张图片串行上传、展示上传预览/状态，并按上传结果批量创建图生图或本地像素化任务。

## [0.8.0] - 2026-05-10

### Added

- 新增受保护的 `/files` 图片访问接口，仅允许登录用户预览 `web_outputs` 与 `outputs` 下的图片文件。
- 上传响应与任务输出响应新增预览 URL，前端作品网格、上传面板和微调面板现在可以直接显示图片预览。

## [0.7.0] - 2026-05-10

### Added

- 新增浏览器图片上传接口 `/uploads/image`，登录用户可上传 PNG/JPG/WebP 到 Web 本地存储并用于图生图/本地像素化。
- 单图生成面板支持选择本地图片上传，上传成功后自动填充任务输入路径，同时保留手动路径输入。

## [0.6.0] - 2026-05-10

### Added

- 前端工作台重构为作品网格优先，新增单图生成、批量生产模式切换，以及选中作品后的免费本地微调 / AI 微调面板。
- 新增公开 `/pricing` 接口，普通用户也能在创建任务前看到预计点数。

## [0.5.0] - 2026-05-10

### Added

- 新增网站版前端 MVP：Vite + React 工作台，支持注册/登录、点数查看、任务创建、队列轮询、输出路径展示和管理员加点/价格配置。
- FastAPI 后端新增本地开发 CORS，允许 `localhost:5173` 前端访问。

## [0.4.0] - 2026-05-10

### Added

- 新增网站版 Phase 1 后端 MVP：FastAPI API、用户注册登录、JWT、点数账户、点数流水、管理员加点/价格配置、生成任务创建/查询，以及串行 worker 队列。
- Web worker 复用现有 `pix.pipeline.run_pipeline()`，支持任务成功扣费、失败自动退款、本地文件输出记录。

## [0.3.2] - 2026-05-10

### Fixed

- 修复 GUI 运行完成后在主线程同步等待后台线程退出，可能导致窗口短暂显示“未响应”的问题。

## [0.3.1] - 2026-05-10

### Fixed

- 修复源图比例与目标像素尺寸比例不一致时被拉伸的问题：现在会按原比例缩放并居中适配目标画布。

## [0.3.0] - 2026-05-10

### Added

- 接入 Packy `/v1/images/edits` 图生图编辑：CLI `pix run IMAGE --prompt TEXT` 和 GUI 图片模式填写 prompt 时会先图生图，再进入分析与像素化；留空 prompt 时保持直接像素化原图。

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

[Unreleased]: https://github.com/zhibeigg/pix/compare/v0.21.0...HEAD
[0.21.0]: https://github.com/zhibeigg/pix/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/zhibeigg/pix/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/zhibeigg/pix/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/zhibeigg/pix/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/zhibeigg/pix/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/zhibeigg/pix/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/zhibeigg/pix/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/zhibeigg/pix/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/zhibeigg/pix/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/zhibeigg/pix/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/zhibeigg/pix/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/zhibeigg/pix/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/zhibeigg/pix/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/zhibeigg/pix/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/zhibeigg/pix/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/zhibeigg/pix/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/zhibeigg/pix/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/zhibeigg/pix/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/zhibeigg/pix/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/zhibeigg/pix/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/zhibeigg/pix/compare/v0.2.4...v0.3.0
[0.2.4]: https://github.com/zhibeigg/pix/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/zhibeigg/pix/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/zhibeigg/pix/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/zhibeigg/pix/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/zhibeigg/pix/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zhibeigg/pix/releases/tag/v0.1.0
