# 贡献指南

感谢你为 Pix 做出贡献。提交 PR 前请确保改动可复现、没有凭据，并通过与 CI 相同的检查。

## 开发环境

后端要求 Python 3.10–3.12，推荐使用 uv：

```bash
uv sync --frozen --extra dev
cp .env.example .env
uv run pix-web-api
```

前端要求 Node.js 22：

```bash
cd apps/web
npm ci
npm run dev
```

请只在本地 `.env` 中填写开发凭据，不要修改示例文件为真实值。

## 提交前检查

```bash
uv lock --check
uv run ruff check src tests scripts/check_release_version.py scripts/extract_release_notes.py
uv run pytest -q
uv run python scripts/check_release_version.py

cd apps/web
npm ci --no-audit --no-fund
npm test -- --run
npm run build
npm audit --audit-level=high
```

CI 会在 Python 3.10、3.11、3.12 上运行测试，并构建 Python 分发包和两个 Docker 镜像。本项目当前没有整仓 Ruff formatter 基线；请对本次触及的 Python 文件运行 `uv run ruff format <files...>`，不要为了小改动格式化无关文件。

## 测试与文档

- Bug 修复必须增加能复现旧行为的测试；
- 新功能需同步更新默认配置、示例配置、README、语言文案和外部 API 文档（如适用）；
- 不要删除已有 CHANGELOG；在顶部增加新版本条目；
- 新资产需在 PR 中说明来源、生成方式和许可证，参见 [ASSETS.md](ASSETS.md)。

## 版本号

版本格式为 `A.B.C`：

- `A`：公开接口发生不兼容变更；
- `B`：新增功能；
- `C`：Bug 或兼容性修复。

发布版本必须同步更新：

- `pyproject.toml`；
- `src/pix/__init__.py`；
- `apps/web/package.json`；
- `apps/web/package-lock.json`；
- `uv.lock`。

运行 `uv run python scripts/check_release_version.py` 可自动校验。Release 标签必须为同版本的 `vA.B.C`。

## 安全与仓库卫生

严禁提交：

- `.env`、API Key、JWT Secret、数据库/支付/邮件凭据；
- 真实用户上传、任务输出、生产日志或内部事故记录；
- `outputs/`、`web_outputs/`、`test/`、`dist/`、`build/` 等生成产物；
- 来源不明或无法再分发的图片、字体和模型；
- 与改动无关的大型二进制文件。

建议安装提交前扫描：

```bash
uv tool install pre-commit
pre-commit install
pre-commit run --all-files
```

发现漏洞或凭据泄漏时，不要公开提交 Issue，请按 [SECURITY.md](SECURITY.md) 私密报告。

## PR 规范

- 一个 PR 聚焦一个主题；
- 说明原因、用户影响、迁移方式和测试结果；
- 不绕过 hooks，不提交被忽略的本地文件；
- 尊重 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
