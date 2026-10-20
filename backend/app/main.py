"""Сборка приложения. `create_app` не обращается к БД и сети: его можно вызывать в тестах
и для экспорта OpenAPI (CLAUDE.md §8.1)."""

from fastapi import FastAPI

from app.core.access import ensure_routes_have_policy
from app.core.config import Settings
from app.core.health import router as health_router
from app.core.http_errors import install_error_handlers
from app.core.middleware import (
    BodyGuardMiddleware,
    OriginGuardMiddleware,
    RequestContextMiddleware,
)


def create_app(settings: Settings) -> FastAPI:
    # Swagger UI и ReDoc отключены: они тянут скрипты с CDN, а контракт берётся из app.openapi().
    app = FastAPI(
        title="Конкурс идей",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings

    install_error_handlers(app)
    app.include_router(health_router)
    ensure_routes_have_policy(app)

    # add_middleware ставит последнюю добавленную прослойку снаружи.
    app.add_middleware(BodyGuardMiddleware)
    app.add_middleware(OriginGuardMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(RequestContextMiddleware)
    return app
