# Образ приложения (CLAUDE.md §12, Р1): SPA собирается стадией node и раздаётся тем же процессом.
FROM node:22-slim AS spa

WORKDIR /app/frontend

# Сначала зависимости по lock-файлу: слой кэшируется, пока lock не меняется.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# `npm run build` = проверка типов + vite build (openapi.json нужен для типов в frontend/).
COPY frontend/ ./
RUN npm run build


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
# Лаунчер ищет SPA в `frontend/dist` рядом с `backend/` (core/launcher.py: SPA_DIR).
COPY --from=spa /app/frontend/dist /app/frontend/dist

USER app
EXPOSE 8000

# Лаунчер: блокировка единственного экземпляра → миграции → uvicorn (один процесс).
CMD ["python", "-m", "app.core.launcher"]
