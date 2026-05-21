FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE alembic.ini ./
COPY src ./src
COPY migrations ./migrations

RUN pip install --upgrade pip \
    && pip install -e ".[web]"

EXPOSE 8000

CMD ["uvicorn", "pix_web.main:app", "--host", "0.0.0.0", "--port", "8000"]
