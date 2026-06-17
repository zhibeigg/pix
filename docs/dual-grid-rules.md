# 双瓦片（dual-grid）素材直出规则

Pix 的 `asset_kind=dual_grid` 用于一次性产出一**套**可无缝拼接的过渡瓦片，表达像素地图里两种地形 A/B 的交界（草地↔泥土、草地↔水/空等）。它在内部先用 `tile_texture` 的生图链路生成两张四边无缝材质 A、B，再用 16 个角掩码**确定性合成** 16 张瓦片，拼成一张 4×4 图集；地图引擎按 dual-grid 规则即可自动平滑过渡。

与 `tile_texture`（单张铺满地面的无缝纹理）不同，dual_grid 解决的是「两种材质如何互相过渡」。

## 什么是 dual-grid（16-tile）

经典 dual-grid 系统：

- **世界格**：每格是 A 或 B 两种地形之一。
- **显示格**相对世界格偏移半格；每张显示瓦片的 4 个角恰好落在 4 个世界格中心上（左上 TL、右上 TR、左下 BL、右下 BR）。
- 每张显示瓦片由它 4 个角的 A/B 组合决定，2 态 → `2^4 = 16` 张瓦片。
- 引擎运行时只需看一个显示格周围 4 个世界格的地形，组成 4 位掩码，查表取对应瓦片 —— 无需手摆过渡块。

**无缝性由构造保证**：每条瓦片边只由「该边两端的两个角 + 中点二分（近角材质占该半）」决定。相邻显示瓦片共享一条边就共享该边两端的两个角，于是这条边在两张瓦片里的材质归属逐像素一致，整套天然无缝。瓦片内部的过渡形状（圆角 / 直边）纯属外观，不影响拼接。

## API 字段

dual_grid 字段写在 `asset` 块里：

```json
{
  "job_type": "asset",
  "asset": {
    "name": "草地泥土过渡",
    "asset_kind": "dual_grid",
    "material_a": "草地",
    "material_b": "泥土",
    "material_a_texture_kind": "terrain_ground",
    "material_b_texture_kind": "terrain_ground",
    "transition_style": "rounded"
  },
  "pixelize": {
    "output_size": [32, 32],
    "colors": 12
  }
}
```

| 字段 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `material_a` | str | 必填非空 | 材质 A 描述（主体地形，如「草地」）。 |
| `material_b` | str | 始终提供 | 材质 B 描述；空串或 `"transparent"` 即透明模式（不报「缺失」错）。 |
| `material_a_texture_kind` | texture_kind | `auto` | 材质 A 的纹理细分，复用 `tile_texture` 的 `texture_kind` 枚举（`auto`/`generic_texture`/`terrain_ground`/`path_floor`/`wall_surface`/`wood_planks`/`water_liquid`/`foliage_canopy`/`roof_tile`/`metal_panel`/`fabric_carpet`）。 |
| `material_b_texture_kind` | texture_kind | `auto` | 材质 B 的纹理细分，枚举同上。 |
| `transition_style` | `"rounded" \| "hard" \| "outline"` | `rounded` | A/B 交界的画法，见下文。非法值由 schema 直接 422 拒绝。 |

说明：

- `name` 是整套素材名（用于文件名 / 展示）。
- `pixelize.output_size` = **单张瓦片**的尺寸；输出图集是它的 4×4 排布（即 `4W × 4H`）。
- `pixelize.colors` 沿用限色，作用于生成的材质。
- `asset` 现有的**单数** `texture_kind` 字段在 dual_grid 下被忽略（它只对 `tile_texture` 生效）；dual_grid 用上面两个 `material_*_texture_kind`。

## 图集约定 `pix-dualgrid-v1`

- 图集为 **4×4 行优先**排布：`cell(row, col)`，`idx = row*4 + col`。
- 单瓦片尺寸 = `output_size`，整图 = `4W × 4H`。
- `meta.json` 里 `convention = "pix-dualgrid-v1"`，并显式记录完整的 `bitmask → cell` 映射表（导入任意引擎只需按表重映射，本期不导出引擎专用配置）。

### 角位编码与 bitmask → cell 映射

- 角位：`TL=bit0, TR=bit1, BL=bit2, BR=bit3`；地形 **A=1，B=0**。
- 瓦片索引：`idx = TL·1 + TR·2 + BL·4 + BR·8 ∈ [0, 15]`。`idx=0` 全 B，`idx=15` 全 A。
- 图集坐标：`row = idx // 4`，`col = idx % 4`。

下表即 `pix-dualgrid-v1` 的 16 项映射（A=该角为材质 A，B=该角为材质 B）：

| idx | TL | TR | BL | BR | row | col |
|---|---|---|---|---|---|---|
| 0 | B | B | B | B | 0 | 0 |
| 1 | A | B | B | B | 0 | 1 |
| 2 | B | A | B | B | 0 | 2 |
| 3 | A | A | B | B | 0 | 3 |
| 4 | B | B | A | B | 1 | 0 |
| 5 | A | B | A | B | 1 | 1 |
| 6 | B | A | A | B | 1 | 2 |
| 7 | A | A | A | B | 1 | 3 |
| 8 | B | B | B | A | 2 | 0 |
| 9 | A | B | B | A | 2 | 1 |
| 10 | B | A | B | A | 2 | 2 |
| 11 | A | A | B | A | 2 | 3 |
| 12 | B | B | A | A | 3 | 0 |
| 13 | A | B | A | A | 3 | 1 |
| 14 | B | A | A | A | 3 | 2 |
| 15 | A | A | A | A | 3 | 3 |

引擎侧用法：对每个显示格，按它左上 / 右上 / 左下 / 右下 4 个世界格的地形（A=1，B=0）算出 `idx`，再用 `(idx // 4, idx % 4)` 取图集对应单元格即可。

## 实心模式 vs 透明模式

- **实心模式**（`material_b` 为非空且非 `"transparent"`）：A 区取材质 A，B 区取材质 B，得到「两种地形互相过渡」的瓦片集。
- **透明模式**（`material_b` 为空串或 `"transparent"`）：B 区像素 `alpha=0`，A 区取材质 A，得到「材质 A 的孤岛 / 边缘」瓦片集（如草地浮岛、贴在透明背景上的地块）。透明模式不生成、不采样 B。

## 过渡画法 transition_style

三种画法**只改瓦片内部外观，都不破坏边不变量**（每条边最外 1px 严格遵守「近角材质 + 中点二分」，故拼接始终无缝）：

- `rounded`（默认）：在象限交界处做圆角，过渡自然，最贴近地道的像素 dual-grid 观感。
- `hard`：象限硬边，A/B 在瓦片中线处直角相交，颗粒感强。
- `outline`：在 `rounded` 归属基础上，对 A↔B（或 A↔透明）边界的 **A 侧像素**（A 区内缩 1px，绝不画到 B / 透明一侧）描 1px 边。描边色缺省取**材质 A 的最暗可见色**，让描边与主体融合。

> 默认行为：`transition_style` 在**所有模式**下都缺省 `rounded`（含透明模式）。若希望透明模式下的孤岛带 1px 描边以防裸边，请显式传 `transition_style="outline"`。

## 产物

一次 dual_grid 任务在该任务 run 目录下产出：

- `dual_grid_atlas.png`：4×4 图集（`4W × 4H`），16 张瓦片按上表排布。
- `dual_grid_preview.png`：**应用预览**。代码用确定性种子随机一张世界格，按 dual-grid 规则铺成一片显示瓦片，直观展示无缝拼接效果（种子由 `name + material_a + material_b + transition_style` 哈希派生，同参数同预览，便于复现）。
- `materials/material_a.png`（+ 实心模式下的 `materials/material_b.png`）：合成所用的无缝材质源图，便于调试与复用。
- `meta.json`：记录 `asset_kind`、`material_a` / `material_b`、解析后的 texture kinds、`transition_style`、`transparent_mode`、`tile_size`、`atlas_size`、`convention`（`pix-dualgrid-v1`）、`mapping`（bitmask → cell 表）、`preview_seed` 等。

外部 API 的 `JobOutputResponse` 额外暴露 `dual_grid_atlas_path` / `dual_grid_atlas_url` 与 `dual_grid_preview_path` / `dual_grid_preview_url`，方便直接拿到图集与预览。

## 设计原则

- A、B 两张材质都是四边无缝纹理，瓦片只决定它们的**归属**（哪块像素属于谁），不改材质内容，因此同材质区域跨瓦片自动续接。
- 无缝性是构造保证而非生成约束 —— 不要寄望「让 AI 一次直出整张图集」，图像模型无法满足跨瓦片角拓扑对齐的组合约束。
- 透明模式适合做地块孤岛 / 边缘；需要防裸边时配合 `outline`。
- 单瓦片尺寸即 `output_size`（沿用 `tile_texture` 的 ≥16×16 限制），图集与预览都按它派生。
