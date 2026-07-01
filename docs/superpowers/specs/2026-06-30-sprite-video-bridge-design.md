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
    "video_action_prompt": "从站立蓄力到挥剑释放一道蓝色剑气"
  }
}
```

- `mode` 缺省为 `mosaic`，保持旧任务兼容。
- `rows × cols` 仍决定最终抽帧数量和输出布局，至少 2 帧。
- `video_action_prompt` 可选；留空时回退到第一条 `row_prompts`，再回退到主 prompt。
- `reference_image_path` 仍可用于关键帧图生图。

## Pipeline

1. 生成一张左右双栏关键帧图：左栏为起始姿势，右栏为结束姿势。
2. 切分首帧/尾帧；每个半图先执行 perfectPixel 预处理，再用 key-color 转 alpha，按背景色与主体色块轮廓识别原始连通组件：保留主体轮廓和近邻组件、过滤远处孤立噪点，带安全边距裁剪后按统一尺寸/锚点铺回视频输入画布，转为 PNG data URL。
3. 构造视频补间 motion prompt：本地硬约束要求动作小步均匀连贯、每一帧都是清晰方块像素格、无抗锯齿/模糊/绘画化，并要求只有 flat key-color 背景可以接触画布边缘，任何非背景/非 key-color 像素都视为前景，包含主体、武器、烟雾、粒子、阴影、高光、拖尾和特效，必须完整留在内部安全区，禁止裁切/出界/触边。若 VL key 可用，会把整理后的首/尾视频输入帧和本地硬约束发送给 VL 模型生成 `optimized_motion_plan`，再附加到最终 Ark prompt；VL 不可用或解析失败时回退本地硬约束 prompt。随后调用 Ark `/contents/generations/tasks` 创建 Seedance 首尾帧图生视频异步任务。
4. 抛出 `VideoBridgeWaiting`，worker 将 job 置为 `waiting`，并在 `params_json.sprite.video_bridge_state` 保存：
   - `run_dir`
   - `ark_task_id`
   - `next_poll_at`
   - prompt、关键帧路径、Ark 原始响应等调试信息
5. 到期后 worker 重新领取 waiting job，查询 Ark 任务：
   - 未完成：更新 `next_poll_at`，继续 `waiting`
   - 失败/超时：标记失败并退款
   - 成功：立即下载视频到 `ark_video.mp4`
6. 用 `imageio` / `imageio-ffmpeg` 按最终帧数均匀抽帧。
7. 对抽取帧执行 key-color 去背景、统一 bbox、边缘处理、共享调色板。
8. 输出与 mosaic 兼容的 sprite 产物。

## Worker 状态机

新增 job status：`waiting`。

- `waiting` 不退款，不写 `finished_at`，不占用长时间运行的 worker 槽位。
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

## 配置

`[video_bridge]` 支持：

- `enabled`
- `provider`
- `base_url`
- `api_key`
- `model`
- `resolution`
- `ratio`
- `duration`
- `fps`
- `generate_audio`
- `watermark`
- `poll_interval_seconds`
- `task_timeout_seconds`
- `video_input_size`
- `max_base64_image_bytes`

环境变量：`ARK_API_KEY` / `VOLCENGINE_ARK_API_KEY`、`PIX_VIDEO_BRIDGE_ENABLED`、`PIX_VIDEO_BRIDGE_MODEL`、`PIX_VIDEO_BRIDGE_BASE_URL`、`PIX_VIDEO_BRIDGE_DURATION`。
