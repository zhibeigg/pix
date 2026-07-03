# 角色素材三视图（正/侧/背拼合图）设计

## 背景

素材类型「角色」（`asset_kind="character"`）原本只生成单张完整角色参考图。游戏开发常需要角色的多朝向设定图（turnaround sheet）作为美术参考，以及作为后续序列帧不同朝向的来源。逐张手动生成正 / 侧 / 背再拼接成本高、朝向 / 比例 / 配色难对齐。

## 目标

- 角色素材**默认生成一张横向排列的正 / 侧 / 背三视图拼合图**，同一角色、同比例、同调色板，仅朝向变化。
- 三视图是**单张成品 PNG**：不切分、不改输出模型，分享 / 角色库 / 下载全部天然兼容。
- 画布**自动横向 3 倍宽**：用户所选「像素尺寸」表示单视图尺寸，后端换算成拼合尺寸。
- 站内单张 / 批量面板与外部 API 一致；保留 `single` 模式便于回退与兼容。

## 范围

- 纳入：`job_type="asset"` 且 `asset_kind="character"` 的素材直出与参考图重绘（`image_to_image` 复用素材类型）。
- 不改：输出模型、worker 自动入库逻辑、分享筛选 / 展示（三视图作为单张 `pixelized` 图正常处理）。

## 数据模型与参数

- 新增请求字段 `asset.character_views: "single" | "three_view"`，默认 `three_view`。
- `AssetParamsSchema._normalize_subject_kind`：非 `character` 类型即便误传也强制回落 `single`，避免其它素材误带三视图标志。
- 该字段是请求级参数，不进 TOML 配置；三视图画布尺寸由前端单视图 `pixelize.output_size` 横向 ×3 推导。

## 尺寸换算（关键）

- 落点：`pipeline_adapter.asset_pixelize_params_from_json`。角色 + 三视图时把 `output_size` 宽度 ×3（如 `64x64 → 192x64`），高度不变。
- 同时**强制关闭** `auto_crop` / `crop_square`，避免把三列并排主体裁成单一主体。
- `size_retry` 的 target 取 `inputs.pixelize_params.output_size`，因而自然对齐三视图拼合尺寸，不会误判。
- 生图 API 侧：3:1 宽图走现有宽幅档位（1536×1024、2048×1024 等）+ perfectPixel extract → 透明填充路径，无需新管线。

## Prompt

- 落点：`pix.asset.build_asset_prompt` 新增 `character_views` 形参；角色 + 三视图走专用 `_canonical_character_three_view_prompt`，优先于通用 / 用户模板（否则会退化成单图措辞）。
- Prompt 要点：TURNAROUND SHEET；从左到右 FRONT / SIDE（左向侧身）/ BACK 三个等宽列；同角色、同比例、同服装、同配色，仅朝向变化，脚底基线对齐；保留纯色背景 chroma-key、`max_colors`、像素网格、禁止文字 / 视图标注 / 箭头 / 额外角色等。
- 参考图 appendix（`_asset_reference_prompt_appendix`）三视图分支：保留角色身份 / 剪影 / 服装 / 配色，重绘为三视图且三视图一致。
- `single` 模式保持原 `character` profile 与通用 prompt 不变（零回归）。

## 前端

- `SingleGeneratePanel` / `BatchGeneratePanel`：角色类型显示「生成三视图（正 / 侧 / 背）」开关，默认开启；提交时带 `asset.character_views`。三视图开启时像素尺寸控件标签显示为「单视图尺寸」。
- 复用（reuse）与参数快照（`JobParameterSnapshotDialog`）：透传并展示 `character_views`；缺省视为三视图，仅原任务显式 `single` 时关闭开关。
- 类型：`types.ts` 的 `AssetParams` 增加 `character_views?: 'single' | 'three_view'`。
- 文案：`locales/zh-CN.ts` / `en.ts` 的 `batchForm` 新增 `characterThreeViewLabel` / `characterThreeViewHint`。
- 外部 API 文档页（`ApiPage`）补 `character_views` 字段与中英说明。

## 预览

- `prompt_preview._asset_prompt_preview` 透传 `character_views` 并对三视图把预览尺寸 ×3，保证 `/jobs/prompt-preview` 与实际生成一致。

## 测试

- `tests/test_asset_prompt_background.py`：单图保持原断言 + 不含三视图措辞；新增三视图 prompt 断言（front/side/back、TURNAROUND、192x64、每列 64x64、抠色约束）；非角色误带标志不触发三视图。
- `tests/test_character_three_view.py`：schema 默认 / 归一、`_apply_character_three_view_size` 与 `asset_pixelize_params_from_json` 的 ×3 与关裁剪、prompt 分支。
- `tests/test_external_api.py`：角色 schema 用例补 `character_views` 默认值与非角色归一断言。

## 兼容性

- 旧角色任务无 `character_views` 字段：读取时缺省视为 `three_view`。若需精确复现历史单张角色，可在复用时手动关闭三视图开关，或外部显式传 `single`。
- 输出结构、分享、角色库、下载均不变；三视图为单张 PNG。
