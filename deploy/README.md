# Pix 后端部署包

这个目录是 Pix 后端的独立部署资料包，适合只部署 API、数据库、Redis 和后台 worker。

> 使用方式：把 `deploy/` 目录放在 Pix 项目根目录下，然后在项目根目录执行下面的命令。

## 包含文件

| 文件 | 作用 |
|---|---|
| `docker-compose.backend.yml` | 后端生产部署 Compose：PostgreSQL、Redis、migrate、API、worker |
| `.env.production.example` | 生产环境变量模板 |
| `Dockerfile.backend` | 后端镜像构建文件 |
| `nginx.pix-api.conf` | Nginx API 反向代理示例 |
| `scripts/deploy-backend.sh` | 一键迁移并启动后端 |
| `scripts/check-backend.sh` | 健康检查和部署前检查 |

## 服务器要求

- Linux 服务器，推荐 2C4G 起步。
- Docker Engine。
- Docker Compose v2，即 `docker compose` 命令。
- 已准备 Pix 项目源代码。
- 已准备 Packy API Key 或兼容的图像/视觉模型 Key。

## 第一次部署

### 1. 准备环境变量

在项目根目录执行：

```bash
cp deploy/.env.production.example deploy/.env.production
```

编辑 `deploy/.env.production`，至少替换这些值：

```env
POSTGRES_PASSWORD=换成强数据库密码
PACKY_API_KEY=sk-你的生图key
PACKY_VL_API_KEY=sk-你的视觉模型key
PIX_WEB_JWT_SECRET=至少32位随机字符串
PIX_WEB_PUBLIC_BASE_URL=https://api.your-domain.com
```

生成 JWT Secret 的示例：

```bash
openssl rand -hex 32
```

如果前端和后端不同域名，还需要设置：

```env
PIX_WEB_CORS_ORIGINS=https://your-frontend-domain.com
```

### 2. 执行数据库迁移

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production run --rm migrate
```

### 3. 启动后端

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production up -d --build
```

默认 API 暴露在：

```text
http://服务器IP:8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

返回类似下面内容表示 API 正常：

```json
{"ok":"true","version":"1.9.0"}
```

## 使用脚本部署

也可以直接执行：

```bash
bash deploy/scripts/deploy-backend.sh
```

脚本会自动执行迁移、构建、启动，并显示服务状态。

## 查看状态和日志

```bash
# 服务状态
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production ps

# API 日志
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production logs -f api

# worker 日志
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production logs -f worker
```

## 部署前检查

服务启动后执行：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production run --rm api pix-web-check
```

或使用脚本：

```bash
bash deploy/scripts/check-backend.sh
```

重点确认：

- `PIX_WEB_JWT_SECRET` 不是默认值，且长度至少 32。
- `PACKY_API_KEY` 已配置。
- 数据库可连接。
- Alembic 迁移已到最新版本。
- 存储目录可写。
- Redis/RQ 可连接。

## Nginx 反向代理

如果你有域名，建议用 Nginx/Caddy 反代到本机 `8000`，不要直接暴露后端端口。

Nginx 示例文件：

```text
deploy/nginx.pix-api.conf
```

将其中的：

```nginx
server_name api.example.com;
```

替换成你的域名，然后放到 Nginx 配置目录，例如：

```bash
sudo cp deploy/nginx.pix-api.conf /etc/nginx/sites-available/pix-api
sudo ln -s /etc/nginx/sites-available/pix-api /etc/nginx/sites-enabled/pix-api
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS 推荐使用 certbot 或云厂商证书。

## 更新版本

拉取新代码后执行：

```bash
git pull
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production run --rm migrate
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production up -d --build
```

## 扩容 worker

生成任务较多时可以增加 worker 数量：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production up -d --scale worker=2
```

## 备份数据库

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production exec -T postgres pg_dump -U pix pix > pix_backup.sql
```

如果你改过 `POSTGRES_USER` 或 `POSTGRES_DB`，把命令里的 `pix` 替换成实际值。

## 停止服务

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production down
```

如果要删除数据库、Redis 和输出文件卷，需要显式加 `-v`，请谨慎使用：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production down -v
```

## 常见问题

### 1. migrate 失败

先看数据库是否健康：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production ps
```

再看迁移日志：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production logs migrate
```

### 2. API 健康检查失败

查看 API 日志：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production logs -f api
```

常见原因是 `.env.production` 里密钥、数据库或 Redis 配置错误。

### 3. 任务一直不执行

查看 worker 是否运行：

```bash
docker compose -f deploy/docker-compose.backend.yml --env-file deploy/.env.production logs -f worker
```

确认 `PIX_WEB_QUEUE_BACKEND=rq`，且 `PIX_WEB_REDIS_URL=redis://redis:6379/0`。
