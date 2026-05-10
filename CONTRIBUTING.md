# Contributing to pix

欢迎贡献！在提 PR 之前请花两分钟读完本文。

## 开发环境

```bash
git clone https://github.com/zhibeigg/pix
cd pix

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -e ".[dev]"
```

## 编码规范

- **Python 3.10+**，尽量用类型标注。
- 代码风格由 `ruff` 统一，CI 会跑 `ruff check`。
- 不要往 `Bukkit`/主线程 之类的概念迁移，这是 Python 项目；但请遵守：
  - 数据库/网络 I/O 必须放在 `httpx` 或异步环境里处理，**GUI 主线程**只发信号
  - 优先 Kotlin 风格的空安全思维：显式判空、`Optional[X]`，避免 `assert x is not None` 当运行时保险
  - 捕获异常时用 `except Exception` 并给出明确日志，不要裸 `except:`

## 提交前

本地至少跑通：

```bash
ruff check .                       # lint
pytest                             # 全量测试
QT_QPA_PLATFORM=minimal pytest     # GUI 相关必须跑
```

- 新功能必须配套测试；bug 修复至少要有一个能复现 bug 的回归用例。
- 改动涉及 GUI/CLI 的文案时，务必**同步更新 9 种语言 catalog**（`src/pix/i18n_catalog.py`）。测试 `test_languages_have_all_default_keys` 会帮你兜底检查。
- 新增 CLI 子命令或改变现有命令的行为时，同步更新：
  - `README.md` 里的 CLI 表格
  - `CHANGELOG.md` 的 `[Unreleased]` 段
  - 如有必要，`config.example.toml` 里的默认值

## Commit 风格

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat: add batch subcommand
fix: preview_panel crash on missing file
docs: clarify API key instructions
ci: upgrade actions to v5/v6
refactor: split combo_keys module
test: cover vision retry-on-parse path
```

## 分支 / PR

- 从 `master` 开分支：`feat/batch-command`、`fix/preview-crash` 这种。
- 一个 PR 聚焦一件事。
- PR 描述请写清楚**为什么**和**怎么验证**，模板里会问。
- PR 标题会被用来生成 Release Notes，所以要清晰。

## 版本号

遵循 `A.B.C` 三段：

- `A`：公开接口不兼容变更
- `B`：新功能
- `C`：bug 修复 / 兼容性修复

发布时由维护者打 tag，`v<A>.<B>.<C>`，CI 会自动构建四平台产物并发布。

## 行为准则

保持善意和专业。项目目标是做一个好用的小工具，不是政治广场。人身攻击、骚扰、歧视言论会被立刻清除。
