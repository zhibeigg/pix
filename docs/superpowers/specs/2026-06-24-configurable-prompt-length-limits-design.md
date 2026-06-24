# 可配置描述长度限制设计

## 背景

素材直出与序列帧的主体描述、额外风格描述和逐行动作描述原先散落在前端和后端硬编码中。管理员无法根据模型能力、运营策略或外部 API 客户端需求调整这些限制，且前端提示与后端校验存在漂移风险。

## 目标

- 将素材主体、素材额外描述、序列帧主体、序列帧逐行动作描述的长度限制纳入 Pix 配置。
- 管理后台可在线调整这些限制。
- 后端任务创建、批量创建、外部 API 创建、失败重试和 Worker 二次审核使用同一组运行时配置。
- 公开模型设置接口返回当前 limits，前端按接口值展示计数、超限提示并禁用提交。

## 配置项

新增默认配置：

```toml
[asset]
subject_max_chars = 160
extra_prompt_max_chars = 3000

[sprite]
subject_max_chars = 3000
row_prompt_max_chars = 600
```

对应后台系统设置：

- `pix.asset.subject_max_chars`：素材主体、Logo 标题、纹理主题、双瓦片材质 A/B 的最大字符数。
- `pix.asset.extra_prompt_max_chars`：素材额外风格描述最大字符数。
- `pix.sprite.subject_max_chars`：序列帧主体 / 角色描述最大字符数。
- `pix.sprite.row_prompt_max_chars`：序列帧每行动作描述最大字符数。

保存时按正整数校验，最小值为 1。

## 接口

`GET /settings/image-models` 与 `GET /external/v1/models` 返回：

```json
{
  "limits": {
    "prompt_max_chars": 3000,
    "raw_image_prompt_max_chars": 3000,
    "asset_subject_max_chars": 160,
    "asset_extra_prompt_max_chars": 3000,
    "sprite_subject_max_chars": 3000,
    "sprite_row_prompt_max_chars": 600
  }
}
```

`prompt_max_chars` / `raw_image_prompt_max_chars` 继续来自既有 `pix.image_gen.prompt_guard_max_chars`。新增四个字段来自 `[asset]` 与 `[sprite]` 配置。

## 后端校验路径

- `validate_job_request(req, cfg)` 按运行时 `AppConfig` 校验：
  - asset 主体与额外描述。
  - dual-grid 的 `material_a` / `material_b`。
  - sprite 主体 prompt 与 `row_prompts`。
  - raw text/image prompt 使用 `image_gen.prompt_guard_max_chars`。
- `create_job`、`create_jobs_batch`、`retry_failed_job`、`retry_failed_jobs_in_batch` 都加载数据库覆盖后的配置并传给校验。
- 外部 API 通过同一创建函数复用校验。
- Worker 中普通 asset、tile asset、dual-grid、sprite mosaic 和 raw image pipeline 的 prompt guard 上限均来自同一运行时配置，避免绕过创建阶段校验。

## 前端行为

- `ImageModelsResponse.limits` 通过 `promptLimitsFromModels()` 规范化，旧后端缺字段时使用默认值兜底。
- 单图面板：素材主体、额外描述、双瓦片材质、序列帧主体与逐行动作均显示计数，超限时显示错误并禁用提交。
- 批量面板：每行主体与额外风格描述按 limits 校验。
- 原图页面：提示词按 `raw_image_prompt_max_chars` 校验。

## 兼容性

- Pydantic Schema 只保留宽松安全硬上限，避免在读取运行时配置前被固定业务上限拦截。
- 未升级前端或旧后端缺少 `limits` 时，前端默认值仍保持旧行为。
- 现有任务参数不迁移；失败重试会按当前配置重新校验。