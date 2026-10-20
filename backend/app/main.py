"""Сборка приложения. `create_app` не обращается к БД и сети: его можно вызывать в тестах
и для экспорта OpenAPI (CLAUDE.md §8.1)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.access import ensure_routes_have_policy
from app.core.config import Settings
from app.core.db import Database
from app.core.health import router as health_router
from app.core.http_errors import install_error_handlers
from app.core.middleware import (
    BodyGuardMiddleware,
    OriginGuardMiddleware,
    RequestContextMiddleware,
)


def create_app(settings: Settings, database: Database | None = None) -> FastAPI:
    """`database` подменяется в тестах; по умолчанию создаётся из настроек (без подключения)."""
    database = database or Database(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await database.dispose()

    # Swagger UI и ReDoc отключены: они тянут скрипты с CDN, а контракт берётся из app.openapi().
    app = FastAPI(
        title="Конкурс идей",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database

    install_error_handlers(app)
    app.include_router(health_router)
    ensure_routes_have_policy(app)

    # add_middleware ставит последнюю добавленную прослойку снаружи.
    app.add_middleware(BodyGuardMiddleware)
    app.add_middleware(OriginGuardMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(RequestContextMiddleware)
    return app
