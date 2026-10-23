"""Итоги и экран организатора: доступ по фазам, ранжирование, числа (П8, П10, Ф5; IC-014)."""

from collections.abc import Awaitable, Callable

import httpx
import pytest

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
PersonFactory = Callable[..., Awaitable[Person]]


def results_path(contest_id: int) -> str:
    return f"/api/contests/{contest_id}/results"


def dashboard_path(contest_id: int) -> str:
    return f"/api/organizer/contests/{contest_id}/dashboard"


async def vote(client: httpx.AsyncClient, person: Person, idea_id: str) -> None:
    assert (await call(client, person, "PUT", f"/api/ideas/{idea_id}/vote")).status_code == 204


async def test_full_contest_cycle(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    organizer: Person,
    anna: Person,
    boris: Person,
    make_person: PersonFactory,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    clara = await make_person("Clara")
    contest_id = await new_contest()
    first = (await new_idea(anna, contest_id, title="Идея Анны")).json()["id"]
    second = (await new_idea(boris, contest_id, title="Идея Бориса")).json()["id"]

    # Приём: сотрудник итоги не видит, организатор видит пустые голоса без авторов.
    assert (await call(client, anna, "GET", results_path(contest_id))).status_code == 403
    board = (await call(client, organizer, "GET", dashboard_path(contest_id))).json()
    assert board["ideas_count"] == 2
    assert board["voters_count"] == 0

    clock.set(SUBMISSION_DEADLINE)
    await vote(client, clara, second)
    await vote(client, anna, second)
    await vote(client, boris, first)

    board = (await call(client, organizer, "GET", dashboard_path(contest_id))).json()
    assert board["voters_count"] == 3
    assert [(r["idea_id"], r["votes"]) for r in board["results"]] == [(second, 2), (first, 1)]
    assert "author_name" not in str(board)  # Ф5: организатор до финала без авторов
    mid = await call(client, organizer, "GET", results_path(contest_id))
    assert mid.json()["status"] == "in_progress"
    assert "Anna" not in mid.text
    assert (await call(client, anna, "GET", results_path(contest_id))).status_code == 403

    clock.set(VOTING_DEADLINE - MICROSECOND)
    assert (await call(client, clara, "GET", results_path(contest_id))).status_code == 403
    clock.set(VOTING_DEADLINE)
    final = (await call(client, clara, "GET", results_path(contest_id))).json()
    assert final["status"] == "final"
    assert [(r["place"], r["author_name"], r["votes"]) for r in final["results"]] == [
        (1, "Boris", 2),
        (2, "Anna", 1),
    ]
    assert (await call(client, None, "GET", results_path(contest_id))).status_code == 401
    assert (await call(client, clara, "GET", dashboard_path(contest_id))).status_code == 403


async def test_tie_goes_to_earlier_submission(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    organizer: Person,
    anna: Person,
    boris: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    first = (await new_idea(anna, contest_id)).json()["id"]
    clock.advance(MICROSECOND * 10)
    second = (await new_idea(boris, contest_id)).json()["id"]
    clock.set(SUBMISSION_DEADLINE)
    await vote(client, boris, first)
    await vote(client, anna, second)
    results = (await call(client, organizer, "GET", results_path(contest_id))).json()["results"]
    assert [r["idea_id"] for r in results] == [first, second]  # П10


async def test_no_ideas_and_zero_votes(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    organizer: Person,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    empty = await new_contest()
    other = await new_contest()
    mine = (await new_idea(anna, other)).json()["id"]
    clock.set(VOTING_DEADLINE)
    assert (await call(client, anna, "GET", results_path(empty))).json()["results"] == []
    board = (await call(client, organizer, "GET", dashboard_path(other))).json()
    assert board["results"][0]["idea_id"] == mine
    assert board["results"][0]["votes"] == 0


async def test_counts_follow_withdrawn_votes_and_deleted_ideas(
    client: httpx.AsyncClient,
    clock: FrozenClock,
    organizer: Person,
    anna: Person,
    boris: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    first = (await new_idea(anna, contest_id)).json()["id"]
    second = (await new_idea(boris, contest_id)).json()["id"]
    clock.set(SUBMISSION_DEADLINE)
    await vote(client, boris, first)
    await vote(client, anna, second)
    board = (await call(client, organizer, "GET", dashboard_path(contest_id))).json()
    assert (board["ideas_count"], board["voters_count"]) == (2, 2)

    await call(client, boris, "DELETE", f"/api/ideas/{first}/vote")
    board = (await call(client, organizer, "GET", dashboard_path(contest_id))).json()
    assert (board["ideas_count"], board["voters_count"]) == (2, 1)

    await call(client, boris, "DELETE", f"/api/ideas/{second}")
    board = (await call(client, organizer, "GET", dashboard_path(contest_id))).json()
    assert (board["ideas_count"], board["voters_count"]) == (1, 0)


async def test_unknown_contest_is_404_before_role(
    client: httpx.AsyncClient, anna: Person, organizer: Person
) -> None:
    assert (await call(client, anna, "GET", results_path(9999))).status_code == 404
    assert (await call(client, organizer, "GET", dashboard_path(9999))).status_code == 404
