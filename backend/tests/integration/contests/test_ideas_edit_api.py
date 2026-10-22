"""Правка идеи: версия, повтор, границы дедлайна, две вкладки (Ф2, П2; IC-012)."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import uuid4

import httpx
import pytest

from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    MICROSECOND,
    NOW,
    SUBMISSION_DEADLINE,
    VOTING_DEADLINE,
    Person,
    call,
)

pytestmark = pytest.mark.commits

NewContest = Callable[..., Awaitable[int]]
NewIdea = Callable[..., Awaitable[httpx.Response]]


async def edit(
    client: httpx.AsyncClient,
    person: Person | None,
    idea_id: str,
    *,
    title: str = "Новое название",
    description: str = "Новое описание",
    version: int = 1,
) -> httpx.Response:
    return await call(
        client,
        person,
        "PATCH",
        f"/api/ideas/{idea_id}",
        json={"title": title, "description": description, "version": version},
    )


async def test_author_edits_idea_and_version_grows(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    clock.advance(MICROSECOND * 5)
    response = await edit(client, anna, created["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert (body["title"], body["description"]) == ("Новое название", "Новое описание")
    assert body["version"] == 2
    # submitted_at не меняется: по нему решается ничья (П10).
    assert body["submitted_at"] == created["submitted_at"]
    assert datetime.fromisoformat(body["updated_at"]) == NOW + MICROSECOND * 5


async def test_stale_version_is_rejected(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    assert (await edit(client, anna, created["id"], title="Вкладка А")).status_code == 200
    stale = await edit(client, anna, created["id"], title="Вкладка Б", version=1)
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    fresh = await edit(client, anna, created["id"], title="Вкладка Б", version=2)
    assert fresh.status_code == 200
    assert fresh.json()["version"] == 3


async def test_repeating_an_applied_edit_returns_200_without_a_new_version(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    first = await edit(client, anna, created["id"])
    # Ответ потерялся, запрос повторён — в том числе после закрытия приёма (проверка полей
    # идёт до фазы и версии).
    clock.set(SUBMISSION_DEADLINE + MICROSECOND)
    again = await edit(client, anna, created["id"], version=1)
    assert again.status_code == 200
    assert again.json() == first.json()


@pytest.mark.parametrize(
    ("moment", "status"),
    [
        (SUBMISSION_DEADLINE - MICROSECOND, 200),
        (SUBMISSION_DEADLINE, 409),
        (VOTING_DEADLINE - MICROSECOND, 409),
        (VOTING_DEADLINE, 409),
    ],
)
async def test_edit_closes_exactly_at_the_submission_deadline(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
    moment: datetime,
    status: int,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    clock.set(moment)
    response = await edit(client, anna, created["id"])
    assert response.status_code == status
    if status == 409:
        assert response.json()["code"] == "submission_closed"


async def test_someone_elses_idea_looks_like_a_missing_one(
    client: httpx.AsyncClient,
    anna: Person,
    boris: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    foreign = await edit(client, boris, created["id"])
    missing = await edit(client, boris, str(uuid4()))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["code"] == missing.json()["code"] == "idea_not_found"
    # Для чужой идеи не различим даже порядок проверок: фаза и версия не проверяются.
    assert (await edit(client, boris, created["id"], version=99)).status_code == 404


async def test_organizer_anonymous_and_malformed_id(
    client: httpx.AsyncClient,
    anna: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    forbidden = await edit(client, organizer, created["id"])
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "organizer_cannot_participate"
    assert (await edit(client, None, created["id"])).status_code == 401
    assert (await edit(client, anna, "not-a-uuid")).status_code == 422


@pytest.mark.parametrize(
    ("title", "description"),
    [("", "d"), ("   ", "d"), ("t", "   "), ("н" * 201, "d"), ("t", "о" * 10_001), ("a\x00b", "d")],
)
async def test_invalid_text_is_rejected_on_edit(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    title: str,
    description: str,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    response = await edit(client, anna, created["id"], title=title, description=description)
    assert response.status_code == 422
    assert response.json()["code"] in {"invalid_idea", "validation_error"}


async def test_bad_version_and_unknown_fields_are_rejected(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    for body in (
        {"title": "t", "description": "d", "version": 0},
        {"title": "t", "description": "d"},
        {"title": "t", "description": "d", "version": 1, "author_id": 5},
    ):
        response = await call(client, anna, "PATCH", f"/api/ideas/{created['id']}", json=body)
        assert response.status_code == 422


async def test_two_tabs_editing_in_parallel_leave_exactly_one_winner(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    results = await asyncio.gather(
        edit(client, anna, created["id"], title="Вкладка А"),
        edit(client, anna, created["id"], title="Вкладка Б"),
    )
    assert sorted(response.status_code for response in results) == [200, 409]
    loser = next(response for response in results if response.status_code == 409)
    assert loser.json()["code"] == "stale_version"
    winner = next(response for response in results if response.status_code == 200)
    listed = (await call(client, anna, "GET", f"/api/contests/{contest_id}/ideas")).json()
    assert listed["items"][0]["title"] == winner.json()["title"]
    assert listed["items"][0]["version"] == 2
