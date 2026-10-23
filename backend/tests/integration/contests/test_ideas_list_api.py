"""Список идей по фазам: что видит каждый и какие ключи отдаёт ответ (П3, П4, Ф3; IC-012)."""

from collections.abc import Awaitable, Callable
from datetime import datetime

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

OWN_KEYS = {"id", "title", "description", "version", "submitted_at", "updated_at"}
VOTING_KEYS = {"id", "title", "description", "is_mine", "my_vote"}
FINISHED_KEYS = {"id", "title", "description", "is_mine", "author_name", "submitted_at"}


async def list_ideas(
    client: httpx.AsyncClient, person: Person | None, contest_id: int
) -> httpx.Response:
    return await call(client, person, "GET", f"/api/contests/{contest_id}/ideas")


async def test_submission_shows_only_own_ideas(
    client: httpx.AsyncClient,
    anna: Person,
    boris: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    mine = (await new_idea(anna, contest_id, title="Идея Анны")).json()
    await new_idea(boris, contest_id, title="Идея Бориса")

    own = await list_ideas(client, anna, contest_id)
    assert own.status_code == 200
    body = own.json()
    assert body["phase"] == "submission"
    assert [item["id"] for item in body["items"]] == [mine["id"]]
    assert set(body["items"][0]) == OWN_KEYS
    assert "Boris" not in own.text  # П3
    assert "Идея Бориса" not in own.text

    # Организатор до закрытия приёма не видит чужих идей: он не автор ни одной.
    assert (await list_ideas(client, organizer, contest_id)).json()["items"] == []


async def test_submission_lists_own_ideas_in_submission_order(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
) -> None:
    contest_id = await new_contest()
    ids = []
    for number in range(3):
        clock.advance(MICROSECOND * 1000)
        ids.append((await new_idea(anna, contest_id, title=f"Идея {number}")).json()["id"])
    items = (await list_ideas(client, anna, contest_id)).json()["items"]
    assert [item["id"] for item in items] == ids


async def test_voting_shows_everything_without_authors(
    client: httpx.AsyncClient,
    anna: Person,
    boris: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
) -> None:
    contest_id = await new_contest()
    anna_idea = (await new_idea(anna, contest_id, title="Идея Анны")).json()
    boris_idea = (await new_idea(boris, contest_id, title="Идея Бориса")).json()
    clock.set(SUBMISSION_DEADLINE)

    for viewer in (anna, boris, organizer):
        response = await list_ideas(client, viewer, contest_id)
        assert response.status_code == 200
        body = response.json()
        assert body["phase"] == "voting"
        assert {item["id"] for item in body["items"]} == {anna_idea["id"], boris_idea["id"]}
        for item in body["items"]:
            assert set(item) == VOTING_KEYS  # ни автора, ни времени подачи (П4)
        # Порядок — по случайному UUID: он не выдаёт порядок подачи.
        assert [item["id"] for item in body["items"]] == sorted(
            item["id"] for item in body["items"]
        )
        # Названия идей содержат имена, поэтому ищем имена авторов из учётных записей.
        assert "Anna" not in response.text
        assert "Boris" not in response.text
        assert "author" not in response.text
        assert "submitted_at" not in response.text

    mine = {
        item["id"]: item["is_mine"]
        for item in (await list_ideas(client, anna, contest_id)).json()["items"]
    }
    assert mine == {anna_idea["id"]: True, boris_idea["id"]: False}
    organizer_view = (await list_ideas(client, organizer, contest_id)).json()["items"]
    assert [item["is_mine"] for item in organizer_view] == [False, False]


async def test_finished_reveals_authors_to_everyone(
    client: httpx.AsyncClient,
    anna: Person,
    boris: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
) -> None:
    contest_id = await new_contest()
    first = (await new_idea(anna, contest_id, title="Первая")).json()
    clock.advance(MICROSECOND)
    second = (await new_idea(boris, contest_id, title="Вторая")).json()
    clock.set(VOTING_DEADLINE)

    for viewer in (anna, boris, organizer):
        body = (await list_ideas(client, viewer, contest_id)).json()
        assert body["phase"] == "finished"
        assert [item["id"] for item in body["items"]] == [first["id"], second["id"]]
        assert [item["author_name"] for item in body["items"]] == ["Anna", "Boris"]
        for item in body["items"]:
            assert set(item) == FINISHED_KEYS


@pytest.mark.parametrize(
    ("moment", "phase"),
    [
        (SUBMISSION_DEADLINE - MICROSECOND, "submission"),
        (SUBMISSION_DEADLINE, "voting"),
        (VOTING_DEADLINE - MICROSECOND, "voting"),
        (VOTING_DEADLINE, "finished"),
    ],
)
async def test_list_flips_at_exact_deadlines(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
    moment: datetime,
    phase: str,
) -> None:
    contest_id = await new_contest()
    await new_idea(anna, contest_id)
    clock.set(moment)
    assert (await list_ideas(client, anna, contest_id)).json()["phase"] == phase


async def test_unknown_contest_and_anonymous(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    missing = await list_ideas(client, anna, 999_999)
    assert missing.status_code == 404
    assert missing.json()["code"] == "contest_not_found"
    assert (await list_ideas(client, None, contest_id)).status_code == 401
