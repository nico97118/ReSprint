FROM ghcr.io/astral-sh/uv:0.11.2 AS uv

FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --extra server --no-install-project

COPY README.md LICENSE NOTICE ./
COPY src ./src
RUN uv sync --locked --no-dev --extra server --no-editable

FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GUNICORN_CMD_ARGS="--bind=0.0.0.0:5000 --workers=2 --timeout=300 --no-control-socket --access-logfile=- --error-logfile=-"
WORKDIR /app

RUN groupadd --gid 10001 resprint \
    && useradd --uid 10001 --gid resprint --no-create-home resprint
COPY --from=build /app/.venv /app/.venv

USER resprint
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).close()"]
CMD ["gunicorn", "resprint.frontend.wsgi:create_application()"]
