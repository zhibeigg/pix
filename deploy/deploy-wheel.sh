#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.production"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.wheel.yml"

if [ ! -f "$ENV_FILE" ]; then
  echo "缺少 $ENV_FILE"
  echo "请先执行：cp .env.production.example .env.production 并填入密钥"
  exit 1
fi

if ! ls "$SCRIPT_DIR"/pix-*.whl >/dev/null 2>&1; then
  echo "缺少 .whl 文件，请将 pix-x.y.z-py3-none-any.whl 放到部署目录"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

echo "==> 执行数据库迁移"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm migrate

echo "==> 构建并启动 Pix 后端"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo "==> 当前服务状态"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

echo "==> 健康检查"
sleep 3
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:${PIX_WEB_API_PORT:-8000}/health" || true
  echo
else
  echo "请手动访问：http://127.0.0.1:${PIX_WEB_API_PORT:-8000}/health"
fi
