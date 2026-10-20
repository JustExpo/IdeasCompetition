"""Политика доступа маршрута: default deny (CLAUDE.md §9.2).

Каждый маршрут `/api` обязан объявить политику зависимостью `require(Policy.…)`.
`ensure_routes_have_policy` вызывается в `create_app` и роняет запуск, если политики нет
или публичный маршрут не входит в явный allow-list.
"""

from enum import StrEnum

from fastapi import Depends, FastAPI, params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import BaseRoute

from app.common.exception import NotAuthenticatedError

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


class RequirePolicy:
    """Зависимость-маркер политики.

    Пока нет сессий (IC-007), любая политика кроме `PUBLIC` отвечает 401: маршрут,
    который забыли подключить к проверке личности, закрыт, а не открыт.
    """

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    async def __call__(self) -> None:
        if self.policy is not Policy.PUBLIC:
            raise NotAuthenticatedError("Требуется вход в систему.")


def require(policy: Policy) -> params.Depends:
    """Вернуть элемент `dependencies=[…]` маршрута или роутера."""
    dependency: params.Depends = Depends(RequirePolicy(policy))
    return dependency


def _find_policies(dependant: Dependant) -> list[Policy]:
    found: list[Policy] = []
    for sub in dependant.dependencies:
        if isinstance(sub.call, RequirePolicy):
            found.append(sub.call.policy)
        found.extend(_find_policies(sub))
    return found


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def _check_route(route: BaseRoute) -> str | None:
    path = getattr(route, "path", "")
    if not _is_api_path(path):
        return None  # статика SPA и fallback на index.html — вне /api
    if not isinstance(route, APIRoute | APIWebSocketRoute):
        return f"{path}: маршрут /api не через FastAPI-роутер, политику не объявить"
    policies = _find_policies(route.dependant)
    if not policies:
        return f"{path}: не объявлена политика доступа"
    if Policy.PUBLIC in policies and path not in PUBLIC_API_PATHS:
        return f"{path}: публичный маршрут не входит в allow-list"
    return None


def ensure_routes_have_policy(app: FastAPI) -> None:
    problems = [p for route in app.routes if (p := _check_route(route)) is not None]
    if problems:
        raise RoutePolicyError("Маршруты без допустимой политики:\n" + "\n".join(problems))
