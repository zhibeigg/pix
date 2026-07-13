# Pix Forge 全站审美升级 · "Studio" 设计语言

- **日期**: 2026-06-27
- **状态**: 已获方向批准（待 spec 评审 + 用户复核）
- **范围**: `apps/web` 前端表现层（颜色 / 排版 / 结构 / 交互 / 文案密度 / 引入新库）
- **目标气质**: 高端全流程自动化 —— 从"温柔 pastel SaaS" 转向"精密生产工作室"

## 1. 目标与非目标

### 目标
- 全站统一一套高端设计语言，**light + dark 双主题都达到高端水准**。
- 以"设计 token 层"为地基，改一次值、全站联动，最大化杠杆、最小化散点改动。
- 分阶段交付，每阶段可独立运行、截图验收后再进入下一阶段。

### 非目标（严格不碰）
- **不改任何影响实际出图的东西**：生成算法、prompt、出图参数、各资产类型（图标/纹理/精灵/序列帧）的功能效果与产物。
- 不改后端 API 契约、计费逻辑、点数规则、权限模型。
- 不做无关重构（仅在为本目标服务时做有针对性的清理）。

### 前端"禁改清单"（出图数据流，位于 apps/web 之内但严禁触碰其逻辑/数值）
保护判据从"不碰后端 `src/`"修正为 **"不碰任何 generate / params / pixelize 数据流文件的逻辑与数值，只允许改其渲染样式"**。明确禁改：
- `apps/web/src/pixelize.ts` — `defaultPixelize` / `defaultAssetPixelize` / `edgeStylePixelize` / `normalizeEdgeStyle` / `buildPixelize` 等出图参数（output_size / colors / dither / edge_style / bg_removal / crop…），一个数值都不动。
- `apps/web/src/types.ts` 中生成/参数相关类型（`PixelizeParams`、`GridDesignParams`、Job 参数等）。
- `apps/web/src/api.ts` 的请求体构造与字段。
- `homepage*Examples.ts` 中作为生成示例的参数数据。
- `jobReuse.ts`（复用链参数逻辑）。
> 允许：仅调整上述功能所对应 UI 组件（如生成面板、PixelControls、TuningPanel）的**视觉样式与文案**，不改其传给后端的参数值。

### 允许
- 优化交互逻辑、精简文案、调整 UI 结构、引入新库（字体、图标补充等）。
- **大胆更换品牌主色与字体**（用户已授权）；保留 Pix Forge logo、中文优先、暗色模式。

## 2. 设计语言："Studio"

### 2.1 中性色（最高杠杆改动）
中性底色由**暖米黄 / 羊皮纸（cream / parchment, 暖 hue 30–49）** 改为**冷石墨（cool graphite, 中性偏冷）**。这是拉开"高端自动化"气质的单点最大杠杆。

- Dark canvas / surface / elevated：约 `#0B0C0E` / `#141619` / `#1B1E23`（替换现 navy `223° 蓝调`）。
- Light canvas / surface / subtle：约 `#FBFBFC` / `#FFFFFF` / `#F1F2F5`（替换现暖 cream）。
- Hairline：dark `rgba(255,255,255,.08)`，light `#E7E9ED`。
- 文本：dark `#F4F5F7` / muted `#A4ABB3`；light `#16181C` / muted `#5B626B`。

### 2.2 彩色用法
去 pastel 色卡（薄荷/天蓝/薰衣草/玫瑰…作为大面积装饰的用法）。**彩色只保留给：品牌 CTA、语义状态（成功/警告/危险/信息）、数据可视化。** 其余表面回归中性 + 发丝边框 + 克制分层阴影。

### 2.3 品牌主色
通用 SaaS 紫 `#5645d4` → 更电、更冷的 **Iris 紫 `#6D5EF8`**（仍属紫系，延续 logo 识别）。
- hover/active：`#8B7BFF` / `#4B3DD6`。
- 暗色模式下品牌元素带 glow（`box-shadow` 投射 iris 28% 柔光）。
- CTA 采用细微竖向渐变 + 内高光，强化"按钮"实体感。

### 2.4 字体
- 拉丁 UI / 标题：**Inter Tight**（紧字距、现代、适合 display）。
- 中文：**Noto Sans SC / HarmonyOS Sans**（优先级链，保留中文优先）。
- 等宽：JetBrains Mono / 保留 Maple Mono NF CN。
- 字体策略：实现阶段**自托管**（不依赖 Google Fonts 运行时），display 加紧字距（约 `-0.02 ~ -0.03em`），建立清晰字号梯度。

### 2.5 规格
- 圆角：卡片 14 / 控件 9 / 胶囊 full（收紧现有最大 24px 的偏软圆角）。
- 边框：1px 发丝边框为主导分隔手段（暗色尤其依赖边框而非阴影）。
- 阴影：复用现有 `--pix-shadow-*` 语义阶梯，重新调参为更克制、更分层。
- 动效：复用现有 `--motion-*` / `--ease-*` token，补充微交互弹性；遵守 `prefers-reduced-motion`。

### 2.6 Hero / 落地页气质
深色高对比、细网格纹理 + CTA glow、产品"素材生产看板"内嵌展示、**精简文案**（去冗余、提密度）。

## 3. 架构与落点

现有 token 体系高度抽象：`apps/web/src/styles.css` 以 HSL CSS 变量定义，并有多层语义别名（`--ledger-*`、`--data-*`、`--tone-*`、`--pix-shadow-*`），组件通过别名消费。**因此改造主要改变量值与少量别名，而非每个消费点。**

关键文件：
- `apps/web/src/styles.css` —
  - `@theme` 块（顶部）：`--font-sans/serif/mono` 字体栈、`--radius-*` 圆角梯度、`--motion-*`/`--ease-*`。**phase 1 必改**。
  - `:root` / `[data-theme=dark]`：颜色变量主战场（中性色 navy/cream → 冷石墨、`--primary` → Iris、各 `--pix-*` / `--ledger-*` / `--tone-*` / `--pix-shadow-*` 调参）。
- `apps/web/src/design/tokens.ts`（`tint` 暖色别名表）、`apps/web/src/theme.ts`（`pixBrand` 暖色别名表，引用 `--pix-cream/amber/mint/...`）—— **phase 1 必改散点**，否则换肤后暖色残留。`status.ts` 的 tone 映射随语义色调整。
- 字体自托管：新增 `apps/web/public/fonts/`（或 `src/styles` 内 `@font-face`），`package.json` 视情况新增字体/图标依赖；`index.html` 加关键字重 preload。
- `apps/web/src/components/ui/*` — 基础组件（button/card/input/textarea/badge/select/tabs/...）。
- 落地页：`AppHero.tsx`、`LandingSections.tsx`、Header 与 footer（均在 `App.tsx` 内联，配合 `HeaderUtilityBar.tsx`、`AccountMenu.tsx`）。
- 工作区：`SingleGeneratePanel`、`BatchGeneratePanel`、`GalleryGrid`、`AssetPackPanel`、`WorkspacePage` 与 `WorkspaceShell`（定义于 `App.tsx`）等 —— **仅改样式/文案，不改出图参数**。
- 其余：`BillingPage`、`RewardsPage`、`ApiPage`、`AdminPanel`、`AppOverlays`（弹窗/Toast）。

## 4. 分阶段交付

每阶段结束：本地运行 + Chrome 截图（light & dark）验收，再进入下一阶段。

1. **设计 token 层** — styles.css 变量 + tokens.ts + 字体自托管。改完整站底色/主色/字体自动联动。
2. **基础组件** — button / card / input / textarea / badge / chip / select / tabs / panel / dialog 等统一新规格。
3. **落地页** — Hero + LandingSections + Header + Footer，精简文案、重排结构。登录态桌面顶栏将点数余额与紧凑的充值 CTA 作为相邻操作，直接进入 `#/billing`；窄屏继续通过账号菜单提供点数中心入口，避免挤压品牌与全局工具。首页「用户分享」中的序列帧卡片复用作品库播放器：现代分享直接使用逐帧坐标，历史横向 sprite sheet 根据图片实际尺寸与帧数推导坐标；仅在卡片可见且页面处于前台时推进帧，`prefers-reduced-motion` 下固定首帧。
4. **工作区** — 生成面板 / 作品库 / 素材包 / WorkspaceShell。作品库、任务队列与后台「任务与作品」共用序列帧预览解析：新任务优先使用 `sprite_sheet_url` 和逐帧坐标，旧任务回退 `pixelized_url` 与请求帧数；播放器的背景画布必须限制在单帧尺寸内，宽卡片不能显示相邻帧。
5. **其余页面** — 计费 / 奖励 / API 文档 / 后台 / 弹窗 Toast。

## 5. 验证

- 每阶段：`npm --prefix apps/web run build`（tsc + vite）通过；Chrome 无头截图 light + dark 双主题人工验收。
- 回归：`npm --prefix apps/web run test`（vitest）通过；不改动 `jobReuse.test.ts` 等既有逻辑测试的预期。
- 功能不变性自检：生成流程、参数快照、复用链、计费展示数值不变（只换皮）。
- 可访问性：对比度 ≥ WCAG AA；focus-visible 环保留；reduced-motion 生效。

### phase 1 出口判据（可执行）
- grep 断言：全站不再存在对暖色 token 的**直接内联消费**——
  `--pix-cream | --pix-parchment | --pix-amber | --pix-mint | --pix-sky | --pix-lavender | --pix-rose | --pix-peach` 的 `bg-[hsl(var(--...))]` 用法应归零或改走语义别名；`tint`/`pixBrand` 别名表中的旧暖 key 必须改为新中性/语义值（保留 key 名可，但其值不得再产出暖米黄/pastel）。
- 字体断言：运行时无新增对 `fonts.googleapis.com` 的请求（字体已自托管）。
- `package.json` 若新增依赖，`npm --prefix apps/web run build` 后产物体积无异常膨胀（关注字体子集化）。
- 出图保护断言：`git diff` 不包含"禁改清单"文件的逻辑/数值改动（仅允许其对应 UI 组件的样式变更）。

## 6. 风险与缓解
- **风险**：大面积换肤可能漏改散点内联色（`bg-[hsl(var(--pix-...))]`）导致暖色残留。
  **缓解**：phase 1 后全站 grep 审查 `--pix-cream/parchment/amber/mint/sky/lavender/rose/peach` 等暖 token 的直接消费点，逐一归并。
- **风险**：字体自托管体积/加载。**缓解**：子集化 + `font-display:swap` + 预加载关键字重。
- **风险**：误伤出图相关代码（含前端 `pixelize.ts` 等出图数据流文件）。**缓解**：遵守 §1"前端禁改清单"，只改表现层样式/文案；不触碰 `src/`（Python 后端）与前端出图参数/类型/请求构造；以 §5 出图保护断言把关。

## 7. 后台运维台与安全更新扩展

管理后台在 Studio 语言上采用更高密度的运维控制台变体，服务站长与少量可信运营人员：

- 一级信息架构分为「观测 / 运营 / 商业 / 系统」，不再把业务页与系统设置平铺成二十个同权 Tab。
- 桌面端使用紧凑侧栏、命令条和数据表；窄屏改为模块选择器，保留所有关键操作。
- 概览采用「运营总览 2.0」结构：顶部控制带提供 `24h / 7d / 14d / 30d / 90d / 自定义`、小时/日/7 天粒度及上一周期对比；范围、日期、粒度、对比开关和趋势主题均写入 `#/admin?...`，支持刷新、前进后退与深链接。
- 第一视觉层只保留任务量、成功率、消费点数、充值点数、付费订单、活跃用户六个周期指标，统一显示本期、上期与变化；上一期为零时使用「新增」而非无穷百分比，无真实对比数据时不显示伪造环比。
- 主趋势是页面焦点，可在任务质量、点数流量、订单转化、用户活跃四个主题间切换；当前期实线、上一期虚线，配合可开关图例、十字线、精确 Tooltip 和逐时/逐日明细联动。主题切换只重组已有数据，不重新请求。
- 实时运行、异常诊断与历史累计仍保留，但压缩为辅助状态带和账本；历史数据直接从业务表按站点时区聚合并补零，不引入持久化统计表。色彩只用于曲线区分、状态、风险和主要动作，不新增装饰性卡片墙或卡片嵌套。
- 小屏下六指标横向滚动、诊断区落到图表下方、明细表改为日期分组列表；所有图例、行选择和控制器都有键盘焦点，减弱动效模式关闭图表动画。
- 后台使用独立的 compact density 作用域，不降低生成工作台与营销页面的触控尺寸。

版本更新遵循控制面与执行面分离：

- FastAPI 仅检测固定 GitHub Release、展示可信 manifest、执行管理员重新认证并向 updater 提交窄协议请求；API 容器不挂 Docker socket。
- 独立 Pix Updater 是唯一拥有 Docker/Compose 权限的服务，只接受固定仓库、固定镜像 allowlist 和固定部署项目，不接收任意命令、URL、镜像或路径。
- Release manifest 绑定 tag、commit、Alembic head 与 backend/frontend/updater 镜像 digest，并通过 GitHub provenance 验证。
- 更新前必须完成预检与 PostgreSQL 备份；使用不可变 digest 部署，展示完整状态机，并保留上一已知良好版本和受控数据库恢复路径。
- 首次从源码构建部署迁移到 release Compose / updater 需要人工 bootstrap；后续版本才允许在后台按钮更新。

## 8. 开放问题
- 字体最终授权与自托管来源（Inter Tight / Noto Sans SC 均为开源，可自托管）。
- 是否需要在工作区引入更强的信息密度布局（留待 phase 4 结合实景决定）。
