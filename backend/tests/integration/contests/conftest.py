"""Фикстуры api-тестов конкурсов и идей: приложение на реальной БД и готовые участники.

Участники создаются сразу с сессией (без Argon2): тесты проверяют правила конкурса, а не вход.
"""

import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service.sessions import open_session
from app.common.model import UserId
from app.core.config import Settings
from app.core.db import Database
from app.main import create_app
from app.user import service as user_service
from app.user.model import UserRole
from tests.fakes import FrozenClock
from tests.unit.core.test_config import apply_env, base_env

ORIGIN = "http://127.0.0.1:8000"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
SUBMISSION_DEADLINE = NOW + timedelta(days=1)
VOTING_DEADLINE = NOW + timedelta(days=2)
MICROSECOND = timedelta(microseconds=1)


@dataclass(frozen=True)
class Person:
    id: UserId
    name: str
    cookie: str


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    apply_env(monkeypatch, base_env())
    return Settings()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def app(settings: Settings, database: Database, clock: FrozenClock) -> FastAPI:
    return create_app(settings, database, clock=clock)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=ORIGIN, headers={"Origin": ORIGIN}
    ) as http:
        yield http


PersonFactory = Callable[..., Awaitable[Person]]


@pytest.fixture
def make_person(database: Database, clock: FrozenClock) -> PersonFactory:
    async def make(name: str, role: UserRole = UserRole.EMPLOYEE) -> Person:
        token = secrets.token_urlsafe(32)

        async def work(session: AsyncSession) -> Person:
            ensured = await user_service.ensure_user(
                session,
                email=f"{name.lower()}@example.com",
                name=name,
                password_hash="not-a-real-hash",
                role=role,
                now=clock.now(),
            )
            await open_session(session, ensured.user, token, clock.now())
            return Person(ensured.user.id, name, token)

        return await database.run_in_transaction(work)

    return make


@pytest.fixture
async def organizer(make_person: PersonFactory) -> Person:
    return await make_person("Olga", UserRole.ORGANIZER)


@pytest.fixture
async def anna(make_person: PersonFactory) -> Person:
    return await make_person("Anna")


@pytest.fixture
async def boris(make_person: PersonFactory) -> Person:
    return await make_person("Boris")


async def call(
    client: httpx.AsyncClient,
    person: Person | None,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    headers = {} if person is None else {"cookie": f"sid={person.cookie}"}
    return await client.request(method, path, headers=headers, **kwargs)


def iso(moment: datetime) -> str:
    return moment.isoformat()


@pytest.fixture
def new_contest(client: httpx.AsyncClient, organizer: Person) -> Callable[..., Awaitable[int]]:
    async def create(
        *,
        topic: str = "Как улучшить офис",
        submission_deadline: datetime = SUBMISSION_DEADLINE,
        voting_deadline: datetime = VOTING_DEADLINE,
    ) -> int:
        response = await call(
            client,
            organizer,
            "POST",
            "/api/contests",
            json={
                "topic": topic,
                "description": "Принимаем любые идеи",
                "submission_deadline": iso(submission_deadline),
                "voting_deadline": iso(voting_deadline),
            },
        )
        assert response.status_code == 201, response.text
        return int(response.json()["id"])

    return create


@pytest.fixture
def new_idea(client: httpx.AsyncClient) -> Callable[..., Awaitable[httpx.Response]]:
    async def submit(
        person: Person,
        contest_id: int,
        *,
        title: str = "Кофе-поинт",
        description: str = "Поставить кофемашину на кухне",
        client_request_id: str | None = None,
    ) -> httpx.Response:
        return await call(
            client,
            person,
            "POST",
            f"/api/contests/{contest_id}/ideas",
            json={
                "title": title,
                "description": description,
                "client_request_id": client_request_id or str(uuid4()),
            },
        )

    return submit
