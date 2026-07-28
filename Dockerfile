FROM ghcr.io/astral-sh/uv:0.11.32 AS uv
FROM python:3.13-slim

ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --locked --no-dev --extra postgres
RUN groupadd --gid "${APP_GID}" google-health-agent \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home google-health-agent \
    && mkdir -p /app/data /app/credentials /app/reports \
    && chown -R "${APP_UID}:${APP_GID}" /app/data /app/credentials /app/reports

USER google-health-agent

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()"]
CMD ["healthctl", "serve"]
