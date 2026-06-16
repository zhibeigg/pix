# 接入胜算云（ShengSuanYun）生图上游 — 设计文档

- 日期：2026-06-15
- 状态：已与用户确认，准备实现
- 分支：`feat/shengsuanyun-upstream`

## 1. 背景与目标

Pix 通过 `logical model → provider candidates` 的方式调用多个生图上游，按 `priority`
自动失败切换（现有 `crazyrouter`、`packy`）。本次新增第三个上游 **胜算云
（ShengSuanYun，`https://router.shengsuanyun.com`）**，作为 `gpt-image-2` 这个 logical
model 的又一个候选 provider，增强可用性与冗余。

## 2. 上游 API 形态（已核实）

胜算云图像生成是 **「OpenAI gpt-image 风格请求体 + 异步任务轮询」** 的组合：

### 提交任务
`POST /api/v1/tasks/generations`，`Authorization: Bearer <API_KEY>`，请求体：

```json
{
  "model": "openai/gpt-image-2",
  "prompt": "...",
  "n": 1,
  "size": "auto",
  "quality": "auto",
  "background": "auto",
  "moderation": "auto",
  "output_compression": 100,
  "image": "<base64 或公网 URL>"
}
```

- 必填：`model`、`prompt`。
- 图生图：同一端点，额外传 `image`（单图）或 `images`（数组），值可为 base64 或公网 URL。

提交响应（`code/message/data` 信封）：

```json
{
  "code": "success",
  "message": "",
  "data": {
    "request_id": "...",
    "task_id": "...",
    "action": "IMAGE_GENERATION",
    "status": "SUBMITTED",
    "fail_reason": "",
    "data": { "image_urls": [], "video_urls": [], ... }
  }
}
```

### 查询结果
`GET /api/v1/tasks/generations/{id}`（同样信封）：
- 状态字段：`data.status`，枚举（大写）：`SUBMITTING` / `SUBMITTED` / `IN_PROGRESS` /
  `COMPLETED` / `FAILED` / `CANCELLED`。
- 成功：`status == COMPLETED`，图片在 `data.data.image_urls[]`（**只返回 URL，无 base64**）。
- 失败：`status in {FAILED, CANCELLED}`，原因在 `data.fail_reason`。

## 3. 已确认的设计决策

| 决策点 | 结论 |
|---|---|
| 协议归属 | 新增独立协议 `shengsuanyun`（OpenAI 风格 body + 异步轮询，现有协议无一匹配） |
| 接入范围 | **仅单模型 `gpt-image-2`**（`provider_model = openai/gpt-image-2`），固定配置，不做在线发现 |
| 图生图 | 支持，复用同一异步端点 + 轮询，仅多传 `image` 字段 |
| 优先级 | `packy=10`（第一）、`shengsuanyun=20`（第二，新增）、`crazyrouter=30`（最后） |
| 启用方式 | 检测环境变量 `SHENGSUANYUN_API_KEY` 自动注入（与 crazyrouter 一致）+ 示例配置 |
| 版本号 | `1.72.0 → 1.73.0`（B 位：新增功能） |

### 为什么不做「模型自动发现」
- 胜算云**无文档化的图像模型列表端点**（无可靠的 `/api/v1/models` 图像发现）。
- 即便复用现有 `built_in_model()` 推断，`gpt-image-2` 会被标成**同步 `openai_images`
  协议**，而胜算云必须走**异步 `shengsuanyun` 协议** —— 协议标错会导致候选必然失败。
- 故采用固定单模型配置，协议正确、零发现开销；后续加模型只需在 `config.toml` 追加。

## 4. 实现要点

### 4.1 `ShengSuanYunProvider`（`src/pix/api/image_providers.py`）
- `generate(request)`：构造 OpenAI 风格 payload（`model=provider_model`、`prompt`、`n=1`，
  `size`/`quality` 在非 `auto` 且模型支持时下发；`background=auto`、`moderation=auto` 默认
  下发，`output_compression` 仅 jpeg/webp 时下发），`POST` 提交 → 取任务 ID → 轮询。
- `edit(request)`：要求 `image_path`，转 base64 data URL 作为 `image` 字段，其余复用
  `generate` 的提交 + 轮询逻辑。
- `_poll_task(task_id)`：异步轮询（复用 `_run_async_poll`），`deadline=cfg.api.timeout`、
  `interval=provider_poll_interval_seconds`；`COMPLETED` 返回、`FAILED`/`CANCELLED` 抛
  `ProviderError(category="provider_unavailable", fail_reason)`、超时抛
  `ProviderError(category="timeout")`。
- 任务 ID 提取：`data.request_id` 优先，回退 `data.task_id`（用户示例用 REQUEST_ID）。
- 结果提取：胜算云结果嵌套在 `data.data.image_urls[]`，现有 `pick_image_entry` 无法解析
  该结构，故在 Provider 内直接取 `image_urls[0]` 构造 `ImageProviderResult(url=...)`。
- 注册：`_PROVIDER_BY_PROTOCOL["shengsuanyun"] = ShengSuanYunProvider`。

### 4.2 配置注入（`src/pix/config.py`）
- 新增 `_shengsuanyun_provider_from_env()`：读 `SHENGSUANYUN_API_KEY`，base_url 取
  `SHENGSUANYUN_BASE_URL`（默认 `https://router.shengsuanyun.com`），`priority=20`，
  `protocols=["shengsuanyun"]`，`discover_models=false`，内置单个 `gpt-image-2` 模型
  （`provider_model="openai/gpt-image-2"`，operations 含文生图/图生图，
  `edit_mode="image_input"`）。
- `_normalize_image_providers()`：注入胜算云 provider。
- 调整既有优先级：`_crazyrouter_provider_from_env()` `priority 10→30`、
  `_packy_provider_from_legacy()` `priority 20→10`。

### 4.3 同步更新（遵循 CLAUDE.md「新增功能必须同步更新配置/文档」）
- `config.example.toml`：新增 `[[image_providers]]` 胜算云块 + 调整两家 priority。
- `.env.example` / `.env.production.example`：`SHENGSUANYUN_API_KEY` / `SHENGSUANYUN_BASE_URL`。
- `README.md`：环境变量表 + 「通用生图 Provider 调用规范」补充胜算云（异步 task 协议、新优先级）。
- `pyproject.toml`：版本 `1.73.0`；`CHANGELOG.md`：新增条目。
- 前端：生图下拉只暴露 `image2`、`gemini-3.1-flash-image-preview`、`gemini-3-pro-image-preview`；旧 `gpt-image-2` 会在后端归一为 `image2`。
- `image_model_registry.py`：通过 allowlist 控制可选模型，胜算云的 `image2` 上游真实模型仍为 `openai/gpt-image-2`。

## 5. 数据流

```
dispatch_image_request(model="image2", op=text_to_image)
  └─ candidates_for_model 按 priority 排序: packy(10) → shengsuanyun(20) → crazyrouter(30)
       └─ ShengSuanYunProvider.generate()
            ├─ POST /api/v1/tasks/generations  → data.request_id
            ├─ 轮询 GET /api/v1/tasks/generations/{request_id} 直到 COMPLETED
            └─ ImageProviderResult(url = data.data.image_urls[0])
       └─ 失败且属 failover_on 类别 → 切换下一候选
```

## 6. 错误处理
- 提交无 ID → `ProviderError(malformed_response)`。
- 轮询 `FAILED`/`CANCELLED` → `ProviderError(provider_unavailable, fail_reason)`（可失败切换）。
- 轮询超时 → `ProviderError(timeout)`（可失败切换）。
- 缺 `image_urls` → `ProviderError(empty_response)`。
- 缺 API key → 复用 `BaseImageProvider` 的 `auth` 错误。

## 7. 验证策略（项目无测试框架）
- 用 mock `ProviderHttpClient` 验证：payload 构造（文生图/图生图字段）、轮询状态机
  （SUBMITTED→IN_PROGRESS→COMPLETED 成功、FAILED 报错、超时报错）、`image_urls` 提取。
- `pix-web-check` 配置自检确认 provider 正确注册、优先级排序正确。
- 若用户提供真实 `SHENGSUANYUN_API_KEY`，跑一次端到端冒烟。

## 8. 实测结论（2026-06-15 真实 key 端到端验证通过）
用真实 `SHENGSUANYUN_API_KEY` 跑 ShengSuanYunProvider 真实代码路径：文生图 31s、图生图
75.9s 均成功出图（结果为胜算云 OSS 图片 URL）。原"待实测"细节全部确认：
- 查询路径用 `data.request_id` 轮询成功（代码同时兼容 `task_id`）。
- 图生图 `image` 用 base64 data URL **被胜算云接受**（排除"仅支持 URL"风险）。
- `background`/`moderation` 默认下发 `auto`、`output_compression` 仅 jpeg/webp 下发，均正常。
- 胜算云结果只返回图片 URL（无 base64），下游 URL 下载兜底已覆盖。
