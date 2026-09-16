FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SANDBOX_WORKSPACES_ROOT=/app/data/workspaces

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY cli ./cli
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh

RUN pip install --no-cache-dir . \
    && chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/data/workspaces

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
