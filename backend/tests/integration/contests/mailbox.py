"""Помощники тестов писем: чтение outbox и сценарий «конкурс дошёл до голосования»."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.notification.dao import OutboxEmailRow
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    SUBMISSION_DEADLINE,
    Person,
    call,
)

PUBLIC_URL = "http://127.0.0.1:8000"
NewContest = Callable[..., Awaitable[int]]
NewIdea = Callable[..., Awaitable[httpx.Response]]


async def outbox_rows(database: Database) -> list[OutboxEmailRow]:
    async def read(session: AsyncSession) -> list[OutboxEmailRow]:
        rows = await session.scalars(
            select(OutboxEmailRow)
            .order_by(OutboxEmailRow.id)
            .execution_options(populate_existing=True)
        )
        return list(rows)

    return await database.run_in_transaction(read)


async def vote_for(client: httpx.AsyncClient, person: Person, idea_id: str) -> None:
    response = await call(client, person, "PUT", f"/api/ideas/{idea_id}/vote")
    assert response.status_code == 204, response.text


@dataclass(frozen=True)
class Contest:
    id: int
    ideas: dict[str, str]  # название → id


async def run_to_voting(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    new_contest: NewContest,
    new_idea: NewIdea,
    submissions: list[tuple[Person, str]],
) -> Contest:
    """Создать конкурс, принять идеи `(автор, название)` и открыть голосование."""
    contest_id = await new_contest()
    ideas: dict[str, str] = {}
    for author, title in submissions:
        response = await new_idea(author, contest_id, title=title)
        assert response.status_code == 201, response.text
        ideas[title] = str(response.json()["id"])
        # Разное время подачи: иначе ничью разрешал бы случайный UUID (П10).
        clock.advance(timedelta(seconds=1))
    clock.set(SUBMISSION_DEADLINE)
    return Contest(contest_id, ideas)
