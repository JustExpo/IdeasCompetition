"""Финализация и итоговые письма (Ф4, П1, П10; IC-020, IC-022)."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId
from app.contest.dao import ContestRow
from app.core.db import Database
from app.notification.model import EmailKind
from app.result.service import finalize_contest, finalize_due_contests
from app.vote.dao import VoteRow
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    MICROSECOND,
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
    run_to_voting,
    vote_for,
)

pytestmark = pytest.mark.commits

type Finalize = Callable[[], Awaitable[list[ContestId]]]


@pytest.fixture
def finalize(database: Database, clock: FrozenClock) -> Finalize:
    async def run() -> list[ContestId]:
        return await finalize_due_contests(database, clock, public_base_url=PUBLIC_URL)

    return run


async def read_contest(database: Database, contest_id: int) -> ContestRow:
    async def read(session: AsyncSession) -> ContestRow:
        return (
            await session.execute(
                select(ContestRow)
                .where(ContestRow.id == contest_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()

    return await database.run_in_transaction(read)


@pytest.fixture
async def clara(make_person: PersonFactory) -> Person:
    return await make_person("Clara")


async def test_finalization_fixes_winner_and_queues_one_email_per_participant(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
    clara: Person,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    # Борис — победитель и сам голосует: письмо ему всё равно одно.
    await vote_for(client, anna, contest.ideas["Идея Бориса"])
    await vote_for(client, clara, contest.ideas["Идея Бориса"])
    await vote_for(client, boris, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)

    assert await finalize() == [ContestId(contest.id)]

    row = await read_contest(database, contest.id)
    assert row.finalized_at == VOTING_DEADLINE
    assert str(row.winner_idea_id) == contest.ideas["Идея Бориса"]
    emails = {email.to_email: email for email in await outbox_rows(database)}
    assert set(emails) == {"boris@example.com", "anna@example.com", "clara@example.com"}
    assert "Вы победили" in emails["boris@example.com"].subject
    assert emails["boris@example.com"].kind == EmailKind.WINNER_ANNOUNCEMENT.value
    assert "Ваша идея не прошла" in emails["anna@example.com"].subject
    assert "Идея Бориса" in (emails["anna@example.com"].body or "")
    assert "Итоги конкурса" in emails["clara@example.com"].subject
    assert f"{PUBLIC_URL}/contests/{contest.id}" in (emails["clara@example.com"].body or "")


async def test_second_tick_changes_nothing(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, boris, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)
    assert await finalize()
    before = await outbox_rows(database)

    clock.advance(MICROSECOND * 10)
    assert await finalize() == []

    after = await outbox_rows(database)
    assert [email.id for email in after] == [email.id for email in before]
    assert (await read_contest(database, contest.id)).finalized_at == VOTING_DEADLINE


async def test_parallel_ticks_finalize_once(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, boris, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)

    results = await asyncio.gather(
        *(
            finalize_contest(database, clock, ContestId(contest.id), public_base_url=PUBLIC_URL)
            for _ in range(4)
        )
    )

    assert results.count(True) == 1
    assert len(await outbox_rows(database)) == 2


async def test_not_finalized_before_voting_deadline(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
) -> None:
    contest = await run_to_voting(client, clock, new_contest, new_idea, [(anna, "Идея Анны")])
    clock.set(VOTING_DEADLINE - MICROSECOND)

    assert await finalize() == []
    assert (await read_contest(database, contest.id)).finalized_at is None

    clock.set(VOTING_DEADLINE)
    assert await finalize() == [ContestId(contest.id)]


async def test_contest_without_ideas_has_no_winner_and_no_emails(
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
) -> None:
    contest_id = await new_contest()
    clock.set(VOTING_DEADLINE)

    assert await finalize() == [ContestId(contest_id)]

    row = await read_contest(database, contest_id)
    assert row.finalized_at is not None
    assert row.winner_idea_id is None
    assert await outbox_rows(database) == []


async def test_author_of_several_ideas_gets_single_email(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
) -> None:
    contest = await run_to_voting(
        client,
        clock,
        new_contest,
        new_idea,
        [(anna, "Первая Анны"), (anna, "Вторая Анны"), (boris, "Идея Бориса")],
    )
    await vote_for(client, boris, contest.ideas["Вторая Анны"])
    await vote_for(client, anna, contest.ideas["Идея Бориса"])
    clock.set(VOTING_DEADLINE)

    await finalize()

    emails = {email.to_email: email for email in await outbox_rows(database)}
    assert len(emails) == 2
    assert "Вы победили" in emails["anna@example.com"].subject
    assert "Ваша идея не прошла" in emails["boris@example.com"].subject


async def test_tie_is_resolved_by_earlier_submission_and_mentioned_in_email(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
    clara: Person,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, clara, contest.ideas["Идея Бориса"])
    await vote_for(client, boris, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)

    await finalize()

    assert (
        str((await read_contest(database, contest.id)).winner_idea_id) == contest.ideas["Идея Анны"]
    )
    emails = {email.to_email: email for email in await outbox_rows(database)}
    assert "поданная раньше" in (emails["boris@example.com"].body or "")


async def test_email_winner_matches_api_results(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    finalize: Finalize,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
    clara: Person,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, clara, contest.ideas["Идея Бориса"])
    await vote_for(client, anna, contest.ideas["Идея Бориса"])
    clock.set(VOTING_DEADLINE)
    await finalize()

    response = await call(client, anna, "GET", f"/api/contests/{contest.id}/results")

    assert response.status_code == 200, response.text
    api_winner = response.json()["results"][0]
    assert str(api_winner["idea_id"]) == contest.ideas["Идея Бориса"]
    row = await read_contest(database, contest.id)
    assert str(row.winner_idea_id) == str(api_winner["idea_id"])


async def test_vote_accepted_before_deadline_is_counted_in_final_result(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
    clara: Person,
) -> None:
    """Запись держит `FOR SHARE`: финализация (`FOR UPDATE`) ждёт её и видит её голос (Р6)."""
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, clara, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)
    holding = asyncio.Event()
    release = asyncio.Event()

    async def late_vote(session: AsyncSession) -> None:
        await session.execute(
            text("SELECT 1 FROM contests WHERE id = :id FOR SHARE"), {"id": contest.id}
        )
        session.add(
            VoteRow(
                idea_id=UUID(contest.ideas["Идея Бориса"]),
                voter_id=int(anna.id),
                created_at=VOTING_DEADLINE - MICROSECOND,
            )
        )
        await session.flush()
        holding.set()
        await release.wait()

    async def waiting_finalizers() -> int:
        async def count(session: AsyncSession) -> int:
            return int(
                await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE wait_event_type = 'Lock' AND query ILIKE '%FOR UPDATE%'"
                    )
                )
                or 0
            )

        return await database.run_in_transaction(count)

    writer = asyncio.create_task(database.run_in_transaction(late_vote))
    await holding.wait()
    finalizer = asyncio.create_task(
        finalize_contest(database, clock, ContestId(contest.id), public_base_url=PUBLIC_URL)
    )
    for _ in range(5000):  # ждём, пока финализация встанет на блокировке конкурса
        if await waiting_finalizers():
            break
    release.set()
    await writer

    assert await finalizer is True
    row = await read_contest(database, contest.id)
    # По голосу за каждую идею: ничью решает время подачи, победила идея Анны.
    assert str(row.winner_idea_id) == contest.ideas["Идея Анны"]
    results = await call(client, boris, "GET", f"/api/contests/{contest.id}/results")
    votes = {item["idea_id"]: item["votes"] for item in results.json()["results"]}
    assert votes[contest.ideas["Идея Бориса"]] == 1
