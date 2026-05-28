# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.43.132] - 2026-05-26

### Fixed

- 修复锚点调整编辑器选中最后一帧时半透明影子显示为第 1 帧的问题；现在任意帧都显示它的上一帧，第 1 帧则显示最后一帧。

## [1.43.131] - 2026-05-26

### Added

- 作品库新增“参数”快览入口，可快速查看每个作品的 prompt、模型、像素化、素材直出、序列帧、计费快照与输出文件路径。
- 作品卡片展开状态增加关键生成参数标签，如尺寸、颜色数、模型、帧数和 FPS，便于快速比较作品。
- 参数快览支持一键复制完整 JSON 快照，方便复现生成或排查问题。

## [1.42.131] - 2026-05-26

### Fixed

- 修复图生图/本地像素化上传成功后预览区域显示破图的问题：上传接口返回的 `/files` 相对地址现在会在前端转换为带 API Base 与 token 的可访问地址。

## [1.42.130] - 2026-05-26

### Added

- 新增序列帧锚点调整编辑器：可逐帧拖动主体位置，叠加半透明 onion-skin 影子，并实时预览调整后的动画。
- 新增 `/jobs/{job_id}/sequence-alignment` 本地重合成接口，保存每帧偏移并生成新的 `sprite_sheet.png`、`sequence.json` 与可选 GIF，不重新生图也不额外扣点。

### Changed

- 作品库的序列帧作品增加“调整锚点”入口；保存后作品库自动切换到调整版本。
- 前端 422 错误提示现在会展示字段级校验原因，不再只显示“请求失败 (422)”。
- `/files` 下载允许访问生成的 `.json`、`.txt` 与 `.gif` 产物，便于下载 `sequence.json` 和动画预览。

## [1.41.130] - 2026-05-26

### Changed

- 将 `sprite_sheet` 任务彻底替换为逐帧序列帧流程：首帧文生图，后续逐帧图生图，最终输出 `sprite_sheet.png` 与 `sequence.json`。
- 作品库、队列和微调工位改为优先使用横向精灵表加帧坐标播放序列帧，不再默认依赖 GIF。
- 序列帧计费改为“帧数 × 单帧基础价”，用户可选 1-12 帧，前后端均校验上限。
- 更新 `[sprite]` 配置、后台设置、前端创建表单与下载项，补充帧数、FPS、有效尺寸和清单导出字段。

## [1.40.130] - 2026-05-26

### Changed

- 调整九宫格动画后处理为整表 `perfectPixel -> Color-to-Alpha`，再等分切 9 帧并透明补到目标/预设帧尺寸。
- 横向精灵表与 GIF 现在直接使用等宽高最终帧合成，作品库继续优先播放 `sprite_gif_url` 作为序列帧预览。
- 更新 sprite 文档和后台设置说明，标注 `crop_*` 为历史兼容字段。

## [1.40.129] - 2026-05-26

### Changed

- 强化九宫格动画 prompt 的单帧尺寸合同：按用户选择的导出尺寸写入每帧 `{width}x{height}`、整表 `{sheet_width}x{sheet_height}` 以及每帧逻辑坐标范围。
- `00_input.txt` 现在记录 raw prompt、归一化描述、sprite 设置、帧坐标和完整 effective prompt，便于排查生图规则是否生效。

## [1.40.128] - 2026-05-26

### Changed

- 强化九宫格动画精灵表 prompt 模板，使其与 asset 模板同样明确要求 TRUE pixel-art、单帧尺寸、像素格、颜色上限、纯色 key 背景、禁止抗锯齿和稳定锚点。
- 更新示例配置与 README，说明 sprite 模板的额外连续帧约束。

## [1.40.127] - 2026-05-26

### Changed

- 九宫格动画精灵表切帧后改为逐帧执行 `perfectPixel -> Color-to-Alpha` 背景处理，再统一 bbox 裁剪与像素化。
- 在 sprite 元数据中记录 `frame_background_flow=perfect_pixel_to_color_to_alpha`，便于追踪序列帧后处理链路。

## [1.40.126] - 2026-05-26

### Changed

- 调整邀请链接生成与根路径 `aff` 跳转，优先指向前端登录面板。
- 修复删除确认弹窗在视口中的居中和宽度约束，并加入 GIMP Color-to-Alpha 参考实现目录。

## [1.40.125] - 2026-05-26

### Changed

- 使用固定 Color-to-Alpha 后处理全量重跑 608 个主页展示物品图标，并以最新 visual 输出替换主页展示资源。
- 同步更新主页图标实际 PNG 尺寸映射。

## [1.40.124] - 2026-05-26

### Changed

- 背景移除默认固定使用四角纯色作为 key 的 Color-to-Alpha 路径，不再从 auto 回退到 flood-fill。
- 更新默认配置、示例配置与文档，明确 `bg_removal_algorithm` 使用 `color_to_alpha`。

## [1.40.123] - 2026-05-26

### Fixed

- 修复 PerfectPixel 后 chroma-key 角点轻微波动时错误退回 flood-fill 的问题，避免将贴边主体暗色作为背景 seed 误删主体边缘。
- 重新以后处理结果替换主页 `06_sanguo_item_01` 青龙偃月刀图标，并同步图标尺寸映射。

## [1.40.122] - 2026-05-26

### Fixed

- 修复 PerfectPixel center sample 在边界网格上可能访问越界的问题，避免回退到强制 64x64 采样。
- PerfectPixel 外部后端失败后的内置回退改为继续自动检测网格，保持与 webdemo 更一致的输出尺寸。

## [1.40.121] - 2026-05-26

### Fixed

- 重新生成缺失的主页示例物品 `68_sea_item_07` visual 图标，并替换主页展示 PNG 与尺寸映射。

## [1.40.120] - 2026-05-26

### Changed

- 将主页展示用物品图标替换为最新重处理的 `visual` 输出，并按 PNG 实际尺寸同步前端图标尺寸映射。

## [1.40.119] - 2026-05-25

### Changed

- 删除 Pixel Grid 采样后的边缘连通背景兜底步骤；AI 纯色 key 背景以 Color-to-Alpha 结果为准，避免后续推断再次破坏主体。

## [1.40.118] - 2026-05-25

### Fixed

- 修复 Pixel Grid 第 7 步边缘连通背景兜底误删主体的问题：当 Color-to-Alpha 已经产生足够透明背景时，跳过二次边缘背景推断，避免主体贴边像素被当成背景删除。

## [1.40.117] - 2026-05-25

### Changed

- AI 生成图每次执行 perfect pixel 预处理时，都会在 run 目录保存 `02_perfect_pixel_preprocess.png`，并在 `meta.outputs.perfect_pixel_preprocess` 中记录。

## [1.40.116] - 2026-05-25

### Changed

- 将 GIMP Color-to-Alpha 风格算法内置为 AI 纯色 key 背景的默认去背景路径，保留普通 flood-fill 作为非 chroma-key 场景回退。
- 新增 `bg_removal_algorithm` 与 Color-to-Alpha 阈值配置，统一 Pixel Grid 与传统 pixelize 两条路径的背景移除行为。

## [1.40.115] - 2026-05-25

### Fixed

- 收紧 key-color soft matte 的候选条件，只清理具有 key 色通道方向的混色边缘，避免灰白/金属扇面因与品红欧氏距离较近而被误删。

## [1.40.114] - 2026-05-25

### Fixed

- 调整 `n_sample` 候选处理：候选与 `01_source.png` 保持模型原始返回图，不再提前 key 色抠图/裁剪；后续 pixelize 的第一步始终是 perfect pixel。
- contact-sheet 候选元数据新增 perfect pixel 中间图与预处理信息，便于调试区分候选图和最终像素化 source。

## [1.40.113] - 2026-05-25

### Fixed

- 强化 key-color soft matte 清理策略，对贴近透明背景的高 alpha 混色粉/灰边缘直接硬清理，避免放大后仍能看到品红残留。

## [1.40.112] - 2026-05-25

### Fixed

- 背景移除增加 key-color soft matte / despill，修复纯色背景经抗锯齿或缩放后形成的半透明、混色品红边缘无法被去除的问题。

## [1.40.111] - 2026-05-25

### Changed

- 继续精简素材与候选图 prompt，移除额外的简洁性强调句，只保留基础轮廓、颜色数、像素对齐和背景抠色要求。

## [1.40.110] - 2026-05-25

### Changed

- 精简素材与候选图 prompt，移除 `with very few noisy details` 约束，保留简洁轮廓和像素对齐要求。

## [1.40.109] - 2026-05-25

### Fixed

- 素材 prompt 模板按 `asset_kind` 分流：物品图标不再同时出现 UI 语义，UI 组件不再混入物品/背包语义；旧 `inventory/UI use` 模板会在构建时自动转换为类型感知占位符。
- 候选图 n-sample/contact-sheet 包装模板改为通用 generation brief，不再额外写死 `inventory/UI use` 或 `game UI`。

## [1.40.108] - 2026-05-25

### Changed

- 主页示例 icon 生成参数改为无额外边缘处理：默认 `edge_style=hard`、`bg_feather=0`，不再使用 `outline` 描边。
- 用无描边参数重新走真实网站素材生成流水线生成前 3 个武侠物品 icon，并同步最终 PNG 真实尺寸映射。

## [1.40.107] - 2026-05-25

### Fixed

- 修复网站素材流水线加载像素化预设时缺少 `sys` 导入导致无法启动的问题。

### Changed

- 按 `homepage示例物品icon清单.md` 重新走真实网站素材生成流水线生成前 3 个武侠物品 icon，并覆盖主页静态 PNG。

## [1.40.106] - 2026-05-25

### Changed

- 仓库收敛为网站版：保留 React 前端、FastAPI 后端、Web worker、数据库迁移与网站素材生成核心，移除历史 CLI/GUI、测试、旧静态素材、临时输出和打包/部署杂项。
- README 合并 prompt 构建规则，明确网站 asset 直出必须走 `build_asset_prompt`、本地 prompt guard、`gpt-image-2` 单图、生图后 Pixel Grid extract 的当前流水线。
- 主页示例区移除旧 UI、64×64/32×32 对比字段，只保留现行全流程生成的物品 icon 与真实最终 PNG 尺寸。
- 后端依赖与 Docker 镜像改为网站运行所需集合，并把 `assets/presets` 一并复制进镜像。

## [1.39.106] - 2026-05-25

### Added

- 新增 `scripts/generate_homepage_item_icons_from_manifest.py`，可按 `homepage示例物品icon清单.md` 逐个走真实 Pix 全流程重生成 608 张主页物品 icon，先写入 staging 并在完整验证后发布。

### Changed

- Web 主页移除旧 UI/精灵图展示素材，只保留全流程重生成的 608 张物品 PNG 图标墙，并同步清理旧静态资源目录引用。

## [1.38.106] - 2026-05-25

### Added

- Web 主页范例区只保留 608 张新版后处理物品 PNG，并新增实际尺寸 tag、题材风格 tag、尺寸/大类/风格筛选器和单图右键下载/复制主体 prompt 操作。

## [1.37.106] - 2026-05-25

### Fixed

- 透明画布补齐改为按预设尺寸档位向上取整，例如 40x40 会补到 48x48，而不是 8 的倍数 40x40。

## [1.37.105] - 2026-05-25

### Added

- 作品网格卡片显示真实生成像素尺寸 tag，并按尺寸区间使用不同颜色区分。

## [1.37.104] - 2026-05-25

### Fixed

- Grid 流程调整为先在完整 perfectPixel 图上去背景，再贴边裁剪主体，避免裁剪后背景参考色被误判。

## [1.37.103] - 2026-05-25

### Fixed

- perfectPixel 贴边裁剪并去背景后不再缩放回用户请求尺寸，改为向上取整到 8 的倍数正方形并用透明像素补画布。

## [1.37.102] - 2026-05-25

### Fixed

- perfectPixel 之后的自动裁剪改为贴住主体边缘的最小 bbox，不再额外 padding 或强制正方形。

## [1.37.101] - 2026-05-25

### Fixed

- 调用 `perfectPixel-main` 时不再强制传入目标输出尺寸，改为与官方演示一致自动检测网格，再由后续 Pixel Grid 提取归一到用户选择尺寸。

## [1.37.100] - 2026-05-25

### Fixed

- AI 生图本地处理顺序改为先执行 `perfectPixel-main` 的 perfectPixel 网格对齐，再裁剪、去背景和提取 Pixel Grid。

## [1.37.99] - 2026-05-25

### Fixed

- 背景去除在四角 key background 存在轻微明暗波动时仍按单一背景处理，避免实际生图的品红背景整张残留。

## [1.37.98] - 2026-05-25

### Fixed

- 背景去除会同步清理与边缘背景色相同、但被主体轮廓封闭的孔洞区域，避免茶壶把手等闭环内残留纯色背景块。

## [1.37.97] - 2026-05-25

### Fixed

- Asset Prompt 不再固定写入 `#FF00FF` 等背景 HEX，改为要求模型选择与主体颜色距离足够远的纯色背景，并按用户实际选择的颜色上限填充 `{max_colors}` / `{colors}`。

## [1.37.96] - 2026-05-25

### Fixed

- Asset 全模板 Prompt 审核改为只按用户原始主体/描述计算长度，模板内容不计入本地长度限制。

## [1.37.95] - 2026-05-25

### Fixed

- 放宽 asset 全模板 Prompt 的本地审核长度上限，避免 `prompt构建.md` 标准英文模板在 Web/CLI 全流程中因超过 500 字符被拒绝。

## [1.37.94] - 2026-05-25

### Fixed

- 以 `prompt构建.md` 为准恢复素材直出 TRUE pixel-art 英文模板，并为 Web/CLI asset prompt 正确填充动态 `{green}` 与 `{key_tolerance}`。

## [1.37.93] - 2026-05-25

### Fixed

- 统一素材直出 Prompt 为主页示例清单同款中文模板，确保 Web/CLI 生成记录使用 `主体：{name}` 结构而不是旧英文模板。

## [1.37.92] - 2026-05-25

### Changed

- 重新从 64x64 单图源资源批量后处理首页展示的 608 张 32x32 outline 物品图标，使用当前 perfectPixel 生成图网格预处理和 Pixel Grid outline 流程。

## [1.36.92] - 2026-05-25

### Changed

- 将默认生图 prompt 从物理拼豆表述调整为像素游戏素材语义，保留 `{width}x{height}` 动态尺寸、网格对齐和无抗锯齿约束。

## [1.35.92] - 2026-05-25

### Changed

- 将生图/图生图与素材直出的默认 prompt 优化为 TRUE perler bead 物理拼豆图案约束，并按实际目标尺寸自动填充 `{width}x{height}`（如 16x16/32x32/64x64）。

## [1.34.92] - 2026-05-25

### Changed

- AI 生图/图生图源图在进入像素化或 Pixel Grid 提取前默认启用内置 perfectPixel 风格网格对齐预处理，按目标尺寸进行 FFT/Sobel 网格采样；本地上传像素化默认保持旧流程。

## [1.33.92] - 2026-05-24

### Changed

- CLI/Web 候选生图 prompt 的 RGB 容差约束改为“保持在最大色容差之外”语义，`{key_tolerance}` 作为当前抠色最大容差边界写入模板和 fallback prompt。

## [1.32.92] - 2026-05-24

### Fixed

- Web 删除确认弹窗使用专用视口居中样式，避免通用 Dialog 动画 transform 导致位置偏移。

## [1.32.91] - 2026-05-24

### Fixed

- Web 邀请链接生成优先使用前端公开地址，并在仅配置后端 `/api` 公开地址时自动去除 `/api` 前缀；兼容已发出的 `/api/?aff=...` 旧链接，自动重定向到前端注册锚点。

## [1.32.90] - 2026-05-24

### Fixed

- Web 系统公告弹窗改为直接使用 Radix 原始 Content 与内联 fixed 居中样式，绕开通用 DialogContent 默认定位和动画影响。

## [1.32.89] - 2026-05-24

### Fixed

- Web 首页加载到新的已启用系统公告时会自动弹出公告弹窗，并按公告内容与更新时间记录已读状态，避免同一条公告重复弹出。

## [1.32.88] - 2026-05-24

### Fixed

- Web 系统公告弹窗使用专用视口居中样式，避免继承通用 Dialog 宽度和动画 transform 后仍偏向页面左侧。

## [1.32.87] - 2026-05-24

### Changed

- Web 系统公告弹窗强制按视口居中，并接入后端公开公告接口；管理后台新增“系统公告”发布表单，可发布、保存草稿或下线全站公告。

## [1.31.87] - 2026-05-24

### Changed

- Web 作品和空素材包删除确认改为 Pix Forge 风格站内弹窗，替代浏览器原生 confirm，并补充删除影响说明与中英文文案。

## [1.30.87] - 2026-05-24

### Changed

- Web 前端取消 reduced-motion 动效无障碍分支，按钮、表单、加载态、页面进入与环境流动动效现在始终启用。

## [1.29.87] - 2026-05-24

### Changed

- Web/CLI 候选生图 prompt 模板新增 `{key_tolerance}` 约束，构建时填入当前 `green_screen_tolerance`，要求主体可见颜色与 key background 保持足够 RGB 欧氏距离，降低后处理抠色误伤。

## [1.28.87] - 2026-05-24

### Fixed

- Web 首页范例物品右键复制现在真实复制 `主体：` 后的 subject prompt 描述片段，并在菜单中直接展示将复制的内容，避免只复制物品名。

## [1.28.86] - 2026-05-24

### Fixed

- Web 首页范例物品右键复制文案与实现改为复制 `主体：` 后面的 subject prompt 片段，而不是表达为复制主体名。

## [1.28.85] - 2026-05-24

### Added

- Web 首页范例图谱新增单个物品格右键菜单，可下载指定 64×64 / 32×32 outline 案例图；复制时只复制该槽位 `主体：` 后面的 subject prompt 片段，悬浮详情保留物品组和 UI 展示图下载入口，并补齐 171 个原待补名范例物品主体。

## [1.27.85] - 2026-05-24

### Fixed

- Web 首页 32×32 outline 范例资源改用新的静态目录，避免部署后浏览器或 CDN 复用旧 `/homepage-examples/items/` 缓存导致两组图片看起来相同。

## [1.27.84] - 2026-05-24

### Fixed

- Web 首页范例图谱悬浮详情改为 requestAnimationFrame 更新位置，并缓存分组与卡片渲染，避免鼠标移动时反复触发整块图谱重渲染。

## [1.27.83] - 2026-05-24

### Fixed

- Web 首页范例图谱恢复展示原 64×64 物品资源，并与新 32×32 outline 图标并列对比，避免只展示小图标却缺少原高像素资源。

## [1.27.82] - 2026-05-24

### Fixed

- 支付宝支付完成返回页不再暴露 JSON，后端会安全重定向到 Pix 前端充值页并触发前端刷新订单状态；新增 `PIX_WEB_FRONTEND_BASE_URL` 配置用于前后端不同域名部署。

## [1.27.81] - 2026-05-24

### Added

- 素材直出 prompt 构建改为“尺寸 + 素材类型 + 主体类型 + 主体”结构，用户只需填写 `主体：` 后面的主体内容；Web 单张/批量表单仅保留物品图标 / UI 组件一个选择，主体类型由素材类型自动匹配。

## [1.26.81] - 2026-05-23

### Fixed

- 修复 RQ 部署下“Worker 并发上限”不生效的问题：`pix-web-rq-worker` 现在会按后台/环境变量并发上限启动多个独立 RQ worker 子进程。
- Web 任务流水线新增本地处理阶段文件锁，让生图/图生图等网络等待并发执行，同时将候选拆图、像素化、精灵帧处理和写盘阶段串行化，避免高并发压垮本地 CPU/磁盘。

## [1.26.80] - 2026-05-23

### Fixed

- 修复 Web 素材直出/Pixel Grid extract 路径中“描边”和“羽化边缘”只记录参数但未实际影响最终输出的问题：描边现在会应用到 Grid 后处理，羽化会应用到最终透明 PNG。

## [1.26.79] - 2026-05-23

### Changed

- Web 加载动画简化为单一旋转进度环、中心呼吸点和轻量点点文案，移除多层反向旋转、轨道点、跳动像素和扫光效果，降低视觉干扰。

## [1.26.78] - 2026-05-23

### Fixed

- Web Motion loader 不再因系统减少动态设置完全静止；减弱模式改为降低幅度和速度，仍保留可见的旋转、呼吸和像素点跳动反馈。

## [1.26.77] - 2026-05-23

### Fixed

- Web 预览加载态改用 Motion React 动画库驱动，提供旋转环、反向环、呼吸核心、轨道点和跳动像素点，避免 CSS loader 在部分环境中看起来像静态图标。

## [1.26.76] - 2026-05-23

### Changed

- Web 首页首屏文案改为直接说明目标用户、核心功能、解决的素材生产痛点，以及早期原型可节省的时间和外包沟通成本。

## [1.26.75] - 2026-05-23

### Removed

- Web 首页移除“像素素材生产线”和“提示词/验收/打包助手”两段说明区块及中间统计条，首屏后直接进入可验收的道具、UI、动作帧和范例内容。

## [1.26.74] - 2026-05-23

### Fixed

- Web 预览加载态增加画布扫描、像素追逐、任务卡片呼吸反馈，并在作品库/微调工位优先展示精灵 GIF，避免正常动效环境下仍像静态占位。
- Web 单图上传和批量上传中的占位预览接入同一套动态加载态；在 `prefers-reduced-motion: reduce` 下保留静态扫描提示与省略号兜底。

## [1.26.73] - 2026-05-23

### Fixed

- Web 作品预览加载态改为独立动态 loader，包含旋转环、呼吸光晕、轨道光点和文字点点动画，避免显示为静态图标。

## [1.26.72] - 2026-05-23

### Fixed

- Web 邀请奖励统计区改为专用主题配色类，明确区分浅色模式与深色模式的背景、文字、指标卡和操作按钮颜色，避免主题样式串色。

## [1.26.71] - 2026-05-23

### Fixed

- Web 邀请奖励收益统计区在浅色主题下改为柔和品牌渐变与高对比操作按钮，减少深蓝绿大色块的突兀感。

## [1.26.70] - 2026-05-23

### Fixed

- Web 作品库和任务队列加载态改用 `jobs.status.*` 国际化状态文案，避免显示 `status.pending` / `status.running` key。

## [1.26.69] - 2026-05-23

### Fixed

- Web 动效增强为更可见的点击涟漪、浮动与环境流动效果，并将邀请奖励相关新增文案迁移到 i18n key，避免中英文混用。

## [1.26.68] - 2026-05-23

### Added

- Web UI 新增全局动效层，为按钮、表单、弹层、菜单、表格、面板、页面切换和奖励页关键操作提供轻量微交互，并尊重 reduced-motion 偏好。

## [1.26.67] - 2026-05-23

### Added

- Web 新增邀请奖励页面，支持专属邀请链接、注册归因、充值返佣、待到账/可用收益统计、划转点数余额与提现申请记录。

## [1.26.66] - 2026-05-23

### Added

- Web 像素参数新增“边缘处理”选择，可在描边、羽化边缘和不额外处理之间切换，并在低像素透明素材中尊重用户选择。

## [1.26.65] - 2026-05-23

### Fixed

- 排队中和生产中的作品预览改为加载动画，避免继续显示上传图或旧输出图。

## [1.26.64] - 2026-05-23

### Fixed

- Web 页脚 ICP 备案号更新为 `鲁ICP备2022023963号-1`。

## [1.26.63] - 2026-05-23

### Fixed

- 数据库 worker 改为按并发上限领取任务，有空闲槽位时直接并发生成，只有超过上限的任务才保持排队中。

## [1.26.62] - 2026-05-23

### Fixed

- 原始生图预览 URL 统一追加认证 token 与 API 前缀，修复任务成功后画布和最近缩略图无法显示的问题。

## [1.26.61] - 2026-05-23

### Fixed

- 原始生图改为单图直出模式：一次只调用 1 张原图，跳过候选图、VL 评分、抠图和像素化后处理，前端不再提供多张变体入口。

## [1.25.58] - 2026-05-23

### Fixed

- 作品卡片预览图改为绝对限制在顶部预览框内，保持比例缩放且不越过信息区。

## [1.25.57] - 2026-05-23

### Changed

- 素材包面板改为资源管理器式命令栏与文件夹列表，支持单击打开、顶部操作和内联重命名。

## [1.25.56] - 2026-05-23

### Fixed

- 素材包数量扩容确认改为站内主题化弹窗，替代浏览器原生提示框。

## [1.25.55] - 2026-05-23

### Fixed

- 作品库卡片预览图取消额外缩小限制，按原图比例尽量缩放至预览边框内。

## [1.25.54] - 2026-05-23

### Fixed

- 下拉菜单默认改为非模态，避免打开更多菜单时页面因滚动锁补偿发生横向抖动。

## [1.25.53] - 2026-05-23

### Fixed

- 作品库卡片预览图按方格区域自适应缩放，避免像素图在预览格内顶满或贴边。

## [1.25.52] - 2026-05-23

### Fixed

- 素材包与批次 ZIP 内部文件名前缀改为“作品名_ID”，避免同名作品导出时难以区分。

## [1.25.51] - 2026-05-23

### Added

- 作品库新增手动删除作品能力，删除时同步清理输出目录、素材包引用和点数流水关联。

## [1.25.50] - 2026-05-23

### Fixed

- 素材包扩容改为增加可创建素材包数量；单个素材包默认容量调整为 100 个作品。

## [1.25.49] - 2026-05-23

### Fixed

- 收紧作品网格卡片尺寸，并缩小透明棋盘背景方格，提升大屏作品库密度。

## [1.25.48] - 2026-05-23

### Fixed

- 下载弹窗不再提供预览图下载；单文件下载以作品/物品名作为文件名前缀。

## [1.25.47] - 2026-05-23

### Added

- 新增用户手动素材包，支持新建、命名、归档、ZIP 下载，以及从作品库拖入作品永久保存。
- 素材包新增数量与容量上限：每个素材包默认最多保存 100 个作品，素材包数量扩容 +1 消耗 99 点并写入点数流水。

### Changed

- 批量生成不再自动创建素材包，结果统一进入作品库；需要长期保存的作品可手动加入素材包。
- 作品库自动清理会跳过已保存到素材包的作品，避免永久素材被清理。
- 前端下载和上传列表不再展示文件名或本地/服务端文件目录。

## [1.24.47] - 2026-05-22

### Changed

- 后端支付宝电脑网站支付改用官方 `alipay-sdk-python` 生成支付链接并进行回调验签，保留公钥模式与证书模式配置。
- Web 运行依赖新增 `alipay-sdk-python>=3.7.1160`，避免继续手写支付宝请求签名流程。

## [1.24.46] - 2026-05-22

### Changed

- Web 高频导航、账户菜单、素材包、队列、作品库和点数中心文案继续迁移到 `i18next` / `react-i18next` 翻译键，减少 `text(zh, en)` 兼容写法。
- 明暗主题说明统一为 Tailwind `dark` class、Radix 组件与 CSS 变量 token 体系，避免为黑白模式新增分散特例。

## [1.18.29] - 2026-05-22

### Added

- Web 账户作品库最多保留最新 10 张成功作品，生成成功后自动清理更旧作品及其输出目录，前端生成前会提示超限清理规则。

## [1.17.29] - 2026-05-22

### Fixed

- 取消 Web 生成任务的每用户排队/运行并发上限，旧 `max_pending_jobs_per_user` 配置仅作为兼容字段保留且不再限制任务提交。

## [1.17.28] - 2026-05-21

### Fixed

- 工作台布局改为全屏应用壳，移除居中 mockup 窗口和登录态页脚，让侧边栏与内容区占满可用屏幕。

## [1.17.27] - 2026-05-21

### Fixed

- 已登录首页的“进入工作台”入口移动到右上角导航区，符合主页返回后的操作预期。

## [1.17.26] - 2026-05-21

### Fixed

- 登录后点击 Logo 现在会进入真实首页路由，首页“进入工作台”按钮可返回生产工作台。

## [1.17.25] - 2026-05-21

### Fixed

- 登录后真实工作台改为与首页 workspace mockup 一致的深海军蓝侧边栏布局，主导航迁移到左侧工作区。

## [1.17.24] - 2026-05-21

### Fixed

- 修复首页序列帧浅色展示卡在深色主题下文字对比度不足，并避免帧数徽章被压缩换行。

## [1.17.23] - 2026-05-21

### Fixed

- Web 前端界面严格对齐 `apps/web/DESIGN.md` 的 Notion 式规范，统一 Notion-Sans 字体、深海军蓝 Hero、紫色主 CTA、12px 卡片、8px 按钮、浅色 Surface 与 pastel feature cards。

## [1.17.22] - 2026-05-21

### Fixed

- Web 主题 token 统一对齐 `apps/web/DESIGN.md` 的 Canvas White / Brand Navy / Ink / Primary Purple 配色，并将状态徽章改为 white/dark 高对比底色。

## [1.17.21] - 2026-05-21

### Fixed

- 提高浅色主题下语义徽章、描边按钮和主色文本对比度，修复队列/任务等状态提示看不清的问题。

## [1.17.20] - 2026-05-21

### Fixed

- 主题模式下拉菜单改为非 modal，避免打开/切换时触发页面滚动锁补偿导致整体左右晃动。

## [1.17.19] - 2026-05-21

### Fixed

- 本地前端从 `127.0.0.1` 打开时自动改走 `localhost` API 代理，兼容 Windows 上不同 loopback 主机名的后端绑定差异。

## [1.17.18] - 2026-05-21

### Fixed

- 首页序列帧播放器改为 React 定时切换真实帧 PNG，避免 CSS 背景 steps 动画在部分环境中不播放。

## [1.17.17] - 2026-05-21

### Added

- 点数充值新增自定义点数数量，后端按启用基准套餐派生单价并重新计算金额，支持支付宝支付和管理员模拟支付。

## [1.16.17] - 2026-05-21

### Fixed

- 首页登录/注册卡片仅保留一处新人注册赠送点数提示，注册切换按钮恢复为本质化“注册”。

## [1.16.16] - 2026-05-21

### Fixed

- 首页序列帧示例不再使用 GIF 预览，改为基于横向精灵图的真实逐帧 steps 播放，并在减弱动效模式下静态显示首帧。

## [1.16.15] - 2026-05-21

### Fixed

- 首页登录/注册卡片在注册入口旁动态展示“新人注册赠送 X 点数”，注册表单提示文案同步改为新人赠送口径。

## [1.16.14] - 2026-05-21

### Fixed

- 首页序列帧展示新增“黑紫魔气爆炸特效”9 帧 VFX 示例，并补齐横向精灵图、GIF 预览和帧源图资源。

## [1.16.13] - 2026-05-21

### Added

- 新增支付宝开放平台应用网关消息接收接口 `/billing/webhook/alipay/app-gateway`，支持 RSA2/证书模式验签、`notify_id` 幂等入库和 `success` 文本响应。

## [1.15.13] - 2026-05-21

### Fixed

- 兼容本地 Docker / Nginx 反向代理访问时的本地测试账号判定，并让注册页同样展示本地测试账号入口。

## [1.15.12] - 2026-05-21

### Fixed

- 新增仅本地访问时可用的测试账号入口，后端限制本地请求与本地 token 使用范围，同时保持登录/注册/初始化表单不预填测试内容。

## [1.15.11] - 2026-05-21

### Fixed

- 移除登录/注册表单的默认预填邮箱、密码和昵称，避免工作台入口展示测试账号内容。

## [1.15.10] - 2026-05-21

### Fixed

- 清理动画精灵帧主体外缘的半透明 key-color 残留，减少深色背景/棋盘格预览中的紫色背景脏边，并重新处理首页月刃骑士示例资源。

## [1.15.9] - 2026-05-21

### Changed

- 优化首页范例图库：左侧题材卡片放大并显示完整名称，详情面板改为跟随鼠标悬浮展示，同时移除底部文件名展示。

## [1.15.8] - 2026-05-21

### Fixed

- 恢复首页序列帧展示区，重新展示月刃骑士挥剑的播放预览、横向精灵图、9 帧拆分、3×3 源图和 GIF 预览。

## [1.15.7] - 2026-05-21

### Fixed

- 恢复首页的生产线优势、数据条、像素 UI 展示、76 套题材范例图库与登录引导内容，并适配 shadcn/Tailwind 新视觉体系。

## [1.15.6] - 2026-05-21

### Added

- 前端全面迁移到 shadcn/ui + Radix primitives + Tailwind CSS 组件体系，移除 MUI/Emotion 依赖并新增 Pix 专属设计组件层。

### Changed

- 重构全局壳层、导航、登录、生产工作台、原始生图、作品库、素材包、点数中心和管理后台的视觉层级与控件布局。

## [1.14.6] - 2026-05-21

### Fixed

- 优化作品库和微调工位视觉层级，收紧右侧参数控件布局，改善空预览、状态角标和卡片操作区展示。

## [1.14.5] - 2026-05-21

### Fixed

- 优化像素参数颜色数控件，移除滑块下方密集刻度数字，改为简洁滑块、数字输入和常用色数快捷按钮。

## [1.14.4] - 2026-05-21

### Fixed

- 修复原始生图页在没有历史原图任务时错误读取空预览覆盖对象导致页面崩溃无法打开的问题。

## [1.14.3] - 2026-05-21

### Fixed

- 修复 Web 下拉菜单打开时锁定页面滚动条导致的横向抖动，菜单弹出不再改变页面滚动条占位。

## [1.14.2] - 2026-05-21

### Added

- 作品库失败任务新增单任务重试按钮，并提供 `POST /jobs/{job_id}/retry` 后端接口，重试后按当前价格重新冻结点数并入队。

## [1.13.2] - 2026-05-21

### Added

- Web 工作台像素参数控件新增常用尺寸快捷选项，颜色数支持滑块拖动与数字输入同步调节。

## [1.12.2] - 2026-05-21

### Fixed

- 原始生图页增加 API 请求超时和历史任务数据空值防护，避免后端无响应或异常任务数据导致页面一直停在初始化/白屏。

## [1.12.1] - 2026-05-21

### Fixed

- 支付宝证书模式解析根证书包时兼容国密曲线证书，跳过无法加载公钥算法的非 RSA 根证书，避免 `UnsupportedAlgorithm` 中断证书序列号计算。

## [1.12.0] - 2026-05-21

### Added

- Web 后端邮件验证码新增 SMTP 465 implicit SSL 支持，`PIX_WEB_SMTP_PORT=465` 时会默认启用 `PIX_WEB_SMTP_SSL`，并可在管理后台查看/覆盖。
- 支付宝电脑网站支付新增证书模式，支持应用公钥证书、支付宝公钥证书和支付宝根证书配置，下单自动带 `app_cert_sn` / `alipay_root_cert_sn` 并使用证书验签回调。

### Fixed

- 主页移除纵向滚动自动吸附，改为自然页面滚动；锚点跳转保留顶部导航避让，避免内容被挡住。
- 首页物品悬浮详情移除多余预览图，将默认产物文案从 Grid 修正为像素化透明 PNG。
- 首页动画预览与详情右上角均默认使用横向精灵表序列帧播放，不再加载 GIF；源图缩略图去掉填充底色，避免紫色背景块。
- 首页题材范例悬浮详情改为跟随鼠标的 Popper 视口定位，放大详情尺寸并移除内部滚动条，避免弹层超出屏幕且不阻挡切换其他卡片。

## [1.10.0] - 2026-05-16

### Added

- 新用户注册赠送点数功能，默认赠送 30 点，管理员可在系统设置中调整或关闭。

### Removed

- 关闭微信支付功能，前端移除微信支付按钮与二维码区域，后端拒绝微信支付请求。

## [1.8.0] - 2026-05-15

### Changed

- 主页 76 套题材范例的详情弹层改为逐格展示 4×2 物品素材，不再只展示整张物品精灵表。
- 主页范例详情中的物品 Prompt 与 UI Prompt 改为中文说明，便于中文游戏素材生产者直接理解题材与交付规格。

## [1.7.1] - 2026-05-15

### Fixed

- 修复主页 76 套题材范例悬浮详情中 UI 预览拉伸过高、物品精灵表区域出现大片空白的问题。

## [1.7.0] - 2026-05-15

### Changed

- 重构 Web 首页视觉基调，改为更安静的像素工坊主题，降低首屏、登录段落和卡片色块饱和度。
- 76 套题材范例改为首屏素材格同款渐进展示：默认紧凑浏览，悬浮或键盘聚焦时展开物品精灵表、16:9 UI 展示图、Prompt 与文件名。
- 优化登录后生产工作台、作品库、素材包和队列组件的信息密度、空状态和状态表达。

## [1.6.0] - 2026-05-15

### Added

- 主页新增 Pix sprite 全流程动画示例，悬浮或键盘聚焦时播放 9 帧序列帧预览，并展开横向精灵图、逐帧缩略图、源图和中文 prompt。

## [1.5.0] - 2026-05-15

### Changed

- 主页展示图删除上一版手工生成资源，改为 12 个真实 Pix 全流程产物；每个示例均经过 prompt 生图、候选选择、VL 分析、Pixel Grid extract 和像素化预览输出。
- 主页展示文案移除“直出”表述，悬浮详情改为展示全流程源图、Grid 渲染图、预览图和中文 prompt。

## [1.4.0] - 2026-05-15

### Added

- 主页展示物品更换为一组新生成的中文素材示例，并在展示卡中直接呈现中文 prompt。
- 主页素材格新增悬浮/键盘聚焦展开详情，展示源图、Grid 与预览三图对照，便于快速理解 Pix asset 输出链路。

## [1.3.0] - 2026-05-15

### Added

- Web 工作台新增 `asset` 游戏素材直出任务类型：单张/批量入口可按素材名称复用 `pix asset` 的白底单图模板、Pixel Grid extract、透明 PNG、预览和 meta 输出。
- Web API 新增 `asset` 任务参数、默认计费规则和 `palette_mode` 参数回传；worker 运行 asset 任务时会复制配置并临时关闭候选包装/远程 prompt 归一化，避免污染后续任务。

## [1.2.0] - 2026-05-14

### Added

- `pix sprite` 新增 soft chroma key 抠色模式，可估算半透明边缘 alpha，并通过 despill 去掉纯色背景对魔气、烟雾、爆炸等 VFX 边缘的染色。
- 新增 `[sprite].key_mode`、`key_softness`、`key_alpha_floor`、`key_despill` 配置，并在 CLI/Web 任务参数中支持覆盖。

## [1.1.0] - 2026-05-14

### Added

- 新增 `pix sprite` 动画精灵表流水线：生成 3×3 九宫格连续关键帧，自动切出 9 帧，逐帧像素化后输出 GIF 与横向精灵表 PNG。
- Web 工作台新增 `sprite_sheet` 任务类型、动画精灵表计费、GIF/帧输出 URL 和前端创建入口。
- 新增 `[sprite]` 默认配置段，支持帧尺寸、颜色数、GIF 帧间隔、统一裁剪、共享调色板和动画 Prompt 模板。

## [1.0.2] - 2026-05-14

### Removed

- 清理废弃的 AI Grid / Grid Review / 局部修补代码路径，删除旧模块、旧测试和前端旧开关字段，只保留 extract Pixel Grid 流程。
- 删除未跟踪的临时测试清单，并把 `testlist.md` 加入忽略规则，避免生成清单误提交。

### Fixed

- 修复 Ruff 报告的未使用导入、未使用局部变量、尾随空格和 `zip(strict=...)` 问题。
- 清理本地 `config.toml` 中已废弃的 `grid_review` 配置项；该文件仍保持不入库。

## [1.0.1] - 2026-05-14

### Fixed

- 恢复 `pix asset` 的经典 16×16 白底单图效果：asset 入口不再走候选包装/远程 prompt 归一化，默认使用白底模板、`palette_mode="auto"`、不默认 `grid_cleanup` / `grid_outline` / `fit_canvas`，贴近早期 `紫檀木/01_16x16.png` 的视觉结果。
- `resolve_size_strategy()` 同步返回 `palette_mode="auto"`，避免默认 ramp 重映射改变小图标色阶。

## [1.0.0] - 2026-05-14

### Removed (Breaking)

- 删除 `pix asset` 的 AI Grid 直绘、Grid Review 和普通 resize 分支。所有 ≥16×16 素材统一走 `extract_pixel_grid` → cleanup/outline → fit_canvas → ramp 调色板 → render；不再支持 8×8 等更小尺寸（最低 16×16）。
- 删除模块：`pix.grid.design`、`pix.grid.review`、`pix.grid.repair`、`pix.grid.style_reference`，以及 CLI 的 `pix grid-review` 子命令。
- `pix asset` 删除选项：`--ai-grid` / `--no-ai-grid`、`--ai-grid-retries`、`--ai-grid-instruction`、`--ai-grid-fallback`、`--style-reference-dir`、`--style-reference-limit`、`--grid-review`。
- `[asset]` 配置删除：`grid_review`、`ai_grid`、`ai_grid_retries`、`ai_grid_instruction`、`ai_grid_fallback`、`ai_grid_repair_mode`、`style_reference_dir`、`style_reference_limit`、`ai_grid_draft`、`ai_grid_draft_max_axis`、`ai_grid_draft_preview_scale`。
- `pix.pipeline.GridDesignInput` 字段收窄到 `mode: Literal["off", "extract"]`，删除 `review` / `retries` / `instruction` / `fallback` / `repair_mode`。
- Web API：`GridDesignSchema` 同步收窄；`POST /jobs` 不再接受 `grid.mode = "ai"`、`grid.fallback`、`grid.repair_mode` 等字段；管理后台「素材默认值」分类下的 AI Grid 相关项已删除。
- 前端：删除「AI 低像素工程图」勾选与 8×8 强制提示；`buildGridDesign()` 不再接收参数，恒返回 `{ mode: 'extract' }`。

### Changed

- `pix.asset.resolve_asset_generation_policy`：仅返回 `"extract"`；输入 <16×16 直接抛 `AssetSizePolicyError("最低支持 16x16 素材")`。
- `pix.asset.resolve_size_strategy`：所有支持尺寸都返回 `grid_mode="extract"`、`palette_mode="ramp"`，删除 `ai_grid` 与 `repair_mode` 字段。
- `pix asset` sidecar 不再写 `ai_grid` 嵌套段；改写 `grid_meta`（来自 pipeline meta 的 grid 段）便于对比。

## [0.59.1] - 2026-05-14

### Fixed

- `pixelize()` 接收已抠好背景的源图（如 candidate 选出来的 `01_source.png`）时，新增 `auto_skip_redundant_bg` 选项；启用后若源图 alpha=0 占比 ≥ 10%，自动跳过 `remove_bg` / `auto_crop`，避免对已抠图重复抠图把主体压缩到画面 1/3。pipeline 在所有内部 `pixelize()` 调用点都启用此选项。
- `meta.json.pixelize` 新增 `input_transparency_ratio` / `skipped_remove_bg` / `skipped_auto_crop` 字段，便于审计。

### Changed

- `pix.asset.resolve_size_strategy` 修正实测结论：
  - 16×16 / 32×32 改回 **extract + ramp + auto 修补**（原推荐 AI Grid 在实测中不如 extract 稳定，木材/果实类素材尤其明显）。
  - 64+ 普通像素化 + ramp，调用方应启用 `auto_skip_redundant_bg`。
  - 8×8 沿用 AI Grid 直绘（硬约束在 `resolve_asset_generation_policy` / web jobs 处），但已知"易铺满画布"是当前短板。
- AI Grid 退回到兜底定位：仅当 extract 出来明显失败时才启用，不再做 16/32 默认。
- 新增 `tests.test_pixelize_enhancements::TestAutoSkipRedundantBg` 3 个测试覆盖跳过开关；现有 `test_resolve_size_strategy_per_size` 同步更新断言。390 条测试全部通过。
## [0.59.0] - 2026-05-14

### Added

- 新增 `pix.asset.resolve_size_strategy(size) -> AssetSizeStrategy`，给出按目标尺寸推荐的 pipeline 组合：
  - 8×8：AI Grid 直绘 + force 修补 + ramp
  - 16×16：AI Grid + auto 修补 + ramp
  - 32×32：extract Pixel Grid + auto 修补 + ramp
  - 64+：普通像素化（grid off）+ ramp
- README 与文档同步推荐"尺寸 → 策略"对照表，方便用户与集成方组合 palette_mode / grid_mode / repair_mode。

### Changed

- 现有 CLI 命令默认值不变，新增 helper 不会自动覆盖；后续上层（GUI / Web 表单）可选择主动调用 `resolve_size_strategy` 填充推荐默认值。
## [0.58.0] - 2026-05-14

### Added

- AI Grid 新增 `repair_mode` 局部修补：当 draft readability 仅有 warning（无 blocking）时，VL 只返回少量像素 patches，Python 合并回 draft，避免整图重画。`pix.grid.repair` 含 `repair_pixel_grid` / `repair_or_passthrough` / `build_repair_mask`。
- `[asset].ai_grid_repair_mode`（off | auto | force，默认 auto）配置项；`GridDesignInput.repair_mode` 同步暴露给 web 入口。Web 管理后台新增对应开关。
- pipeline 在 grid 模式 `ai` 时按 `repair_mode` 走 auto/force 修补；`pix_meta.grid.repair` 落 before/after 报告与失败原因。

### Changed

- 修补总数超过画布 25% 时自动回退（不应用 patch），由上层决定是否走整图重画。
## [0.57.0] - 2026-05-14

### Added

- 候选生成新增 `n_sample` 模式：直接用 `generate_image(n=N)` 拿到 N 张独立 full-res 单图，每张单独 chroma-key 抠色，VL 看 full-res 评分。每张候选独立缓存，命中缓存只补齐缺失。
- `pix.api.image_gen.generate_images_batch` / `edit_images_batch`：优先 `n=N` 单次返回，不足时用 `prompt_variations` 循环补齐，保证最终拿到 N 张。
- `pix.contact_sheet.collect_independent_candidates` / `build_sample_prompt` / `candidate_mode` / `candidate_count`：把 `ContactSheetResult` 的合同复用给 n_sample，下游 ranking、candidate_outputs、GUI/Web 完全不需要改。
- 新增 `[image_gen].candidate_mode` (`n_sample` | `contact_sheet`，默认 `n_sample`)、`n_sample_count`、`n_sample_prompt_variations`、`n_sample_prompt_template` 四个配置项；Web 管理后台新增对应开关。
- 新增 4 个测试：`test_pipeline_n_sample_from_prompt`、`test_collect_independent_candidates`、`test_candidate_mode_*`、`test_generate_images_batch_*`。

### Changed

- 默认候选生成改为 `n_sample`：每张候选都是 full-res，主体细节比 1024² 切 9 格清晰得多，VL 评分更稳定。原 3×3 contact sheet 路径仍保留并默认在测试里锁定，可通过 `candidate_mode = "contact_sheet"` 回切。
- CLI `gen-only` 同步支持 n_sample；输出目录里 `_samples/sample_NN.png` 是独立单图原图，`candidates/` 仍是抠完色的候选。
- 现有 9 张 contact_sheet 测试在 fixture 中显式 `cfg.image_gen.candidate_mode = "contact_sheet"`，行为不变；新增 n_sample 集成测试覆盖 fallback 单图补齐。

## [0.56.0] - 2026-05-14

### Added

- 新增 Ramp 调色板 `pix.pixelize.ramp`：`outline → shadow → mid → highlight` 按 CIELAB 明度阶梯排布，VL 失败时按 HSL 色相聚类本地兜底，量化走 Lab 空间最近色，RGBA 透明通道完整保留。
- `PixelizeParams.palette_mode`（`auto|ramp|kmeans`）与 `[pixelize].palette_mode` / `[asset].palette_mode` 配置；Asset 直出默认切到 `ramp`，手绘层次感显著增强。
- `meta.json.pixelize` 新增 `ramp` / `ramp_info` 字段：落盘 ramp 结构、色相、每个 step 的 role、VL/本地来源与失败原因。
- Web 系统设置新增"调色板模式"开关，支持在管理后台切换。

### Changed

- `pixelize()` 新增 `cfg` / `source_description` 可选关键字参数，用于在 ramp 模式下调用 VL；现有调用点无需修改，不传即走本地兜底。
- CLI `asset`、GUI 单次像素化、Web 生成都会尊重 `palette_mode`，旧用户默认值 `auto` 保持 K-means 行为不变。

## [0.55.1] - 2026-05-13

### Fixed

- 生图模型无法直接输出透明 PNG 时，受控生图改用按 prompt 动态选择的纯色抠色背景，并全局移除 key color，修复封闭孔洞和边缘残留底色问题。
- 量化后贴着透明边界的 key-color 同色相紫边会被继续清理，避免纯色背景在物品轮廓外残留。
- 透明像素的 RGB 会在抠色后清零，避免忽略 alpha 的预览器显示残留背景色。

### Changed

- 默认 `[image_gen].green_screen_color` 改为 `auto`，避免固定 `#00FF00` 与玉石、草地、毒液等绿色题材撞色。

## [0.55.0] - 2026-05-12

### Added

- 网站首页新增 76 套题材范例图库，每套包含真实 Pix 全流程生成的透明物品精灵表和 1920×1080 像素 UI 展示图；物品图按大精灵表输出，保证单格至少 32×32 级可读空间。
- 新增 `scripts/generate_homepage_examples.py`，可从题材清单重新生成主页范例 PNG 与前端 manifest。

### Changed

- 首页第二 CTA 改为直达范例图库，未登录访客可快速查看题材覆盖范围。

## [0.54.1] - 2026-05-12

### Fixed

- 低像素描边策略现在也会处理已经带半透明 alpha 的候选图；即使未开启重新抠背景，也会把半透明边缘硬化并补 1px 外描边。

## [0.54.0] - 2026-05-12

### Added

- Contact sheet 流程现在会为 9 个候选全部生成最终像素产物，保存到 `candidate_outputs/`，并在 Web 候选卡片中直接展示像素结果。
- `meta.json` 的每个候选记录 `pixelized_path`、`preview_path` 和 `pixelized_meta`，主输出仍兼容指向 VL 最高分候选。

## [0.53.2] - 2026-05-12

### Fixed

- 低像素透明素材（最长边 32px 及以下）不再使用 alpha 羽化；启用透明背景时会自动归一为外描边，避免小图标边缘发虚。

## [0.53.1] - 2026-05-12

### Fixed

- 调整文本审核提示词，继续使用 VL 模型审核用户原始描述，但避免审核提示本身触发接口内容拦截导致降级。

## [0.53.0] - 2026-05-12

### Added

- 九宫格候选新增 VL 评分排序：切出的 9 张候选会一次性送入 VL，按描述符合度、低像素可读性、轮廓、居中和抠图质量打分。
- Pipeline 会把最高分候选作为默认 `01_source.png`，并保存 `01_candidate_scores.json` 供审计。
- Web 候选列表显示排名、分数和已选标记，候选仍可手动复用为本地像素化任务。

### Changed

- `meta.json` 中的 contact sheet 候选按 VL 评分从高到低排序，同时保留原始 index/row/col。

## [0.52.0] - 2026-05-12

### Added

- 默认受控生图：文生图/图生图会由后端包装为 3x3 动态纯色抠色背景九宫格 contact sheet，并自动切出 9 个透明候选图。
- 新增用户描述 prompt guard：先执行本地注入/模板覆盖规则，再可选调用文本模型审核，且模型只接收用户原始输入。
- Web 作品和任务卡展示九宫格候选，支持复制候选路径并用候选创建免费的本地像素化任务。

### Changed

- 生图缓存 key 改为基于服务端 effective prompt、九宫格参数和抠色背景参数，避免用户描述与模板版本混淆。
- 默认素材 prompt 从白底改为纯色抠色背景，便于后处理稳定抠图。

## [0.51.0] - 2026-05-12

### Added

- AI Grid 新增手绘图标风格参考目录：`pix asset --style-reference-dir` / `[asset].style_reference_dir` 可传入现有 16x16 美工 icon 目录，让 VL 学习留白、轮廓、色阶和高光密度。
- 管理后台新增 `pix.asset.style_reference_dir` 与 `pix.asset.style_reference_limit` 配置项，worker 任务可使用最新手绘参考目录。

### Changed

- 强化 16x16/8x8 AI Grid 提示词与返修提示，把低尺寸素材明确视为独立手绘图标重绘，而不是源图缩略图。
- 8x8 可读性验收新增贴边、过满、过密阻塞规则，避免生成整块糊成一团的缩图式结果。

## [0.50.0] - 2026-05-12

### Added

- 新增深色“像素工坊门禁”认证 UI 套件，统一登录、邮箱验证码注册和首次管理员初始化界面的布局、表单、提示和错误状态。

### Changed

- 首页认证区改为同源深色工作台场景，注册验证码和登录表单使用更接近像素工坊风格的高对比输入框、按钮和状态反馈。

## [0.49.1] - 2026-05-12

### Fixed

- 修复前端注册验证码发送在同源/局域网/反向代理部署中仍请求 `127.0.0.1:8000` 导致浏览器显示 `Failed to fetch` 的问题；前端默认走 `/api` 代理，Vite 开发环境同步代理到后端。
- 新增 `PIX_WEB_CORS_ORIGINS` 允许前后端分离部署显式放行生产前端域名，并把网络失败提示改为可操作的 API 连接诊断文案。

## [0.49.0] - 2026-05-11

### Added

- 新增首次打开站点的管理员初始化引导：空用户表时可直接创建首个管理员并进入后台。
- 管理后台扩展为独立控制台，可配置运营保护、邮件验证码、模型/API、素材默认值、价格规则和充值套餐。
- 新增 admin settings 元数据、secret 遮罩、测试邮件接口，以及充值套餐创建/更新/启停接口。

### Changed

- Web 生成 worker 会在每个任务开始时加载后台管理的 Pix 配置覆盖，后续任务可使用最新模型和素材默认值。

## [0.48.1] - 2026-05-11

### Fixed

- 修复注册验证码发送不可观测的问题：SMTP 发送失败现在会回滚验证码并返回 503，而不是后台吞错导致用户收不到邮件。
- console 邮件模式会直接返回 `debug_code`，避免开发/内测环境未配置 SMTP 时无法完成注册。

## [0.48.0] - 2026-05-11

### Changed

- 合并首页“核心价值”和“工作流”介绍页为单页“核心优势”，突出 Pix 从 AI 生图到可交付游戏素材生产线的差异化。
- 重写首页优势文案，强调 Pixel Grid 工程图、素材包批量生产、多尺寸交付和可追踪验收。

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
