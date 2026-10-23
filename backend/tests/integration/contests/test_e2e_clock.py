"""Тестовые часы e2e на настоящей БД: сдвиг ведёт к финалу и письмам без ожидания (IC-026)."""

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

from app.core.clock import SystemClock
from app.core.config import Settings
from app.core.db import Database
from app.main import create_app
from tests.fakes import FakeMailSender, FrozenClock
from tests.integration.contests.conftest import Person, PersonFactory, call
from tests.integration.contests.mailbox import outbox_rows
from tests.unit.core.test_config import apply_env, base_env

pytestmark = pytest.mark.commits

HOUR = timedelta(hours=1)
Origin = "http://127.0.0.1:8000"


@pytest.fixture
def clock() -> FrozenClock:
    # Сессии людей создаются от настоящего «сейчас»: часы e2e стартуют с него же.
    return FrozenClock(SystemClock().now())


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    apply_env(
        monkeypatch,
        base_env(
            APP_ENV="e2e",
            DATABASE_URL="postgresql+asyncpg://u:p@db/ideas_e2e",
            TEST_CLOCK_ENABLED="true",
            RATE_LIMIT_PER_IP_ENABLED="false",
        ),
    )
    return Settings()


@pytest.fixture
def mail() -> FakeMailSender:
    return FakeMailSender()


@pytest.fixture
def app(settings: Settings, database: Database, mail: FakeMailSender) -> FastAPI:
    return create_app(settings, database, email_sender=mail)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=Origin, headers={"Origin": Origin}
    ) as http:
        yield http


async def test_moving_the_clock_finishes_the_contest_and_sends_mail(
    app: FastAPI,
    client: httpx.AsyncClient,
    mail: FakeMailSender,
    database: Database,
    make_person: PersonFactory,
    new_contest: Callable[..., Awaitable[int]],
    new_idea: Callable[..., Awaitable[httpx.Response]],
    anna: Person,
    boris: Person,
) -> None:
    now = app.state.clock.now()
    submission_deadline, voting_deadline = now + HOUR, now + 2 * HOUR
    contest_id = await new_contest(
        submission_deadline=submission_deadline, voting_deadline=voting_deadline
    )
    anna_idea = (await new_idea(anna, contest_id, title="Идея Анны")).json()["id"]
    await new_idea(boris, contest_id, title="Идея Бориса")

    async def move_to(moment: str) -> httpx.Response:
        return await client.post("/api/__test__/clock", json={"now": moment})

    assert (
        await move_to((submission_deadline + timedelta(seconds=1)).isoformat())
    ).status_code == 204
    response = await call(client, boris, "GET", f"/api/contests/{contest_id}")
    assert response.json()["phase"] == "voting"
    assert (await call(client, boris, "PUT", f"/api/ideas/{anna_idea}/vote")).status_code == 204

    assert (await move_to((voting_deadline + timedelta(seconds=1)).isoformat())).status_code == 204
    response = await call(client, boris, "GET", f"/api/contests/{contest_id}")
    assert response.json()["phase"] == "finished"
    # Тик выполнился в запросе: итоговые письма уже поставлены и отправлены.
    kinds = sorted(row.kind for row in await outbox_rows(database))
    assert "winner_announcement" in kinds
    assert set(mail.recipients()) == {"anna@example.com", "boris@example.com"}


async def test_clock_refuses_to_go_back(app: FastAPI, client: httpx.AsyncClient) -> None:
    earlier = (app.state.clock.now() - HOUR).isoformat()
    response = await client.post("/api/__test__/clock", json={"now": earlier})
    assert response.status_code == 400
    assert response.json()["code"] == "clock_moves_back"


async def test_clock_needs_a_zone_in_the_timestamp(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/__test__/clock", json={"now": "2030-01-01T00:00:00"})
    assert response.status_code == 422
