## 变更摘要

-

## 原因与用户影响

-

## 验证

- [ ] `uv run ruff check ...`
- [ ] `uv run pytest -q`
- [ ] `uv run python scripts/check_release_version.py`
- [ ] `npm test -- --run`（如涉及前端）
- [ ] `npm run build`（如涉及前端）
- [ ] 已补充或更新测试

## 配置、文档与发布

- [ ] 已更新默认配置和示例配置（如适用）
- [ ] 已更新 README / API 文档 / 语言文案（如适用）
- [ ] 已更新版本号与 CHANGELOG（发布改动）
- [ ] 新增资产已说明来源与许可证

## 安全确认

- [ ] 不包含 `.env`、API Key、JWT Secret、数据库/支付凭据
- [ ] 不包含真实用户数据、生产日志或生成产物
- [ ] 未绕过 hooks 或提交被忽略文件
