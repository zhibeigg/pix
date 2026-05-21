#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="deploy/docker-compose.backend.yml"
ENV_FILE="deploy/.env.production"

if [ ! -f "$ENV_FILE" ]; then
  echo "缺少 $ENV_FILE"
  echo "请先执行：cp deploy/.env.production.example deploy/.env.production"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "==> 服务状态"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

echo "==> 运行 pix-web-check"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm api pix-web-check

echo "==> API 健康检查"
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:${PIX_WEB_API_PORT:-8000}/health"
  echo
else
  echo "未安装 curl，请手动访问：http://127.0.0.1:${PIX_WEB_API_PORT:-8000}/health"
fi
