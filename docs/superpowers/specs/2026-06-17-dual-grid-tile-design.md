# 双瓦片（dual-grid）素材直出设计

- 日期：2026-06-17
- 状态：已确认设计，待实现
- 版本影响：功能更新，`1.88.2 → 1.89.0`（B 位递增）

## 1. 背景与目标

Pix 现有 `asset_kind=tile_texture` 只生成**单张四边无缝**纹理（左右、上下边缘自接），适合「一种材质铺满地面」。但像素地图里两种地形交界（草地↔泥土、草地↔水/空）需要一**套**互相能拼接的过渡瓦片。

目标：新增 **dual-grid 双瓦片**素材直出。一次任务产出「16 张可无缝拼接的瓦片图集 + 一张应用预览 + 映射 meta」，表达两种地形 A/B 的所有角组合，地图引擎按 dual-grid 规则即可自动平滑过渡。

## 2. 已确认的关键决策

1. **含义**：经典 dual-grid 16-tile 系统（每张瓦片由 4 个角决定，2 态 → `2^4 = 16` 张）。
2. **模式**：同时支持「实心 A ↔ 实心 B」与「实心 A ↔ 透明」两种（一个参数切换）。
3. **产物（MVP）**：4×4 图集 + 应用预览 + meta 映射。**不**含逐张小图、引擎专用配置（列入后续）。
4. **生成策略**：**程序化合成**——AI 只生成无缝材质 A/B，代码用 16 个角掩码确定性合成 16 张瓦片；拼接无缝**由构造保证**（优于「AI 一次直出图集」——图像模型无法满足跨瓦片角拓扑对齐的组合约束）。
5. **过渡默认 `rounded`**（像素 dual-grid 最地道）。
6. **范围**：后端 pipeline + 外部 API + `config.example`/README/语言文件/API 文档同步；Web 单图面板的 dual_grid 专用 UI 列入后续跟进，本期不做。

## 3. dual-grid 原理与无缝性保证

- 世界格：每格是 A 或 B。**显示格**相对世界格偏移半格；每张显示瓦片的 4 个角恰好落在 4 个世界格中心上（左上 TL、右上 TR、左下 BL、右下 BR）。
- 显示瓦片 = 4 象限，每象限取**其角**的材质。
- **边不变量（无缝的核心契约）**：每条瓦片边只由「该边两端的两个角 + 在中点处一分为二（近角材质占该半）」决定。相邻显示瓦片共享一条边，就共享该边两端的两个角 → 这条边在两张瓦片里的**材质归属逐像素相同**，整套天然无缝。瓦片**内部**的过渡形状（圆角/直边）纯属外观，只要不破坏边不变量，就不影响拼接。

> 这条不变量是方案 1 的根基，也是核心测试项（§9）。

## 4. 核心算法

### 4.1 角位编码与图集约定

- 角位：`TL=bit0, TR=bit1, BL=bit2, BR=bit3`；`A=1, B=0`。瓦片索引 `idx = TL + 2·TR + 4·BL + 8·BR ∈ [0,15]`。`idx=0` 全 B，`idx=15` 全 A。
- 图集 **4×4 行优先**：`cell(row, col)`，`idx = row·4 + col`。
- meta 显式记录完整 `bitmask → (row,col)` 映射表 + 约定名 `pix-dualgrid-v1`。因映射表是显式数据，导入任意引擎只需按表重映射；本期不导出引擎专用配置。

### 4.2 角掩码与单瓦片合成

- 单瓦片尺寸 = `pixelize.output_size` (W, H)。象限划分中点 `mx = W//2, my = H//2`（奇数尺寸：左/上半含中点列/行，保证两张瓦片中点定义一致）。
- **材质采样按瓦片本地坐标**：`tile[x,y]` 的材质内容取 `materialA[x,y]`（若该像素归 A）或 `materialB[x,y]`（归 B）。因 A、B 都是四边无缝纹理，任意瓦片相邻时同材质区域自动续接无缝；A/B 的**归属**由角掩码决定，与材质内容解耦。
- 合成分两步：先算**归属掩码** `mask[x,y] ∈ {A, B}`（仅依赖 4 个角 + transition_style），再按掩码采样材质上色。
- `transition_style`：
  - `hard`：象限硬边（边界在 `x=mx`、`y=my`）。
  - `rounded`（默认）：在象限交界处按半径 `r = max(1, min(W,H)//4)` 做圆角，**仅改瓦片内部**；每条边最外 1px 严格遵守边不变量（近角材质 + 中点二分）。
  - `outline`：在 `rounded` 归属基础上，对 A↔B（或 A↔透明）边界的 **A 侧像素**（A 区内缩 1px，绝不画在 B/透明一侧——在 `alpha=0` 上色无意义）画 1px 描边色。描边色缺省取**材质 A 的最暗可见色**（让描边与主体融合）；后续可加 `dual_grid.outline_color` 配置覆盖。
- **透明模式**（material_b=transparent）：B 像素 `alpha=0`，A 像素取材质 A；`transition_style` 缺省按 `outline` 处理（即上面的「A 区内缩 1px 描边」给孤岛边缘防裸边），用户仍可显式选 hard/rounded。

### 4.3 材质对齐（可选共享调色板）

A、B 各是一张 `output_size` 的四边无缝纹理。可选把 A、B 一起量化到 `pixelize.colors`（复用 sprite 的 `_apply_shared_palette` 思路），让两种材质配色协调、交界不突兀。

## 5. API 表面

### 5.1 新增 asset_kind 与字段

- `asset.py`：`ASSET_KIND_LABELS` / `ASSET_PROMPT_PROFILES` / `COMPATIBLE_SUBJECT_KINDS` 新增 `"dual_grid"`。
- `schemas.py` 的 `AssetParams` 新增字段：

| 字段 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `material_a` | str | 必填非空 | 材质 A 描述（主体地形，如「草地」） |
| `material_b` | str | 始终提供 | 材质 B 描述；空串 / `"transparent"` 即透明模式（非「缺失」，校验不报错） |
| `material_a_texture_kind` | TileTextureKind | `auto` | A 的纹理细分（复用现有枚举） |
| `material_b_texture_kind` | TileTextureKind | `auto` | B 的纹理细分 |
| `transition_style` | `"rounded"\|"hard"\|"outline"` | `rounded` | A/B 交界画法 |

> 注：dual_grid 使用上面两个 `material_*_texture_kind` 字段；`AssetParams` 现有的**单数** `texture_kind` 在 dual_grid 下忽略（该字段仅 tile_texture 使用）。

- `name` 作为整体素材名（文件名/展示）。`pixelize.output_size` = 单瓦片尺寸；`pixelize.colors` 沿用限色。

### 5.2 校验

- `asset_kind=dual_grid` 时 `material_a` 必填非空；`material_b` 始终提供，空串或 `"transparent"` 解释为透明模式（不报「缺失」错）。
- `output_size` 仍 ≥16×16（沿用 `resolve_asset_generation_policy`），单瓦片尺寸即 output_size。
- `transition_style` 限三枚举（strict `Literal`，非法值由 schema 直接 422 拒绝，不静默回退）。

## 6. 后端 pipeline 集成

- 新增 `src/pix/dual_grid.py`（**纯算法、零网络**）：
  - `corner_masks(size, transition_style) -> list[np.ndarray]`：16 张归属掩码。
  - `compose_tile(mask, material_a, material_b|None, transition_style, outline_rgb)`：单瓦片 RGBA。
  - `compose_atlas(...) -> (atlas_img, tiles, mapping)`：16 瓦片 + 4×4 图集 + 映射表。
  - `render_preview(tiles, world_grid) -> img`：按随机世界格渲染应用预览。
- 新增 `run_dual_grid_asset_job_pipeline`（`pipeline_adapter.py`），类比 `run_tile_asset_job_pipeline`：
  1. 解析参数；
  2. 生成材质 A：复用 tile_texture 生成路径（`build_asset_prompt(asset_kind="tile_texture", texture_kind=material_a_texture_kind)` → 生图 → perfect_pixel → output_size）；
  3. 透明模式跳过 B，否则同法生成 B；
  4. （可选）共享调色板对齐 A/B；
  5. `compose_atlas(...)` → 16 瓦片 + 4×4 图集；
  6. `render_preview(...)` → 预览图：种子**确定性派生自** `name + material_a + material_b + transition_style` 的哈希（同参数同预览，可复现、测试稳定），8×8 世界格，种子写入 meta；
  7. 落盘 atlas、preview、materials、meta。
- 路由：`pipeline_adapter` 现有 dispatch（约 613 行）按 `asset_kind=="dual_grid"` 进入新 pipeline；其余 asset_kind 不变。

## 7. 产物

- `{run}/dual_grid_atlas.png`（4×4 图集）
- `{run}/dual_grid_preview.png`（应用预览）
- `{run}/materials/material_a.png`、`material_b.png`（调试 + 复用；透明模式无 B）
- `{run}/meta.json`：`asset_kind`、`material_a/b`、解析后 texture kinds、`transition_style`、`transparent_mode`、`tile_size`、`atlas_size`、`convention`、`mapping`(bitmask→cell)、`preview_seed`、`shared_palette`。
- 后端 `JobOutputResponse`（schemas.py:509）新增 `dual_grid_atlas_path/url`、`dual_grid_preview_path/url`（computed_field，类比 `sprite_mosaic_path`）。

## 8. 错误处理 / 边界

- 奇数 `output_size`：象限用 `//2` + 中点归左/上，两张瓦片中点定义一致，仍满足边不变量（测试覆盖）。
- 透明模式：不生成、不采样 B；B 像素恒透明；缺省启用 outline。
- 生图失败：沿用现有重试/报错路径（与 `run_tile_asset_job_pipeline` 一致）。
- A、B 理论上都 = output_size；合成前断言尺寸一致，不一致按 A 尺寸为准并记录 warning。

## 9. 测试（TDD）

- `test_dual_grid_masks_complete`：16 张掩码覆盖 idx 0–15、无重无漏；idx0 全 B、idx15 全 A。
- `test_dual_grid_seamless`（**核心**）：对**归属掩码**，任意两张「在世界格里水平/垂直相邻」的瓦片，沿共享边逐像素归属一致（验证边不变量；用掩码、与材质无关）。三种 transition_style 都跑。
- `test_dual_grid_atlas_layout`：`bitmask→cell` 映射与图集像素切片一致。
- `test_dual_grid_transparent`：透明模式 B 区 `alpha=0`、A 区 `alpha>0`、交界存在 outline 像素。
- `test_dual_grid_transition_styles`：`hard` 边界硬直；`rounded` 内部出现圆角但边仍满足不变量；`outline` 出现描边色。
- `test_dual_grid_pipeline`（mock 生图）：mock 材质 A/B → 图集尺寸 `4W×4H`、格数 16、meta 字段齐全、preview 尺寸正确。

## 10. 需同步更新（遵循 CLAUDE.md 规则）

- `config.example.toml`：dual_grid 默认项（如默认 `transition_style`、outline 颜色）若引入配置。
- `README.md` + 新增 `docs/dual-grid-rules.md`：用法、字段、4×4 约定、mapping 表。
- `apps/web/src/locales/zh-CN.ts`、`en.ts`：`dual_grid` 素材类型标签等（即便本期不做面板，参数快照 `JobParameterSnapshotDialog` 要能展示）。
- 外部 API 文档（`apps/web/src/pages/ApiPage.tsx` + README API 段）：dual_grid 字段与示例。
- `CHANGELOG.md`：Added 条目。
- 版本号 `1.88.2 → 1.89.0`（`pyproject.toml` + `src/pix/__init__.py`）。

## 11. 不在本期范围（后续跟进）

- Web 单图生成面板的 dual_grid 专用 UI（材质 A/B 输入、过渡选择、图集/预览展示）。
- 引擎专用配置导出（Godot TileSet / Tiled `.tsx`）。
- 方案 3（AI 有机过渡边）升级。
- 多于两种地形 / 47-blob / 边角更细的瓦片集。
- 逐张瓦片小图输出（按需再加，meta 已含切片信息）。
