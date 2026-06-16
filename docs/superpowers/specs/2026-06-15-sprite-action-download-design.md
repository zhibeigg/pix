# 序列帧动作拆分下载 + 切分修复 — 设计文档

- 日期：2026-06-15
- 状态：已与用户确认，准备实现
- 分支：`feat/sprite-action-download`

## 1. 背景与目标

用户报告：一个 2 行 × 7 列的序列帧 mosaic（每行一个动作），下载得到的 `sprite_sheet.png`
把两个动作拼一起且切歪了（空帧、错位）。诊断确认两件事：

1. **切分 bug**：切分用了 `cols=8`，但模型只画了 7 列，按 8 等分切 7 列内容 → 每行第 5 个
   cell 落在列间隙上 → 空帧 + 整体错位。（已用真实 `_split_sheet_to_cells` 复现。）
2. **下载缺功能**：作品库已能选择动作，但下载选项没有「单个动作图」和「打包所有动作」。

目标：① 修切分让每个动作图干净；② 作品库下载增强：当前动作图 / 所有动作打包 + 统一命名。

## 2. 已确认决策

| 决策点 | 结论 |
|---|---|
| 打包内容 | 每个动作一张横向 PNG（`row_sheet`） |
| 命名规则 | `{作品名}_action{NN}_{动作名}.png`；zip 名 `{作品名}_sprite_actions.zip` |
| 切分修复 | 一并修：切分自动检测实际网格行/列数 |
| 版本 | `1.74.0 → 1.75.0`（B 位） |

## 3. 现状（已核实）

- 前端 `GalleryGrid.tsx`：`GalleryCard` 已有 `rowActions` 选择按钮 + `selectedAction`；
  `DownloadDialog` + `buildDownloadOptions` 多选下载、逐文件、无 zip；命名 `jobFileNamePrefix`
  （asset.name > prompt > job-id）。
- 后端 `schemas.py` `sprite_rows_outputs`：每行 `{row_index, frame_indices, action_phase,
  sheet_path, sheet_url, gif_path, gif_url}`。
- `row_sheets/row_NN.png` 由 `sprite_mosaic.py:979` 生成；文件访问 `GET /files?path=`。
- zip 范例：`packs.py` 的 `_build_pack_zip` / `download_pack`（可复用）。

## 4. Part 1：切分修复

### 4.1 `_detect_grid_count(projection, total, hint)`
1. `proj.max()<=0` 或 `hint<=1` → hint。
2. 内容区间 `[start,end)`：`proj > max*0.04` 的首尾。
3. `approx=span/hint`；`min_gap=max(2, approx*0.18)`。
4. 数低谷带：`proj <= max*0.06` 且连续宽度 `>= min_gap` 的区间数 `gaps`。
5. `detected = gaps + 1`。
6. **护栏**：仅当 `|detected-hint| <= max(1, round(hint/3))` 才返回 detected，否则 hint。

→ 正常作品（detected==hint）与主体填满作品（detected 远离 hint → 回退）不受影响；只有
「模型少画/多画且网格清晰」才修正。已验证此图：列 8→7、行 2→2。

### 4.2 `_split_sheet_to_cells`
- 行：`actual_rows = _detect_grid_count(row_proj, height, safe_rows)` 后切行。
- 列：每行列投影各检测，取众数为统一 `actual_cols`（保证 rows×cols 规整）。
- 用实际网格切；meta 增加 `detected_rows`/`detected_cols`。

### 4.3 pipeline 用实际网格（关键波及面）
`run_sprite_mosaic_pipeline` 原先直接用 `settings.rows/cols` 的后续改用实际网格
`effective_rows/effective_cols`：`rows_outputs` 循环与 `frame_indices`、
`compose_grid_sprite_sheet`、`_build_sequence_json` 的 rows/cols、`_write_mosaic_debug`。
检测值回灌到 `effective` 变量（不改 frozen settings），后续统一引用。

## 5. Part 2：下载增强

### 5.1 后端 zip API
`GET /jobs/{job_id}/sprite-actions.zip`（`routers/jobs.py`）：取当前用户 job（非本人/admin →
403/404），读 `meta_json_path` 的 `sprite.rows_outputs`，每行 `row_sheet` 加入 zip。内部命名
`{prefix}_action{NN}_{safe(phase)}.png`（phase 空则省略），zip 名 `{prefix}_sprite_actions.zip`；
prefix 复用 `_job_item_prefix`。无可打包行 → 409。复用 `ZipFile(ZIP_DEFLATED)` +
`Response(application/zip)`。

### 5.2 前端下载选项
`buildDownloadOptions`：`rowActions.length > 1` 且选中动作时追加：
- **当前动作图**：`url=selectedAction.sheet_url`，`filename={prefix}_action{NN}_{phase}.png`，走现有 `downloadImage`。
- **所有动作打包**：新 `DownloadKind='sprite_actions_zip'`，点击调 `api.downloadSpriteActions(token, jobId)` 下载 zip。
- 仅多动作序列帧作品显示。

### 5.3 api.ts
`downloadSpriteActions(token, jobId)`：参考 `downloadPack`/`downloadBlob`，GET zip 取 blob。

### 5.4 命名（统一前后端）
- 单动作 `{prefix}_action{NN}_{phase}.png`（NN 两位，phase 经清洗、空省略）；zip `{prefix}_sprite_actions.zip`。
- prefix 同口径：asset.name > prompt > job-id。

## 6. 文件清单
- 后端：`src/pix/sprite_mosaic.py`、`src/pix_web/routers/jobs.py`
- 前端：`apps/web/src/components/GalleryGrid.tsx`、`apps/web/src/api.ts`、可能 `types.ts`
- 文档/版本：`README.md`、`CHANGELOG.md`、`1.74.0 → 1.75.0`

## 7. 验证
- 切分：合成图 + 这张 mosaic 测 `_detect_grid_count`（cols=8→7、14 帧无空帧），并验证正常作品
  （参数正确 / 主体填满）切分不变（无回归）。
- zip API：mock job + meta 测打包文件数、命名、zip 名、空作品 409。
- 前端：`tsc + vite build`；preview 验证下载选项与命名。

## 8. 非目标
- 不做打包含 gif / 每帧拆分；不在浏览器端 zip；不改 rows>1 才生成 row_sheets 的策略。
