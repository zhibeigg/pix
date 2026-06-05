#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Pix Forge · 一键构建 + 打包脚本
# 用法: bash scripts/build.sh [--skip-frontend] [--skip-backend] [--skip-package]
# 输出: dist/web/  dist/*.whl  dist/pix-deploy-{version}.tar.gz
# ──────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
SKIP_FRONTEND=false
SKIP_BACKEND=false
SKIP_PACKAGE=false

for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=true ;;
    --skip-backend)  SKIP_BACKEND=true ;;
    --skip-package)  SKIP_PACKAGE=true ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

# ── 读取版本号 ────────────────────────────────────────────────
VERSION=$(python3 -c "
import re, pathlib
text = pathlib.Path('$REPO_ROOT/pyproject.toml').read_text()
m = re.search(r'version\s*=\s*\"([^\"]+)\"', text)
print(m.group(1) if m else 'unknown')
")
echo "═══════════════════════════════════════════════════"
echo "  Pix Forge · 构建 v${VERSION}"
echo "═══════════════════════════════════════════════════"

mkdir -p "$DIST_DIR"

# ── 1. 前端构建 ──────────────────────────────────────────────
if [ "$SKIP_FRONTEND" = false ]; then
  echo ""
  echo "▸ [1/3] 构建前端 (React + Vite)..."
  cd "$REPO_ROOT/apps/web"
  npm run build
  echo "  ✔ 前端产物 → dist/web/"
else
  echo ""
  echo "▸ [1/3] 跳过前端构建"
fi

# ── 2. 后端 wheel ────────────────────────────────────────────
if [ "$SKIP_BACKEND" = false ]; then
  echo ""
  echo "▸ [2/3] 构建后端 wheel..."
  cd "$REPO_ROOT"
  if command -v uv &>/dev/null; then
    uv build --wheel --out-dir "$DIST_DIR"
  else
    python3 -m build --wheel --outdir "$DIST_DIR"
  fi
  echo "  ✔ wheel → dist/pix-${VERSION}-py3-none-any.whl"
else
  echo ""
  echo "▸ [2/3] 跳过后端构建"
fi

# ── 3. 打包 tar.gz ──────────────────────────────────────────
if [ "$SKIP_PACKAGE" = false ]; then
  echo ""
  echo "▸ [3/3] 打包部署归档..."

  # 清理旧版本 wheel，只保留当前版本
  for old_whl in "$DIST_DIR"/*.whl; do
    [ -f "$old_whl" ] && [[ "$old_whl" != *"${VERSION}"* ]] && rm -f "$old_whl" && echo "  清理旧 wheel: $(basename "$old_whl")"
  done

  STAGING="$DIST_DIR/.staging"
  rm -rf "$STAGING"
  mkdir -p "$STAGING/pix-deploy"

  # 前端静态资源
  if [ -d "$DIST_DIR/web" ]; then
    cp -r "$DIST_DIR/web" "$STAGING/pix-deploy/web"
  fi

  # Python wheel
  for whl in "$DIST_DIR"/*.whl; do
    [ -f "$whl" ] && cp "$whl" "$STAGING/pix-deploy/"
  done

  # 部署配置
  for f in Dockerfile docker-compose.yml alembic.ini pyproject.toml uv.lock; do
    [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$STAGING/pix-deploy/"
  done

  # 数据库迁移
  if [ -d "$REPO_ROOT/migrations" ]; then
    cp -r "$REPO_ROOT/migrations" "$STAGING/pix-deploy/"
  fi

  # 像素化预设资源
  if [ -d "$REPO_ROOT/assets" ]; then
    cp -r "$REPO_ROOT/assets" "$STAGING/pix-deploy/"
  fi

  # 前端 Dockerfile（如有独立的）
  if [ -f "$REPO_ROOT/apps/web/Dockerfile" ]; then
    cp "$REPO_ROOT/apps/web/Dockerfile" "$STAGING/pix-deploy/Dockerfile.web"
  fi

  ARCHIVE="pix-deploy-${VERSION}.tar.gz"
  tar -czf "$DIST_DIR/$ARCHIVE" -C "$STAGING" "pix-deploy"
  rm -rf "$STAGING"

  echo "  ✔ 部署归档 → dist/${ARCHIVE}"
else
  echo ""
  echo "▸ [3/3] 跳过打包"
fi

# ── 完成 ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  构建完成 · dist/ 目录内容:"
echo "───────────────────────────────────────────────────"
ls -lh "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz 2>/dev/null || true
ls -d "$DIST_DIR"/web 2>/dev/null && echo "  web/                  (前端静态资源)" || true
echo "═══════════════════════════════════════════════════"
