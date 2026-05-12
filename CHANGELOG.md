# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.47.0] - 2026-05-11

### Added

- 首页素材包看板新增“尺寸校准台”，展示血气灵玉、紫髓铁、幽光菇的 32x、16x、8x 多尺寸交付效果。
- 新增首页静态多尺寸图标资源；32x/16x 来自现有首页图标的 Pixel Grid extract，8x 使用 AI Grid 直绘生成。

## [0.46.0] - 2026-05-11

### Changed

- `pix asset` 默认在 image2 源图后直接走 Pixel Grid extract + cleanup/outline + fit_canvas + render，减少普通 resize/量化与 CLI 二次提取的差异。
- 素材直出新增低尺寸策略：16x16 以下仅允许 8x8，且 8x8 必须使用 AI Grid 直绘并禁止静默回退。
- Web/API 同步低尺寸校验，前端在 8x8 时自动启用 AI 低像素工程图。

## [0.45.0] - 2026-05-11

### Changed

- AI Grid 的 VL 输入升级为原始 prompt + 初始源图 + 源图网格对齐 draft PixelGrid + draft 预览图 + 可读性诊断，降低小尺寸目标直接下采样导致的糊化和误读。
- Python draft 不再强制使用最终目标尺寸，而是优先使用源图检测出的实际像素格尺寸，并按最大轴上限等比裁剪输入矩阵长度。

## [0.44.0] - 2026-05-11

### Added

- `pix asset` 新增可选 `--ai-grid` 直绘模式，让模型直接输出 `palette + pixels[y][x]` Pixel Grid，并通过可读性评分自动返修后由 Python 渲染 PNG。
- Web 单图、批量和微调表单新增 `AI 低像素工程图` 显式开关，并在任务/作品卡展示可读性、返修和回退状态。
- 新增 Pixel Grid 字符串矩阵 schema、AI Grid 设计和可读性评分测试。

## [0.43.0] - 2026-05-11

### Added

- Web 注册流程新增邮箱验证码：先请求 `/auth/register-code` 发送 6 位验证码，再携带 `verification_code` 完成注册。
- 新增邮箱验证码表、SMTP/console 邮件发送配置、部署检查和生产环境示例配置。

## [0.42.5] - 2026-05-11

### Added

- 在 Web 页面底部加入备案号 `鲁ICP备2022023963号`，并链接至工信部备案系统。

## [0.42.4] - 2026-05-11

### Changed

- 调整 Web 首页首屏文案，直截了当地突出“AI 驱动、批量生成可用像素资产”的核心卖点。

## [0.42.3] - 2026-05-11

### Fixed

- 修正 Web 暗色主题的 `inkDeep` token，避免漏网胶囊或选中态继续渲染成浅底浅字。

## [0.42.2] - 2026-05-11

### Fixed

- 系统性修复 Web 暗色模式里深色胶囊、主导航选中态、创建模式选中态和主按钮文字对比度不足的问题。

## [0.42.1] - 2026-05-11

### Fixed

- 修复首页深色模式中 `UI Kit`、`开始` 胶囊标签浅底白字导致对比度不足的问题。

## [0.42.0] - 2026-05-11

### Added

- 为 Web 端加入克制的像素工坊愉悦细节：品牌区像素火花 hover、主题菜单按压反馈、图标徽章和更有场景感的作品库/队列空状态。

## [0.41.2] - 2026-05-11

### Fixed

- 顶部导航左侧品牌区现在可点击返回首页，并提供可访问标签和 hover 反馈。

## [0.41.1] - 2026-05-11

### Changed

- 将 Web 端主题切换从单按钮改为浅色、深色、自动三项菜单，并显示当前系统主题，提升暗色模式选择体验。

## [0.41.0] - 2026-05-11

### Added

- Web 端新增暗色工作台主题，支持跟随系统偏好、顶部手动切换和 `localStorage` 持久化。
- 新增 light/dark 双模式主题变量，让卡片、表单、状态色、阴影和背景在亮色/暗色下统一切换。

## [0.40.0] - 2026-05-11

### Changed

- 简化 Web 端首页、工作台、作品库、素材包、点数中心和管理后台的说明文案，减少重复解释，保留操作必要信息。
- 使用 `pix_logo_64_v2.png` 作为 Web 站点 favicon、Apple touch icon 和顶部导航 Logo。
- 跟踪 `DESIGN.md` 设计参考文档，便于后续界面迭代复用设计上下文。

## [0.39.3] - 2026-05-11

### Fixed

- 修复 GitHub Actions CI 测试环境未安装 Web 可选依赖的问题，测试矩阵会安装 `.[web]`，避免 `alembic`、`sqlalchemy`、`fastapi` 等模块在收集 `tests/web/*` 时缺失。

## [0.39.2] - 2026-05-11

### Fixed

- 修复首页 UI 图片安全抠底时的整数溢出问题，避免深色边框、面板内部和按钮内容被误当作背景扣除。
- 重新从高清源图生成首页 UI PNG，并同步更新生命条、对话框、任务牌、金币计数器和菜单标签的展示尺寸。

## [0.39.1] - 2026-05-11

### Fixed

- 对首页 UI 素材中边缘偏软或碎点较多的生命条、对话框、任务牌、金币计数器和菜单标签补硬边/暗色描边，并清理外侧孤立噪点，提升透明背景上的可读性。

## [0.39.0] - 2026-05-11

### Changed

- 从最近生成的高清源图重新像素化首页 8 张像素 UI 素材，改用更大的目标尺寸与更高颜色数，以更接近原图细节和材质效果。
- 更新首页像素 UI 展示尺寸：方形控件提升到 128×128，横条、标签和面板提升到 240–256px 级别，避免浏览器按旧尺寸压缩新资源。

## [0.38.0] - 2026-05-11

### Added

- `pix asset` 新增 Pixel Grid 画布贴合后处理，支持 `--fit-canvas/--no-fit-canvas`、`--fit-mode smart|contain|stretch`、`--fit-padding` 和 `--fit-min-axis-coverage`，让非方形 UI 元件按目标画布尺寸自适应填充。
- `pix asset` 默认启用 Grid 轮廓和画布贴合，按钮、条形、面板等 UI 素材会获得更硬的边界和更稳定的有效像素覆盖率。

### Changed

- 使用修复后的 `pix asset` 重新生成首页 8 张像素 UI 素材，生命条、金币计数器、菜单标签和对话框的高度覆盖率显著提升。

## [0.37.0] - 2026-05-11

### Changed

- 再次使用 `pix asset` 优化首页 UI 作品的有效像素覆盖率，将生命条、金币计数器、菜单标签、对话框和任务牌调整到更贴合内容的画布尺寸。
- 更新首页 UI 展示元数据和说明文案，强调素材按有效像素贴合画布展示，减少空白浪费。

## [0.36.0] - 2026-05-11

### Changed

- 重新用 `pix asset` 按真实 UI 用途生成多尺寸首页 UI 作品：方形控件使用 96×96，横向条和标签使用 128×64/160×64，面板类使用 160×96。
- 更新首页像素 UI 展示区，让不同宽高比的 UI 素材按真实尺寸和跨列布局展示，避免统一压成 64×64 导致细节糊掉。

## [0.35.0] - 2026-05-11

### Added

- 新增首页“像素 UI 套件”展示区，展示背包格、技能按钮、生命条、对话框、任务牌、金币计数器、菜单标签和确认勾选等 UI 作品。
- 使用项目自带 `pix asset` 管线生成 8 张 64×64 像素 UI PNG，并通过 `pix validate` 校验。

## [0.34.1] - 2026-05-11

### Fixed

- 使用项目自带 `pix asset` 管线重新生成首页 12 张 64×64 像素素材，替换先前非 Pix 管线生成的占位 PNG。

## [0.34.0] - 2026-05-11

### Changed

- 生成 12 张 64×64 首页像素素材 PNG，并将首屏素材包看板从 CSS 方块图替换为真实图片资源。

## [0.33.0] - 2026-05-11

### Changed

- 将首屏右侧能力卡改为像素素材包看板，加入 RPG 道具缩略图、状态标签、失败重试和 ZIP 导出语境，强化游戏创作者工具调性。
- 登录后用紧凑工位状态条替代大型营销 Hero，让生产工作台、作品库和素材包内容更快进入首屏。
- 收敛素材包卡片动作层级，新增完成进度条，并将重命名、归档、删除等次要操作放入更多菜单。
- 批量生产新增点数冻结摘要、余额不足保护、10 个以上任务提交确认和失败退回说明。
- 统一用户可见文案，将 Prompt、Credits、VL 分析、worker 等开发态词替换为素材描述、点数、参考图理解和后台生产服务。

## [0.32.0] - 2026-05-11

### Changed

- 按 PackyAPI 首页骨架重构未登录体验，新增固定顶部导航、左右分栏首屏、一屏一章节的落地页结构。
- 将 Pix 首屏改为产品定位、Prompt 生产管线展示、CTA、指标卡和右侧能力卡组合。
- 新增核心价值、三步工作流、素材生态和最终登录 CTA sections；登录后仍直接展示控制台摘要与当前工作页。

## [0.31.1] - 2026-05-11

### Fixed

- 隐藏顶部导航 Tab 的原生横向滚动条，并微调胶囊 Tab 宽度，避免导航栏出现突兀滚轮。

## [0.31.0] - 2026-05-11

### Changed

- 将主页面切换 Tab 移入顶部 sticky 导航栏，登录后不再在内容区重复显示导航。
- 将账号管理、可用点数/队列状态与退出登录集中到顶部导航栏右侧，新增账号管理菜单和快捷入口。
- 登录后隐藏独立账户卡，未登录时保留登录/注册表单并提供顶部登录/注册链接锚点。

## [0.30.0] - 2026-05-11

### Changed

- 根据 `DESIGN.md` 将前端整体视觉调整为 Notion 式浅色画布、白色 sticky nav、深蓝 hero band 和紫色主 CTA。
- 重写 MUI theme token，统一 8px 矩形按钮、12px 卡片、Notion-Sans 字体栈、hairline 边框和 pastel feature card 色板。
- 优化登录、工作台、作品库、素材包、点数中心和管理后台的卡片层级、状态徽章、空态与上传/微调区域。

## [0.29.0] - 2026-05-11

### Changed

- 将登录、生产表单、批量上传、任务队列、素材包、微调面板和页面骨架全部迁移到 MUI 组件体系。
- 将作品网格、点数中心和管理后台中剩余的布局 class 收敛到 MUI `sx`，移除对 legacy panel/grid 样式的依赖。
- 大幅精简 `styles.css`，只保留页面基础背景、code 色彩和 reduced-motion 兜底。

## [0.28.0] - 2026-05-11

### Added

- 前端接入 MUI 与 Emotion，新增 Pix Forge 深色主题并统一 App Shell / 导航 / 作品卡片 / 点数中心 / 管理后台的组件体系。

### Changed

- 移除 `styles.css` 中对 `button`、`input`、`select`、`textarea` 的全局样式污染，避免覆盖 MUI 组件状态。
- 点数中心和管理后台改用 MUI Card、Tabs、Accordion、TextField 和 Button 渐进重构，复杂表单逻辑保持不变。

## [0.27.0] - 2026-05-10

### Added

- 前端新增主导航 Tab，将生产工作台、作品库、素材包、点数中心和管理后台拆成独立页面。
- 管理后台新增内部 Tab：概览、用户与点数、价格规则、运营保护。

### Changed

- `App.tsx` 从单页堆叠式工作台重构为 hash 页面路由。
- 管理员功能从普通工作台右侧面板中移出，成为独立管理后台页面。

## [0.26.1] - 2026-05-10

### Fixed

- 本地开发 API CORS 支持 Vite 自动切换端口，避免 `5173` 被占用后前端在 `5174+` 注册/登录显示 `Failed to fetch`。

## [0.26.0] - 2026-05-10

### Added

- 作品网格新增本地分页，减少大型作品库一次性渲染压力。
- 前端轮询增加失败退避，避免后端异常时持续高频请求。
- 点数账户订单与流水改为渐进折叠，降低移动端信息密度。

### Changed

- 作品和素材包卡片改为显式“选择/查看”按钮，避免可点击卡片内嵌按钮的复合交互语义。
- 微信支付备用链接改为复制按钮和折叠详情展示。
- 进一步收敛前端主题色 token，减少硬编码颜色。

## [0.25.0] - 2026-05-10

### Added

- 前端工作台增加键盘可访问的作品/素材包卡片、可见焦点样式和 aria 状态提示。
- 图片预览增加懒加载和异步解码，轮询在页面隐藏时暂停。
- 移动端触控目标和信息顺序优化，新增 reduced-motion 适配。
- 整理深色像素工坊主题 token 和排版 token，清理未使用旧组件。

## [0.24.0] - 2026-05-10

### Added

- 接入支付宝电脑网站支付 checkout 和异步通知验签到账。
- 接入微信支付 API v3 Native checkout、回调验签、AES-GCM 解密和幂等到账。
- 前端点数中心新增支付宝支付、微信扫码支付入口。
- `pix-web-check` 增加支付宝/微信支付配置完整性检查。

## [0.23.0] - 2026-05-10

### Added

- 新增 `pix-web-check` 上线前环境检查命令，检查 JWT secret、Packy API key、数据库、Alembic head、存储目录和队列后端。
- README 新增上线前 checklist，覆盖迁移、配置、存储持久化和生产队列设置。

## [0.22.0] - 2026-05-10

### Added

- 新增管理员运营统计 Dashboard，展示今日任务、成功/失败、排队/运行、充值/消费 credits、上传数、总用户数和失败率。

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

[Unreleased]: https://github.com/zhibeigg/pix/compare/v0.42.0...HEAD
[0.42.0]: https://github.com/zhibeigg/pix/compare/v0.41.2...v0.42.0
[0.41.2]: https://github.com/zhibeigg/pix/compare/v0.41.1...v0.41.2
[0.41.1]: https://github.com/zhibeigg/pix/compare/v0.41.0...v0.41.1
[0.41.0]: https://github.com/zhibeigg/pix/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/zhibeigg/pix/compare/v0.39.3...v0.40.0
[0.39.3]: https://github.com/zhibeigg/pix/compare/v0.39.2...v0.39.3
[0.39.2]: https://github.com/zhibeigg/pix/compare/v0.39.1...v0.39.2
[0.39.1]: https://github.com/zhibeigg/pix/compare/v0.39.0...v0.39.1
[0.39.0]: https://github.com/zhibeigg/pix/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/zhibeigg/pix/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/zhibeigg/pix/compare/v0.36.0...v0.37.0
[0.36.0]: https://github.com/zhibeigg/pix/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/zhibeigg/pix/compare/v0.34.1...v0.35.0
[0.34.1]: https://github.com/zhibeigg/pix/compare/v0.34.0...v0.34.1
[0.34.0]: https://github.com/zhibeigg/pix/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/zhibeigg/pix/compare/v0.32.0...v0.33.0
[0.32.0]: https://github.com/zhibeigg/pix/compare/v0.31.1...v0.32.0
[0.31.1]: https://github.com/zhibeigg/pix/compare/v0.31.0...v0.31.1
[0.31.0]: https://github.com/zhibeigg/pix/compare/v0.30.0...v0.31.0
[0.30.0]: https://github.com/zhibeigg/pix/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/zhibeigg/pix/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/zhibeigg/pix/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/zhibeigg/pix/compare/v0.26.1...v0.27.0
[0.26.1]: https://github.com/zhibeigg/pix/compare/v0.26.0...v0.26.1
[0.26.0]: https://github.com/zhibeigg/pix/compare/v0.25.0...v0.26.0
[0.25.0]: https://github.com/zhibeigg/pix/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/zhibeigg/pix/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/zhibeigg/pix/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/zhibeigg/pix/compare/v0.21.0...v0.22.0
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
