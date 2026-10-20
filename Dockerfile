# Образ приложения (CLAUDE.md §12): backend; сборка SPA добавляется в IC-015 отдельной стадией node.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.11.32 \
    && useradd --create-home --uid 10001 app

WORKDIR /app/backend

# Сначала зависимости по lock-файлу: слой кэшируется, пока lock не меняется.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app

USER app
EXPOSE 8000

# Лаунчер: блокировка единственного экземпляра → миграции → uvicorn (один процесс).
CMD ["python", "-m", "app.core.launcher"]
