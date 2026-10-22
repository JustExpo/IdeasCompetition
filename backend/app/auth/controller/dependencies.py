"""Связка запроса с модулем сессий: cookie и действующее лицо."""

from typing import Final

from starlette.requests import HTTPConnection

from app.auth.model import Actor
from app.auth.service import SESSION_LIFETIME, resolve_actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import Database

COOKIE_NAME: Final = "sid"
# Префикс `__Host-` браузер принимает только с Secure, Path=/ и без Domain: cookie нельзя
# подменить с поддомена. В dev и e2e (http) такой cookie не сохранился бы.
PROD_COOKIE_NAME: Final = "__Host-sid"
COOKIE_MAX_AGE_S: Final = int(SESSION_LIFETIME.total_seconds())


def is_secure_cookie(settings: Settings) -> bool:
    return settings.app_env == "prod"


def session_cookie_name(settings: Settings) -> str:
    return PROD_COOKIE_NAME if is_secure_cookie(settings) else COOKIE_NAME


async def resolve_request_actor(connection: HTTPConnection) -> Actor | None:
    """Резолвер для `core.access`: достаёт токен из cookie и ищет действующую сессию."""
    state = connection.app.state
    token = connection.cookies.get(session_cookie_name(state.settings))
    if not token:
        return None
    database: Database = state.database
    clock: Clock = state.clock
    return await resolve_actor(database, clock, token)
