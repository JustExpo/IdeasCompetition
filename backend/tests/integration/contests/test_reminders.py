"""Напоминания за сутки до закрытия раунда (П9; IC-023)."""

import asyncio
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.notification.model import EmailKind
from app.reminder.service import enqueue_due_reminders
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    MICROSECOND,
    NOW,
    SUBMISSION_DEADLINE,
    VOTING_DEADLINE,
    Person,
    PersonFactory,
    call,
)
from tests.integration.contests.mailbox import (
    PUBLIC_URL,
    NewContest,
    NewIdea,
    outbox_rows,
    vote_for,
)

pytestmark = pytest.mark.commits

DAY = timedelta(days=1)


@pytest.fixture
async def clara(make_person: PersonFactory) -> Person:
    return await make_person("Clara")


async def remind(database: Database, clock: FrozenClock) -> int:
    return await enqueue_due_reminders(
        database, clock, public_base_url=PUBLIC_URL, display_tz="Europe/Moscow"
    )


async def recipients(database: Database, kind: EmailKind) -> set[str]:
    return {row.to_email for row in await outbox_rows(database) if row.kind == kind.value}


async def test_submission_reminder_goes_to_employees_without_ideas(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
    clara: Person,
) -> None:
    contest_id = await new_contest()
    assert (await new_idea(anna, contest_id)).status_code == 201

    assert await remind(database, clock) == 2

    assert await recipients(database, EmailKind.SUBMISSION_REMINDER) == {
        "boris@example.com",
        "clara@example.com",  # организатор Olga не получает: он не участвует в конкурсе
    }
    mail = next(row for row in await outbox_rows(database) if row.to_email == "boris@example.com")
    assert mail.not_after == SUBMISSION_DEADLINE
    assert f"{PUBLIC_URL}/contests/{contest_id}" in (mail.body or "")
    assert "Как улучшить офис" in mail.subject


async def test_repeated_and_parallel_ticks_send_one_reminder_per_person(
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    anna: Person,
    boris: Person,
) -> None:
    await new_contest()

    created = await asyncio.gather(*(remind(database, clock) for _ in range(4)))
    again = await remind(database, clock)

    assert sum(created) == 2
    assert again == 0
    assert len(await outbox_rows(database)) == 2


async def test_window_boundaries_for_submission_round(
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    anna: Person,
) -> None:
    deadline = NOW + 3 * DAY
    await new_contest(submission_deadline=deadline, voting_deadline=deadline + DAY)

    clock.set(deadline - DAY - MICROSECOND)
    assert await remind(database, clock) == 0

    clock.set(deadline - DAY)  # d − 24h: окно открылось
    assert await remind(database, clock) == 1


async def test_no_submission_reminder_at_or_after_deadline(
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    anna: Person,
) -> None:
    await new_contest()

    clock.set(SUBMISSION_DEADLINE - MICROSECOND)
    assert await remind(database, clock) == 1  # последний микросекундный миг раунда ещё открыт
    # С дедлайна приём закрыт, но открылось голосование: идёт только напоминание о нём.
    clock.set(SUBMISSION_DEADLINE)
    assert await remind(database, clock) == 1
    assert await recipients(database, EmailKind.VOTING_REMINDER) == {"anna@example.com"}
    assert await recipients(database, EmailKind.SUBMISSION_REMINDER) == {"anna@example.com"}


async def test_voting_reminder_goes_to_those_without_votes(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
    clara: Person,
) -> None:
    contest_id = await new_contest()
    first = (await new_idea(anna, contest_id, title="Идея Анны")).json()["id"]
    second = (await new_idea(boris, contest_id, title="Идея Бориса")).json()["id"]
    clock.set(SUBMISSION_DEADLINE)
    await vote_for(client, clara, first)
    await vote_for(client, boris, first)
    await vote_for(client, anna, second)
    # Клара отозвала единственный голос: по текущему состоянию она снова «не участвовала».
    assert (await call(client, clara, "DELETE", f"/api/ideas/{first}/vote")).status_code == 204

    await remind(database, clock)

    assert await recipients(database, EmailKind.VOTING_REMINDER) == {"clara@example.com"}


async def test_no_voting_reminder_while_voting_has_not_started(
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    anna: Person,
) -> None:
    # Оба дедлайна ближе суток, но идёт приём идей: звать голосовать рано.
    await new_contest(
        submission_deadline=NOW + timedelta(hours=12), voting_deadline=NOW + timedelta(hours=20)
    )

    await remind(database, clock)

    assert await recipients(database, EmailKind.VOTING_REMINDER) == set()
    assert await recipients(database, EmailKind.SUBMISSION_REMINDER) == {"anna@example.com"}


async def test_voting_reminder_boundary_at_deadline(
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    anna: Person,
) -> None:
    await new_contest()
    clock.set(VOTING_DEADLINE - MICROSECOND)
    assert await remind(database, clock) == 1
    clock.set(VOTING_DEADLINE)
    assert await remind(database, clock) == 0


async def test_inactive_employee_gets_no_reminder(
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    anna: Person,
    boris: Person,
) -> None:
    await new_contest()

    async def deactivate(session: AsyncSession) -> None:
        await session.execute(
            text("UPDATE users SET is_active = false WHERE id = :id"), {"id": boris.id}
        )

    await database.run_in_transaction(deactivate)

    await remind(database, clock)

    assert await recipients(database, EmailKind.SUBMISSION_REMINDER) == {"anna@example.com"}
