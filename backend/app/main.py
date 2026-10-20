"""Сборка приложения. `create_app` не обращается к БД и сети: его можно вызывать в тестах
и для экспорта OpenAPI (CLAUDE.md §8.1)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.controller import resolve_request_actor
from app.auth.controller import router as auth_router
from app.auth.service import AttemptLimiter, PasswordService, ensure_organizer
from app.core.access import ensure_routes_have_policy
from app.core.clock import Clock, SystemClock
from app.core.config import Settings
from app.core.db import Database
from app.core.health import router as health_router
from app.core.http_errors import install_error_handlers
from app.core.logging import get_logger
from app.core.middleware import (
    BodyGuardMiddleware,
    OriginGuardMiddleware,
    RequestContextMiddleware,
)
from app.core.singleton import SingletonLock

_log = get_logger(__name__)


def create_app(
    settings: Settings,
    database: Database | None = None,
    singleton: SingletonLock | None = None,
    clock: Clock | None = None,
    passwords: PasswordService | None = None,
    limiter: AttemptLimiter | None = None,
    bootstrap_organizer: bool = False,
) -> FastAPI:
    """`database`, `clock`, `passwords` подменяются в тестах; по умолчанию создаются из настроек
    (без подключения к БД). `singleton` и `bootstrap_organizer` передаёт лаунчер: `/api/health`
    отвечает 503, если блокировка потеряна, а организатор из окружения создаётся при старте."""
    database = database or Database(settings.database_url.get_secret_value())
    clock = clock or SystemClock()
    passwords = passwords or PasswordService()
    limiter = limiter or AttemptLimiter(per_ip_enabled=settings.rate_limit_per_ip_enabled)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if bootstrap_organizer:
            ensured = await ensure_organizer(
                database,
                passwords,
                clock,
                email=settings.organizer_email,
                name=settings.organizer_name,
                password=settings.organizer_password.get_secret_value(),
            )
            _log.info("organizer_ready", created=ensured.created, user_id=int(ensured.user.id))
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
    app.state.singleton = singleton
    app.state.draining = False
    app.state.clock = clock
    app.state.passwords = passwords
    app.state.limiter = limiter
    app.state.actor_resolver = resolve_request_actor

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    ensure_routes_have_policy(app)

    # add_middleware ставит последнюю добавленную прослойку снаружи.
    app.add_middleware(BodyGuardMiddleware)
    app.add_middleware(OriginGuardMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(RequestContextMiddleware)
    return app
