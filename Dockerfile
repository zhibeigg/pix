FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.14-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --uid 10001 pix \
    && mkdir -p /app/outputs /app/web_outputs \
    && chown -R pix:pix /app

COPY --from=builder --chown=pix:pix /app/.venv /app/.venv
COPY --chown=pix:pix alembic.ini ./
COPY --chown=pix:pix migrations ./migrations

USER pix

EXPOSE 8000
STOPSIGNAL SIGTERM

CMD ["uvicorn", "pix_web.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
