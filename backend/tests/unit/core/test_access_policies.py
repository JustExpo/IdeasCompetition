"""Политики маршрутов с подключённым резолвером действующего лица (CLAUDE.md §9.2)."""

from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.requests import HTTPConnection

from app.core.access import Policy, Principal, require
from app.core.config import Settings
from app.main import create_app
from tests.fakes import ReadyDatabase
from tests.unit.core.test_config import apply_env, base_env, clean_env  # noqa: F401

ORIGIN = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class FakePrincipal:
    user_id: int
    role: str


async def header_resolver(connection: HTTPConnection) -> Principal | None:
    """Роль берётся из заголовка: проверяется сама политика, а не поиск сессии."""
    role = connection.headers.get("x-test-role")
    return None if role is None else FakePrincipal(user_id=7, role=role)


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    apply_env(monkeypatch, base_env())
    application = create_app(Settings(), ReadyDatabase("postgresql+asyncpg://x@127.0.0.1/x"))
    application.state.actor_resolver = header_resolver
    for policy in (Policy.AUTHENTICATED, Policy.EMPLOYEE, Policy.ORGANIZER, Policy.E2E_ONLY):

        def make(name: str = policy.value) -> None:
            @application.get(f"/api/probe/{name}", dependencies=[require(Policy(name))])
            async def probe() -> dict[str, str]:
                return {"ok": name}

        make()
    return application


async def call(app: FastAPI, policy: Policy, role: str | None) -> httpx.Response:
    headers = {} if role is None else {"x-test-role": role}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        return await client.get(f"/api/probe/{policy.value}", headers=headers)


# Строка таблицы истинности: политика × роль → статус и код ошибки.
@pytest.mark.parametrize(
    ("policy", "role", "status", "code"),
    [
        (Policy.AUTHENTICATED, None, 401, "not_authenticated"),
        (Policy.AUTHENTICATED, "employee", 200, None),
        (Policy.AUTHENTICATED, "organizer", 200, None),
        (Policy.EMPLOYEE, None, 401, "not_authenticated"),
        (Policy.EMPLOYEE, "employee", 200, None),
        (Policy.EMPLOYEE, "organizer", 403, "organizer_cannot_participate"),
        (Policy.ORGANIZER, None, 401, "not_authenticated"),
        (Policy.ORGANIZER, "employee", 403, "forbidden"),
        (Policy.ORGANIZER, "organizer", 200, None),
        # Тестовые маршруты закрыты вне режима e2e (в режиме e2e — `test_testing_clock.py`).
        (Policy.E2E_ONLY, "organizer", 401, "not_authenticated"),
    ],
)
async def test_policy_truth_table(
    app: FastAPI, policy: Policy, role: str | None, status: int, code: str | None
) -> None:
    response = await call(app, policy, role)
    assert response.status_code == status
    if code is not None:
        assert response.json()["code"] == code


async def test_actor_is_stored_for_route_handlers(app: FastAPI) -> None:
    seen: list[object] = []

    @app.get("/api/probe/actor", dependencies=[require(Policy.AUTHENTICATED)])
    async def probe(request: Request) -> None:
        seen.append(request.state.actor)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        await client.get("/api/probe/actor", headers={"x-test-role": "employee"})
    assert seen == [FakePrincipal(user_id=7, role="employee")]
