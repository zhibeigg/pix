# Pix 后端优化建议

本文档用于交给后端开发者排查和优化当前任务失败量增多的问题。

## 背景

当前线上后端服务本身健康，`/api/health` 正常返回当前版本。

近期失败量增多主要观察到几类情况：

- 提示词策略拦截，例如用户输入“直接抄袭参考图”。
- 上游模型/API 临时错误，例如 `HTTP 503`。
- 长时间卡住的运行中任务，例如 `job-319` 曾处于 `running` 超过 20 小时。
- 成功任务内部候选阶段出现大量错误，例如 `external_backend_error: cannot unpack non-iterable NoneType object`。
- `grid_detection_failed` 等候选/中间步骤失败被计入异常量，容易和最终任务失败混淆。

## 1. 增加超时任务清理机制

建议后台定时扫描：

```text
status = running
started_at 超过 30-60 分钟
finished_at 为空
```

处理逻辑：

```text
标记 failed
写入 error_message = 任务运行超时，系统自动清理
调用 refund_reserved()
释放 reserved_credits
记录退款流水
```

目标是避免任务长期卡在 `running`，同时避免用户点数一直被冻结。

## 2. 区分失败类型

建议给任务增加结构化失败字段：

```text
failure_type
failure_source
failure_code
```

建议分类：

```text
policy_blocked      提示词策略拦截
upstream_error      上游模型/API 错误，例如 HTTP 503
timeout             任务超时
pipeline_error      后端流水线异常
candidate_warning   候选内部失败但最终任务成功
```

前端统计不要只显示 `failed` 总数，否则无法判断是用户输入问题、上游问题还是系统问题。

## 3. 将 prompt guard 前置

类似以下提示词：

```text
直接抄袭这个参考图
```

建议在创建任务前完成校验：

```text
不进入队列
不冻结点数
不计入生成失败
直接提示用户修改描述
```

建议提示语：

```text
该请求涉及直接复刻参考图，请改为“参考风格/构图，重新设计原创素材”。
```

如果当前架构必须进入队列后校验，也应快速失败并退款，并把失败类型标记为 `policy_blocked`。

## 4. 增加上游错误重试

对临时性上游错误做退避重试：

```text
HTTP 429
HTTP 500
HTTP 502
HTTP 503
HTTP 504
connection reset
timeout
```

建议策略：

```text
最多重试 2-3 次
间隔 2s / 5s / 10s
仍失败后标记 failed
释放/退还预留点数
```

不要对策略错误重试，例如 `policy_blocked`。

## 5. 候选内部错误不要算最终失败

目前观察到部分最终成功的任务内部有大量候选错误：

```text
external_backend_error: cannot unpack non-iterable NoneType object
grid_detection_failed
```

建议单独统计为：

```text
candidate_failures
pipeline_warnings
```

这些不应和最终任务 `failed` 混为一类。

## 6. 修复 external_backend_error

重点排查以下异常：

```text
cannot unpack non-iterable NoneType object
```

疑似原因：

```text
perfect pixel / grid detection 外部 backend 返回 None
调用方直接解包 None
```

建议改成显式判断：

```python
result = external_backend(...)
if result is None:
    # 记录明确原因，并 fallback 到 builtin_numpy
    raise RuntimeError("external backend returned None")
```

或者：

```python
result = external_backend(...)
if result is None:
    log_warning(...)
    return builtin_numpy_backend(...)
```

目标是避免 `NoneType` 解包异常重复刷日志，并让错误信息更可定位。

## 7. 管理后台增加任务操作

建议管理员后台增加：

```text
重试任务
取消任务
标记失败并退款
查看失败原因
查看上游错误
查看任务运行时长
```

这样可以避免每次手动进数据库清理任务。

## 8. 增加指标面板

建议至少展示：

```text
最终成功数
最终失败数
策略拦截数
上游错误数
超时任务数
运行中超过 30 分钟任务数
候选内部失败次数
平均生成耗时
P95 生成耗时
```

这样后续出现“失败量增多”时，可以快速定位是外部模型、用户输入、任务超时还是后端 pipeline 问题。

## 9. 当前已确认案例

已观察到的典型问题：

```text
job-319:
  状态曾长期 running
  原因：任务运行超时未自动清理
  处理：手动标记 failed，并退还 10 点预留点数

job-352 / job-353:
  类型：image_to_image
  原因：提示词包含“直接抄袭参考图”
  建议：prompt guard 前置，不进入队列

job-354:
  类型：asset
  原因：上游 HTTP 503
  建议：增加临时错误重试

job-360:
  最终状态：succeeded
  内部现象：大量 external_backend_error
  建议：候选内部错误单独统计，不算最终失败
```

## 优先级建议

建议按以下顺序实施：

1. 超时任务自动清理和退款。
2. 失败类型结构化。
3. prompt guard 前置。
4. 上游错误退避重试。
5. 修复 `external_backend_error` 的 `NoneType` 解包问题。
6. 管理后台任务操作和指标面板。
