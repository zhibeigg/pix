# 素材直出多张同参数生成设计

## 背景

工作台「游戏素材直出」常用于抽取多个同主题候选图标、UI 组件、平铺纹理、Logo、双瓦片或角色。原流程每次只能提交一个 `job_type="asset"` 任务，用户需要重复点击提交，且每次都要等待前端表单状态与作品库跳转。

## 目标

- 在单张工作台素材直出面板提供「生成数量」控件，一次提交多张同参数素材。
- 保持核心生图流水线不变，不启用内部 `n_sample`、contact sheet 或候选拼图模式。
- 每张结果仍是独立作品：独立任务 ID、独立扣点/退款、独立排队、独立下载/分享/保存角色/重试。
- 复用现有 `/jobs/batch`、队列、每日限额、点数冻结、作品库和素材包批次下载能力。
- 对外 API 提供同等批量创建入口，便于脚本或插件一次提交多张同参数素材。

## 范围

纳入多张控件的类型：

- `job_type="asset"` 的物品图标、UI 组件、平铺纹理、Logo、双瓦片和角色。
- 素材直出中的参考图重绘（仍保留 `job_type="asset"`，通过 `input_image_path` 进入参考图链路）。

不纳入该控件的类型：

- `sprite_sheet` 序列帧。
- `local_pixelize`、`local_bg_remove`、`repixelize` 等本地处理或重试类任务。
- 原图生成页的普通文生图 / 图生图候选模式。

## 前端行为

- `SingleGeneratePanel` 在 `isAsset` 时显示生成数量输入，范围为 1～8。
- 数量为 1 时仍走原 `onSubmit(payload)` 单任务路径。
- 数量大于 1 时，前端复制当前 `JobCreateRequest` N 份，并为每份生成独立 `client_request_id`，调用 `onSubmitMany(payloads, batchName, "asset_multi")`。
- 顶部价格徽章通过 `EstimateBadge.repeat` 展示 `数量 × 单价 = 总价`，全局折扣开启时展示原总价、折后总价和每张折后价。
- `App.createJobs` 在提交前按真实任务数触发作品库保留数确认，提交成功后跳转作品库并选中第一张任务。

## 后端与外部 API

站内批量创建继续使用：

```http
POST /jobs/batch
```

外部 API 新增：

```http
POST /external/v1/jobs/batch
```

请求体复用 `JobBatchCreateRequest`：

```json
{
  "batch_name": "Blue sword draws",
  "mode": "asset_multi",
  "jobs": [
    {"job_type":"asset","client_request_id":"sword-001","asset":{"name":"Blue sword"}},
    {"job_type":"asset","client_request_id":"sword-002","asset":{"name":"Blue sword"}}
  ]
}
```

响应复用 `JobBatchCreateResponse`：

```json
{
  "jobs": [],
  "total_price_credits": 40,
  "batch_id": 123
}
```

实现细节：

- 外部接口使用 `jobs:create` scope。
- `create_jobs_batch` 仍负责逐个校验任务、冻结点数、写入 `GenerationBatch` 和创建独立 `GenerationJob`。
- 创建后只 enqueue `pending` 任务，保持和站内 `/jobs/batch` 一致。
- 外部 API 不使用单任务 `Idempotency-Key` header；需要幂等时由调用方为每个子任务设置稳定且不同的 `client_request_id`。

## 计费与兼容性

- 批量提交只改变创建方式，不改变单个素材任务价格。
- 全局折扣、尺寸重试的实际冻结与结算仍由后端批量创建和任务执行阶段决定。
- 旧客户端继续调用 `POST /jobs` 或 `POST /external/v1/jobs` 不受影响。
- 作品库、素材包下载、角色库自动保存、分享审核和失败重试均以独立任务为单位工作，无需迁移历史数据。
