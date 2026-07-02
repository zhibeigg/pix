# 首尾帧视频补间序列帧设计

## 背景

现有 `sprite_sheet` 默认使用 `sprite.mode = "mosaic"`：一次生成 rows×cols 单图网格，再切分为序列帧。该方案速度快、成本可控，但复杂动作的补间连续性受单图模型限制。

新增 `sprite.mode = "video_bridge"`，在不替换 mosaic 的前提下，为单行动作提供“首尾关键帧 → 视频补间 → 抽帧”的生成路径。

## 请求契约

`job_type` 仍为 `sprite_sheet`，新增 sprite 参数：

```json
{
  "sprite": {
    "mode": "video_bridge",
    "rows": 1,
    "cols": 8,
    "fps": 8,
    "video_model": "doubao-seedance-2-0-260128",
    "video_action_prompt": "从站立蓄力到挥剑释放一道蓝色剑气"
  }
}
```

- 后端 schema 的 `mode` 缺省仍为 `mosaic`，保持旧任务兼容；生产工作台初始化与切回序列帧时默认进入 `video_bridge`。
- `rows × cols` 仍决定最终抽帧数量和输出布局，至少 2 帧。
- `video_model` 可选三档 Seedance 2.0 并透传 Ark：`doubao-seedance-2-0-260128`（Standard，默认）、`doubao-seedance-2-0-fast-260128`（Fast）、`doubao-seedance-2-0-mini-260615`（Mini）。
- Ark 视频生成时长由 `rows × cols × duration_ms` 推导并锁定，非整秒向上取整；这样视频补间时间轴与最终 GIF / 序列帧播放节奏一致，不再直接使用 `[video_bridge].duration` 覆盖任务节奏。
- `video_action_prompt` 可选；留空时回退到第一条 `row_prompts`，再回退到主 prompt。
- `reference_image_path` 仍可用于关键帧图生图。
- `pixelize.output_size`、`pixelize.colors`、`pixelize.edge_style/bg_feather`、`pixelize.generated_preprocess_method` 与 `pixelize.dither` 与 mosaic / 素材直出保持同一语义：分别控制最终单帧尺寸、颜色数、抽帧后边缘处理、视频帧 perfectPixel 预处理与限色抖动；这些参数也会写入关键帧 prompt 与 Ark motion prompt。
- 去杂色是 `video_bridge` 固定后处理，不新增用户开关：抽帧后会通过连通域保留主体及近邻特效，移除远离主体的孤立色点 / 杂色块。

## Pipeline

1. 生成一张左右双栏关键帧图：左栏为起始姿势，右栏为结束姿势。
2. 切分首帧/尾帧：不再固定按几何中线硬切，而是沿双栏横轴从 0 像素开始逐列扫掠，跳过开头同色背景，确认主体杂色段后，在下一段同色空隙与再下一段杂色之间取中线作为真实 gutter，避免尾帧后腿、披风、武器、粒子或烟雾越过中线时被裁掉；每个半图先执行 perfectPixel 预处理，再用 key-color 转 alpha，按背景色与主体色块轮廓识别原始连通组件：保留主体轮廓和近邻组件、过滤远处孤立噪点，带安全边距裁剪后按统一尺寸/锚点铺回视频输入画布，转为 PNG data URL。
3. 构造视频补间 motion prompt：按 Seedance 官方提示词指南组织为主体一致性、动作阶段、镜头/机位、节奏/过渡、像素风格和负面约束；本地硬约束要求 first_frame 与 last_frame 是首尾姿态硬约束，动作小步均匀连贯、每一帧都是清晰方块像素格、无抗锯齿/模糊/绘画化，并要求所有像素方块保持横平竖直的正交方块网格，禁止通过旋转、倾斜、斜切或菱形化像素块来模拟动作；并同步写入目标单帧尺寸、颜色上限、key-color / 容差和去杂色纪律（禁止孤立随机色点、压缩噪点、离体杂色块与逐帧颜色闪烁）。同时要求固定镜头/正交视角，只有 flat key-color 背景可以接触画布边缘，任何非背景/非 key-color 像素都视为前景，包含主体、武器、烟雾、粒子、阴影、高光、拖尾和特效，必须完整留在内部安全区，禁止裁切/出界/触边，禁止字幕、水印和额外角色。motion prompt 会写入 `rows×cols` 帧、`duration_ms` 单帧间隔和推导出的 Ark 秒数，要求模型把动作均匀分布在这段锁定时长内。若 `video_return_to_first_frame` 为 true，则 motion prompt 还会要求视频先到达尾帧姿势，再平滑回到首帧；Ark 的 last frame 输入会改用 first_frame，让最终视频帧匹配 first_frame，原本的 last_frame 图作为中途 peak/action target 由 prompt 与 VL motion plan 约束。若 VL key 可用，会把整理后的首/尾视频输入帧和本地硬约束发送给 VL 模型生成 `optimized_motion_plan`：OpenAI 兼容模型使用 `/v1/chat/completions`，Claude / Anthropic 模型直接使用 Anthropic 消息协议 `/v1/messages` 并以 image content block 传入首尾帧；成功后再把计划附加到最终 Ark prompt，VL 不可用或解析失败时回退本地硬约束 prompt。随后按推导出的 `ark_duration_seconds` 调用 Ark `POST /contents/generations/tasks` 创建 Seedance 首尾帧图生视频异步任务，payload 在 `content` 中分别提交 `role: "first_frame"` 与 `role: "last_frame"`，任务成功后从 `content.video_url` 取 MP4。
4. 抛出 `VideoBridgeWaiting`，worker 将 job 置为 `waiting`，并在 `params_json.sprite.video_bridge_state` 保存：
   - `run_dir`
   - `ark_task_id`
   - `next_poll_at`
   - 实际提交的 `model` / `video_model`
   - prompt、关键帧路径、`timing`（`frame_count` / `frame_duration_ms` / `total_duration_ms` / `ark_duration_seconds`）、Ark 原始响应等调试信息
5. 到期后 worker 重新领取 waiting job，查询 Ark 任务：
   - 未完成：更新 `next_poll_at`，继续 `waiting`
   - Ark 轮询/下载遇到可重试的上游网关、网络或超时错误：记录 `last_transient_error` / `transient_error_count`、延后 `next_poll_at`，继续 `waiting`
   - 失败/超时或不可重试错误：标记失败并退款
   - 成功：立即从 `content.video_url` 下载视频到 `ark_video.mp4`
6. 用 `imageio` / `imageio-ffmpeg` 按最终帧数均匀抽帧。
7. 对抽取帧先按 `generated_preprocess_method` 处理：`perfect_pixel` 模式会先对全部原始帧自动检测网格，统计众数网格尺寸，再用该众数作为固定 `grid_size` 对所有帧统一重跑 perfectPixel，并保留 perfectPixel 的实际输出尺寸而不是强制缩回 `pixelize.output_size`；随后执行 key-color 去背景、连通域去杂色，接着做 VL 限色盘（见下），再统一 bbox 裁剪、边缘处理。**限色盘默认走 VL 模型色阶（ramp），与素材直出模式一致**：把「去背景+去杂色后的主体帧」合成一张横向 mosaic 作为参考图，只调用一次 VL 生成整段序列共享的 ramp 色阶，再对每帧按 Lab 最近色量化到该 ramp；VL 不可用 / 调用失败 / 解析失败时优雅回退本地 `build_local_ramp`，绝不因限色盘失败而中断视频任务。仅当用户显式把 `pixelize.palette_mode` 设为 `kmeans` 时才回退旧的本地 K-means 逃生阀（`shared_palette=true` 跨帧共享，关闭时逐帧量化到 `pixelize.colors`）。VL 参考图取自去杂色后、裁剪前的主体帧，颜色未被裁剪 / 2 次幂透明填充破坏，因此限色盘结果与在“去杂色处”限色盘等价；实际逐帧量化在合并成精灵表前执行。最终透明帧不会缩放内容，而是按不小于检测尺寸、透明安全边和 `pixelize.output_size` 的最小 2 的幂 1:1 方形画布交付（如 106×106 → 128×128，四周补透明像素），确保任何非背景/非透明像素都不触碰成品帧边界。去杂色与去背景顺序不可颠倒，否则与背景色相近的主体颜色可能被误判为背景。
8. 输出与 mosaic 兼容的 sprite 产物。

## Worker 状态机

新增 job status：`waiting`。

- `waiting` 不退款，不写 `finished_at`，不占用长时间运行的 worker 槽位；可重试 Ark 瞬时错误也保持该状态，直到下一次 `next_poll_at` 重试或超过 `task_timeout_seconds`。
- 数据库 worker 在无 pending job 时会扫描到期 waiting job 并切回 `running` 处理。
- RQ 后端在超时清理循环里把到期 waiting job 重新 enqueue。
- 管理员可以取消 waiting job 或标记失败并退款。
- retention / 前端删除逻辑将 waiting 视为 active，避免清理未完成任务。

## 输出契约

成功后输出保持序列帧兼容：

- `sprite_sheet.png`：横向播放 sheet
- `sprite_sheet_grid.png`：rows×cols 网格预览
- `frames/raw/*.png`：视频原始抽帧
- `frames/final/*.png`：最终透明帧
- `sprite.gif`：按配置可选
- `sequence.json`：包含 `mode = "video_bridge"`、`source_video`、帧 rect、fps、rows/cols
- `meta.json`：包含 `video_bridge` 调用状态、抽帧采样信息、处理信息和标准 `sprite` 输出块

## 计费

`sprite.mode="mosaic"` 仍按 `ceil(rows·cols / 9) × sprite_sheet` 基础价计费。`sprite.mode="video_bridge"` 不再乘帧组数，而是按所选 Seedance 2.0 视频模型与飞书价格计算器 4–15 秒完整价格表单任务价计费。价格表为：Standard 1.85/2.31/2.77/3.23/3.70/4.16/4.62/5.08/5.54/6.01/6.47/6.93 元，Fast 1.49/1.86/2.23/2.60/2.97/3.34/3.72/4.09/4.46/4.83/5.20/5.57 元，Mini 0.92/1.16/1.39/1.62/1.85/2.08/2.31/2.54/2.77/3.00/3.23/3.47 元；点数按 `ceil(视频价格 × 20 + 10)` 得到 Standard 47/57/66/75/84/94/103/112/121/131/140/149，Fast 40/48/55/62/70/77/85/92/100/107/114/122，Mini 29/34/38/43/47/52/57/61/66/70/75/80，其中 10 点为首尾关键帧生图价。任务创建时会把模型、实际视频秒数、视频价格与折扣后的总点数写入 `params_json.billing` 快照。

## 配置

`[video_bridge]` 支持：

- `enabled`
- `provider`
- `base_url`
- `api_key`
- `model`（默认 Standard 档；任务级 `sprite.video_model` 存在时优先使用任务值）
- `resolution`
- `ratio`
- `duration`（旧配置兜底值；实际 Ark 秒数优先由 `rows×cols×duration_ms` 推导）
- `fps`
- `generate_audio`
- `watermark`
- `poll_interval_seconds`
- `task_timeout_seconds`
- `video_input_size`
- `max_base64_image_bytes`

环境变量：`ARK_API_KEY` / `VOLCENGINE_ARK_API_KEY`、`PIX_VIDEO_BRIDGE_ENABLED`、`PIX_VIDEO_BRIDGE_MODEL`、`PIX_VIDEO_BRIDGE_BASE_URL`、`PIX_VIDEO_BRIDGE_DURATION`（旧视频秒数兜底值；新任务实际秒数仍按 `rows×cols×duration_ms` 推导）。
