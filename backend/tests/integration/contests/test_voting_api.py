"""Голосование: отдать и отозвать голос, порядок проверок, гонки (П2, П4–П6, П11; IC-013)."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.core.db import Database
from app.vote.dao import VoteRow
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    MICROSECOND,
    SUBMISSION_DEADLINE,
    VOTING_DEADLINE,
    Person,
    call,
)

pytestmark = pytest.mark.commits

NewContest = Callable[..., Awaitable[int]]
NewIdea = Callable[..., Awaitable[httpx.Response]]


async def put_vote(
    client: httpx.AsyncClient, person: Person | None, idea_id: str
) -> httpx.Response:
    return await call(client, person, "PUT", f"/api/ideas/{idea_id}/vote")


async def delete_vote(
    client: httpx.AsyncClient, person: Person | None, idea_id: str
) -> httpx.Response:
    return await call(client, person, "DELETE", f"/api/ideas/{idea_id}/vote")


async def count_votes(database: Database) -> int:
    async def work(session):  # type: ignore[no-untyped-def]
        return await session.scalar(select(func.count()).select_from(VoteRow))

    return int(await database.run_in_transaction(work))


@pytest.fixture
async def voting_setup(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    anna: Person,
    boris: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> tuple[int, str, str]:
    """Конкурс в фазе голосования: у Анны и Бориса по идее. Возвращает id идей (Анны, Бориса)."""
    contest_id = await new_contest()
    anna_idea = (await new_idea(anna, contest_id, title="Идея Анны")).json()["id"]
    boris_idea = (await new_idea(boris, contest_id, title="Идея Бориса")).json()["id"]
    clock.set(SUBMISSION_DEADLINE)
    return contest_id, anna_idea, boris_idea


async def test_vote_is_idempotent_and_shown_as_my_vote(
    client: httpx.AsyncClient,
    database: Database,
    anna: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    contest_id, _, boris_idea = voting_setup
    assert (await put_vote(client, anna, boris_idea)).status_code == 204
    assert (await put_vote(client, anna, boris_idea)).status_code == 204  # повтор — не ошибка
    assert await count_votes(database) == 1

    items = (await call(client, anna, "GET", f"/api/contests/{contest_id}/ideas")).json()["items"]
    marks = {item["id"]: item["my_vote"] for item in items}
    assert marks[boris_idea] is True
    assert sum(marks.values()) == 1


async def test_parallel_votes_create_single_row(
    client: httpx.AsyncClient,
    database: Database,
    anna: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    responses = await asyncio.gather(*(put_vote(client, anna, boris_idea) for _ in range(20)))
    assert {r.status_code for r in responses} == {204}  # П5
    assert await count_votes(database) == 1


async def test_withdraw_is_idempotent(
    client: httpx.AsyncClient,
    database: Database,
    anna: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    await put_vote(client, anna, boris_idea)
    assert (await delete_vote(client, anna, boris_idea)).status_code == 204
    assert (await delete_vote(client, anna, boris_idea)).status_code == 204
    assert await count_votes(database) == 0


async def test_own_idea_vote_is_forbidden(
    client: httpx.AsyncClient, anna: Person, voting_setup: tuple[int, str, str]
) -> None:
    _, anna_idea, _ = voting_setup
    response = await put_vote(client, anna, anna_idea)
    assert response.status_code == 403
    assert response.json()["code"] == "own_idea_vote"


async def test_checks_order_401_404_403_409(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    anna: Person,
    organizer: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    assert (await put_vote(client, None, boris_idea)).status_code == 401
    assert (await put_vote(client, anna, str(uuid4()))).status_code == 404
    forbidden = await put_vote(client, organizer, boris_idea)
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "organizer_cannot_participate"
    clock.set(VOTING_DEADLINE)
    closed = await put_vote(client, anna, boris_idea)
    assert closed.status_code == 409
    assert closed.json()["code"] == "voting_closed"


async def test_vote_boundaries(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    anna: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    # d−1µs приём ещё открыт: чужая идея невидима (404); d — голосование началось (fixture);
    # v−1µs — голосовать ещё можно; v — закрыто.
    clock.set(SUBMISSION_DEADLINE - MICROSECOND)
    assert (await put_vote(client, anna, boris_idea)).status_code == 404
    clock.set(SUBMISSION_DEADLINE)
    assert (await put_vote(client, anna, boris_idea)).status_code == 204
    assert (await delete_vote(client, anna, boris_idea)).status_code == 204
    clock.set(VOTING_DEADLINE - MICROSECOND)
    assert (await put_vote(client, anna, boris_idea)).status_code == 204
    clock.set(VOTING_DEADLINE)
    assert (await delete_vote(client, anna, boris_idea)).status_code == 409  # отзыв тоже закрыт
    assert await count_votes(database) == 1


async def test_vote_in_submission_hides_foreign_idea(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    anna: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    clock.set(SUBMISSION_DEADLINE - MICROSECOND)
    # В приёме чужая идея невидима: 404, а не 403/409 (П3).
    hidden = await delete_vote(client, anna, boris_idea)
    assert hidden.status_code == 404


async def test_author_without_ideas_can_vote(
    client: httpx.AsyncClient,
    make_person: Callable[..., Awaitable[Person]],
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    clara = await make_person("Clara")
    assert (await put_vote(client, clara, boris_idea)).status_code == 204


async def test_delete_idea_removes_votes_and_blocks_after_finish(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    anna: Person,
    boris: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    contest_id, _, boris_idea = voting_setup
    await put_vote(client, anna, boris_idea)
    assert (await call(client, anna, "DELETE", f"/api/ideas/{boris_idea}")).status_code == 404
    assert (await call(client, boris, "DELETE", f"/api/ideas/{boris_idea}")).status_code == 204
    assert await count_votes(database) == 0  # П11: голоса ушли каскадом
    items = (await call(client, anna, "GET", f"/api/contests/{contest_id}/ideas")).json()["items"]
    assert boris_idea not in {item["id"] for item in items}
    assert (await put_vote(client, anna, boris_idea)).status_code == 404

    clock.set(VOTING_DEADLINE)
    locked = await call(client, anna, "DELETE", f"/api/ideas/{voting_setup[1]}")
    assert locked.status_code == 409
    assert locked.json()["code"] == "idea_locked"


async def test_delete_races_with_vote_without_orphans(
    client: httpx.AsyncClient,
    database: Database,
    anna: Person,
    boris: Person,
    voting_setup: tuple[int, str, str],
) -> None:
    _, _, boris_idea = voting_setup
    deleted, voted = await asyncio.gather(
        call(client, boris, "DELETE", f"/api/ideas/{boris_idea}"),
        put_vote(client, anna, boris_idea),
    )
    assert deleted.status_code == 204
    assert voted.status_code in {204, 404}
    assert await count_votes(database) == 0  # голос либо ушёл каскадом, либо не принят
