# 任务性能监控（管理后台）— 设计文档

- 日期：2026-06-15
- 状态：已与用户确认，准备实现
- 分支：`feat/task-performance-monitor`

## 1. 背景与目标

管理后台需要一个实时性能监控面板，查看生图任务的**成功率、并发、任务量时间序列、
provider 成功率对比、失败分类与最近任务流**。直接动机：胜算云上游接入后，需要能直观
对比 Packy / 胜算云 / Crazyrouter 的成功率，验证失败切换价值，并及时发现 `http_503`
这类上游故障。

## 2. 已确认的设计决策（用户拍板）

| 决策点 | 结论 |
|---|---|
| provider 维度 | 给 `generation_jobs` 加 `provider` 列（迁移 + worker 写入），可直接 SQL 聚合 |
| 时间范围 | 可切换 `1h / 24h / 7d`，按范围选分桶粒度 |
| 刷新方式 | 前端轮询（8s）调聚合接口 |
| 并发 | 实时 KPI = 当前 running 数（精确）；时序图用每桶启动任务数（吞吐近似，标注语义），不做精确瞬时并发时序（YAGNI） |
| 图表库 | 前端新增 `chart.js` + `react-chartjs-2` |
| 版本 | `1.73.0 → 1.74.0`（B 位：新增功能） |

## 3. 数据基础（已核实）

- `GenerationJob`（[models.py:282](../../../src/pix_web/models.py)）字段足够：`status`
  (pending/running/succeeded/failed/cancelled)、`job_type`、`failure_type/source/code`、
  `created_at/started_at/finished_at`、`price_credits`。
- `provider` **不在表中**，仅在任务 meta JSON 的 `image_gen.provider_history`
  （[pipeline_adapter.py](../../../src/pix_web/pipeline_adapter.py)）→ 故新增表列。
- [dashboard.py](../../../src/pix_web/dashboard.py) 已有"今日"聚合（`func.count`/`func.sum`/
  手写 p95），可参考其聚合风格；新功能新建独立 `metrics.py`，不塞进已不小的 dashboard。
- DB 兼容 SQLite（默认）与 Postgres → 时间分桶 SQL 需 dialect 适配。
- admin 端点模式：`@router.get(..., _admin: User = Depends(require_admin), db = Depends(get_db))`。
- 前端无图表库；后台 Radix `Tabs`（[AdminPanel.tsx](../../../apps/web/src/components/AdminPanel.tsx)）新增 Tab 模式清晰。

## 4. 架构 / 数据流

```
worker 完成任务 → 写 generation_jobs.provider（最终生效 provider）
                      ↓
前端轮询 GET /admin/performance-metrics?range=1h|24h|7d   (每 8s)
                      ↓
metrics.task_performance_metrics(db, range)
  ├─ 时间桶聚合（succeeded/failed/started per bucket）
  ├─ provider group by（成功/失败/成功率）
  ├─ failure_code group by
  ├─ 最近 12 个任务
  └─ 实时并发 = count(status='running')
                      ↓
PerformanceMonitorTab：Chart.js 渲染 KPI / 时序 / provider / 失败 / 任务流
```

## 5. 后端设计

### 5.1 迁移 `0016_job_provider`
`generation_jobs` 加 `provider VARCHAR(32) NOT NULL DEFAULT '' `，加索引。历史任务为空
（前端显示"未知"），不回填。

### 5.2 worker 写入 provider
任务落库成功/失败时，把最终生效（成功）或最后尝试（失败）的 `provider_id` 写入
`job.provider`。来源：`DispatchResult.image.provider_id`，或 meta 的 `provider_history`
最后一条。实现时定位 worker/pipeline_adapter 写 job 结果处。

### 5.3 `metrics.py`（新）
`task_performance_metrics(db, range: str) -> dict`：
- `range → (since, bucket_seconds)`：`1h→300s`、`24h→3600s`、`7d→86400s`
- **时间桶 helper**：`_bucket_expr(db, col, bucket_seconds)` 按 `db.bind.dialect.name`
  返回 SQLite（`strftime`）或 Postgres（`date_trunc`/`to_timestamp(floor(extract(epoch)/n)*n)`）表达式。
- 时序：`group by (bucket, status)` → 每桶 succeeded/failed/started 计数。
- provider：`group by provider, status` → 各 provider 成功/失败/成功率。
- 失败分类：`group by failure_code`（仅 failed）。
- 最近任务：`order by created_at desc limit 12`。
- KPI：range 内 total/failed/success_rate、avg/p95 耗时（`finished_at - started_at`）、
  实时 `running` 计数。

### 5.4 API
`GET /admin/performance-metrics?range=1h|24h|7d`，`Depends(require_admin)`。
响应（Pydantic model 放 [schemas.py](../../../src/pix_web/schemas.py)）：

```json
{
  "range": "24h", "bucket_seconds": 3600, "generated_at": "<iso>",
  "kpi": {"success_rate": 0.93, "running": 4, "total": 1280, "failed": 89,
          "avg_seconds": 28.5, "p95_seconds": 62.0},
  "series": [{"t": "<iso>", "succeeded": 40, "failed": 5, "started": 48}],
  "providers": [{"provider": "shengsuanyun", "succeeded": 188, "failed": 7, "success_rate": 0.96}],
  "failures": [{"code": "http_503", "count": 45}],
  "recent": [{"id": 935, "job_type": "sprite_sheet", "status": "failed",
              "provider": "packy", "failure_code": "http_503", "seconds": 9, "created_at": "<iso>"}]
}
```

非法 `range` → 回退 `24h`。

## 6. 前端设计
- 依赖：`package.json` 加 `chart.js@4` + `react-chartjs-2@5`。
- [AdminPanel.tsx](../../../apps/web/src/components/AdminPanel.tsx) 加 `<TabsTrigger value="performance">` +
  条件渲染 `<PerformanceMonitorTab token=... />`。
- `PerformanceMonitorTab.tsx`（新）：range 切换、`useEffect` 轮询（8s，组件卸载清理 timer）、
  KPI 卡、任务量+成功率时序图、吞吐时序、provider 成功率条、失败分类、任务流列表。
- [api.ts](../../../apps/web/src/api.ts) 加 `performanceMetrics(token, range)`；`types.ts` 加响应类型。
- i18n：`zh-CN.ts` / `en.ts` 加 `admin.performance.*` 文案。

## 7. 关键权衡
- **并发**：精确历史瞬时并发需 interval-overlap 查询，成本高 → 取实时 running KPI +
  吞吐时序近似。
- **SQL 跨库**：时间桶用 dialect helper 适配，避免硬编码。
- **provider 历史**：新列仅对接入后任务生效；上线初期 provider 图偏少，随新任务积累变准；
  历史任务归入"未知"。
- **聚合性能**：按站点任务量级（日百~千）SQL group by 足够；未来量大可加预聚合表或缓存。

## 8. 文件清单
- 后端：`migrations/versions/0016_job_provider.py`(新)、`models.py`、`metrics.py`(新)、
  `routers/admin.py`、`schemas.py`、`pipeline_adapter.py`/worker
- 前端：`package.json`、`AdminPanel.tsx`、`PerformanceMonitorTab.tsx`(新)、`api.ts`、
  `types.ts`、`locales/zh-CN.ts`、`locales/en.ts`
- 文档/版本：`README.md`、`CHANGELOG.md`、`pyproject.toml`/`__init__.py`/`package.json`/`uv.lock` → 1.74.0

## 9. 验证
- 后端：mock/内存 db 造任务，测 `task_performance_metrics` 的分桶、成功率、provider 聚合、
  失败分类、并发计数、range 回退；`pix-web-check` 自检。
- 前端：本地起后端 + 前端，用 preview 验证 Tab 渲染、range 切换、轮询刷新、图表无报错。

## 10. 非目标（YAGNI）
- 不做精确瞬时并发时序、不做 SSE 推送、不做告警/通知、不做导出、不回填历史 provider。
