"""Политика доступа маршрута: default deny (CLAUDE.md §9.2).

Каждый маршрут `/api` обязан объявить политику зависимостью `require(Policy.…)`.
`ensure_routes_have_policy` вызывается в `create_app` и роняет запуск, если политики нет
или публичный маршрут не входит в явный allow-list.
"""

from collections.abc import Awaitable, Callable, Iterable, Iterator
from enum import StrEnum
from typing import Protocol, cast

from fastapi import Depends, FastAPI, Request, params
from fastapi.dependencies.models import Dependant
from starlette.requests import HTTPConnection
from starlette.routing import BaseRoute

from app.common.exception import (
    ForbiddenError,
    NotAuthenticatedError,
    OrganizerCannotParticipateError,
)
from app.common.model import Actor
from app.core.logging import bind_log_context

API_PREFIX = "/api"

# Единственный список маршрутов без входа; расширяется только вместе с §9.2.
PUBLIC_API_PATHS = frozenset({"/api/health", "/api/auth/login", "/api/auth/register"})


class Policy(StrEnum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    EMPLOYEE = "employee"
    ORGANIZER = "organizer"
    E2E_ONLY = "e2e_only"


class RoutePolicyError(RuntimeError):
    """Маршрут объявлен без политики доступа или с недопустимой публичной."""


class Principal(Protocol):
    """Действующее лицо в терминах `core`: ядро не знает модуль `auth`, только эти два поля."""

    @property
    def user_id(self) -> int: ...

    @property
    def role(self) -> str: ...


# Резолвер подключает `main.py` (`app.state.actor_resolver`): по запросу или WebSocket-рукопожатию
# возвращает действующее лицо или `None`, если сессии нет, она истекла или отозвана.
ActorResolver = Callable[[HTTPConnection], Awaitable[Principal | None]]

ORGANIZER_ROLE = "organizer"
EMPLOYEE_ROLE = "employee"


class RequirePolicy:
    """Зависимость-маркер политики и её проверка.

    Порядок: нет входа → 401; вошёл, но роль не подходит → 403. Если резолвер не подключён
    (тесты, неполная сборка), любая политика кроме `PUBLIC` отвечает 401: маршрут, который
    забыли подключить к проверке личности, закрыт, а не открыт.
    """

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    async def __call__(self, connection: HTTPConnection) -> None:
        if self.policy is Policy.PUBLIC:
            return
        resolver: ActorResolver | None = getattr(connection.app.state, "actor_resolver", None)
        if self.policy is Policy.E2E_ONLY:
            # Тестовые маршруты открыты без входа, но только в режиме e2e (его включает
            # `TEST_CLOCK_ENABLED`, допустимый лишь при APP_ENV=e2e); иначе — как закрытые.
            if not connection.app.state.settings.test_clock_enabled:
                raise NotAuthenticatedError("Требуется вход в систему.")
            return
        actor = None
        if resolver is not None:
            actor = await resolver(connection)
        if connection.scope["type"] == "websocket":
            # Отказ до `accept` браузер видит лишь как обрыв без кода (1006), и вкладка не
            # поймёт, что нужно войти заново. Поэтому здесь только определяется личность
            # (`None` — не вошёл), а соединение принимает и закрывает кодом 4401/4403 сам
            # обработчик: он обязан проверить `state.actor`.
            connection.state.actor = actor
            return
        if actor is None:
            raise NotAuthenticatedError("Требуется вход в систему.")
        connection.state.actor = actor
        bind_log_context(user_id=actor.user_id)
        if self.policy is Policy.ORGANIZER and actor.role != ORGANIZER_ROLE:
            raise ForbiddenError("Действие доступно только организатору.")
        if self.policy is Policy.EMPLOYEE and actor.role != EMPLOYEE_ROLE:
            # Организатор видит результаты заранее, поэтому в конкурсе не участвует (§9.2).
            raise OrganizerCannotParticipateError("Организатор не подаёт идеи и не голосует.")


def require(policy: Policy) -> params.Depends:
    """Вернуть элемент `dependencies=[…]` маршрута или роутера."""
    dependency: params.Depends = Depends(RequirePolicy(policy))
    return dependency


def get_current_actor(request: Request) -> Actor:
    """Действующее лицо; доступно только на маршрутах с политикой, отличной от PUBLIC.

    Лежит в `core`, а не в `auth.controller`: контроллеры других модулей не импортируют
    чужие контроллеры (§4.2), а `Actor` — общий тип из `common.model`.
    """
    return cast(Actor, request.state.actor)


def _find_policies(dependant: Dependant) -> list[Policy]:
    found: list[Policy] = []
    for sub in dependant.dependencies:
        if isinstance(sub.call, RequirePolicy):
            found.append(sub.call.policy)
        found.extend(_find_policies(sub))
    return found


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def _effective_routes(routes: Iterable[BaseRoute]) -> Iterator[object]:
    """Маршруты приложения с учётом `include_router`.

    FastAPI ≥ 0.15x не копирует маршруты подключённых роутеров в `app.routes`, а кладёт туда
    обёртку `_IncludedRouter`; проверка, которая смотрит только на `app.routes`, молча пропустила
    бы все маршруты модулей. Обёртка отдаёт «эффективные» маршруты с зависимостями, добавленными
    при подключении, — именно их и нужно проверять.
    """
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if not callable(candidates):
            yield route
            continue
        for context in candidates():
            # У HTTP-маршрута контекст сам несёт `path` и `dependant`; у WebSocket и чужих
            # маршрутов реальный маршрут лежит в `starlette_route`.
            yield context.starlette_route or context


def _check_route(route: object) -> str | None:
    path = str(getattr(route, "path", ""))
    if not _is_api_path(path):
        return None  # статика SPA и fallback на index.html — вне /api
    dependant = getattr(route, "dependant", None)
    if not isinstance(dependant, Dependant):
        return f"{path}: маршрут /api не через FastAPI-роутер, политику не объявить"
    policies = _find_policies(dependant)
    if not policies:
        return f"{path}: не объявлена политика доступа"
    if Policy.PUBLIC in policies and path not in PUBLIC_API_PATHS:
        return f"{path}: публичный маршрут не входит в allow-list"
    return None


def list_api_paths(app: FastAPI) -> frozenset[str]:
    """Пути `/api`, которые видит проверка политик (нужно тесту: она не должна «ослепнуть»)."""
    paths = (str(getattr(route, "path", "")) for route in _effective_routes(app.routes))
    return frozenset(path for path in paths if _is_api_path(path))


def ensure_routes_have_policy(app: FastAPI) -> None:
    problems = [p for route in _effective_routes(app.routes) if (p := _check_route(route))]
    if problems:
        raise RoutePolicyError("Маршруты без допустимой политики:\n" + "\n".join(problems))
