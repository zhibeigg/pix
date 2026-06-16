# 老部署同步提醒：旧 Provider 设置迁移到「上游供应商」

从 `1.78.0` 起，后台「模型与 API」不再展示旧 Packy / Gemini / VL 密钥入口。生图上游统一在后台「上游供应商」中管理。

## 发生了什么

以下旧后台设置入口已移除：

- `pix.api.base_url` / `PACKY_BASE_URL`
- `pix.api.image_api_key` / `PACKY_API_KEY`
- `pix.api.vl_api_key` / `PACKY_VL_API_KEY`
- `pix.api.gemini_api_key` / `PACKY_GEMINI_API_KEY`

仍然保留的「模型与 API」设置是运行策略和模型默认值，例如：

- `pix.api.timeout`
- `pix.api.max_retries`
- `pix.api.trust_env_proxies`
- `pix.api.proxy`
- `pix.image_gen.model`
- `pix.image_gen.failover_enabled`
- `pix.image_gen.model_discovery_enabled`

## 兼容说明

代码仍会读取旧环境变量作为老部署兼容 / 首次种子导入来源：

- `PACKY_API_KEY`
- `PACKY_BASE_URL`
- `PACKY_VL_API_KEY`
- `PACKY_GEMINI_API_KEY`
- `CRAZYROUTER_API_KEY`
- `CRAZYROUTER_BASE_URL`
- `SHENGSUANYUN_API_KEY`
- `SHENGSUANYUN_BASE_URL`
- `PIX_IMAGE_PROVIDERS_JSON`

首次启动时，如果数据库 `image_providers` 表为空，后端会从 `.env` 和 `config.toml` 的 `[[image_providers]]` 导入供应商作为种子。导入后，数据库中的「上游供应商」成为单一真相源。

> 重要：如果 `image_providers` 表已经有记录，后续修改 `.env` 的旧变量不会覆盖数据库供应商。请在后台「上游供应商」中编辑。

## 升级前检查清单

1. 备份数据库。
2. 备份当前 `.env` / `.env.production` / `config.toml`。
3. 确认旧环境变量至少保留到升级后首次成功启动：
   - `PACKY_API_KEY`
   - `PACKY_BASE_URL`
   - `PACKY_VL_API_KEY`
   - `PACKY_GEMINI_API_KEY`
   - `CRAZYROUTER_API_KEY`
   - `SHENGSUANYUN_API_KEY`
4. 如果你已经手动维护 `config.toml` 的 `[[image_providers]]`，确认其中的 `id`、`base_url`、`api_key_env`、`priority`、`protocols` 和 `models` 是最新值。

## 升级步骤

1. 拉取新版本代码。
2. 安装 / 更新依赖。
3. 执行数据库迁移到 head。
4. 启动 API 与 worker。
5. 用管理员账号进入后台。
6. 打开「上游供应商」。
7. 检查供应商是否已导入：
   - Packy
   - Crazyrouter
   - 胜算云 / ShengSuanYun
   - 其它 `config.toml` 中定义的供应商
8. 对每个供应商检查：
   - 是否启用；
   - Base URL 是否正确；
   - API Key 是否显示「已配置」；
   - priority 是否符合预期；
   - protocols / models 是否覆盖当前要用的模型。
9. 打开「模型与 API」检查运行策略：
   - Provider 调用超时；
   - 单家重试次数；
   - 是否启用失败切换；
   - 默认 logical model。
10. 发起一条低成本测试任务，确认任务记录中的 provider 符合预期。

## 升级后清理建议

确认「上游供应商」已经正确保存 API Key 后，可以逐步清理不再需要的旧环境变量，但建议至少保留一轮发布周期，方便回滚。

不要直接删除数据库里的 `image_providers` 表数据，除非你明确想重新从 `.env` / `config.toml` 种子导入。

## 常见问题

### 后台「模型与 API」找不到 Packy API Key 了怎么办？

这是预期行为。请到后台「上游供应商」中编辑 Packy 供应商。

### 修改 `.env` 的 `PACKY_API_KEY` 后为什么不生效？

如果 `image_providers` 表已有记录，数据库供应商优先。请在后台「上游供应商」中更新 API Key，或清空供应商表后重新种子导入。

### 老部署没有自动导入供应商怎么办？

检查：

1. `image_providers` 表是否已经非空；
2. `.env` 是否被进程读取；
3. `config.toml` 是否包含正确的 `[[image_providers]]`；
4. API 启动日志是否有数据库迁移或初始化错误。

### 还能继续使用 Packy 吗？

可以。只是 Packy 的配置入口迁移到了「上游供应商」，旧环境变量仅作为兼容 / 首次导入来源。
