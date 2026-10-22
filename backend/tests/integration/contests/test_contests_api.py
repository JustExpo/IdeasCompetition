"""Создание и просмотр конкурсов по HTTP на реальном PostgreSQL (Ф1, П1, П10; IC-010)."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, timezone

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
    iso,
)

pytestmark = pytest.mark.commits

NewContest = Callable[..., Awaitable[int]]


def contest_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "topic": "Как улучшить офис",
        "description": "Описание",
        "submission_deadline": iso(SUBMISSION_DEADLINE),
        "voting_deadline": iso(VOTING_DEADLINE),
    }
    body.update(overrides)
    return body


async def test_organizer_creates_contest_and_sees_card(
    client: httpx.AsyncClient, organizer: Person
) -> None:
    response = await call(client, organizer, "POST", "/api/contests", json=contest_body())
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id",
        "topic",
        "description",
        "submission_deadline",
        "voting_deadline",
        "created_at",
        "phase",
        "server_time",
        "allowed_actions",
        "tie_break_rule",
    }
    assert body["topic"] == "Как улучшить офис"
    assert body["phase"] == "submission"
    assert body["allowed_actions"] == ["view_results"]  # организатор не подаёт и не голосует
    assert "раньше" in body["tie_break_rule"]  # правило ничьей видно с фазы подачи (П10)
    assert datetime.fromisoformat(body["server_time"]) == NOW
    assert datetime.fromisoformat(body["submission_deadline"]) == SUBMISSION_DEADLINE
    assert "created_by" not in body  # кто создал конкурс, участникам знать незачем


async def test_employee_and_anonymous_cannot_create_contest(
    client: httpx.AsyncClient, anna: Person
) -> None:
    forbidden = await call(client, anna, "POST", "/api/contests", json=contest_body())
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "forbidden"
    anonymous = await call(client, None, "POST", "/api/contests", json=contest_body())
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == "not_authenticated"


async def test_deadline_without_utc_offset_is_rejected(
    client: httpx.AsyncClient, organizer: Person
) -> None:
    naive = SUBMISSION_DEADLINE.replace(tzinfo=None).isoformat()
    response = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(submission_deadline=naive)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_regression_deadline_offset_is_normalized_to_utc(
    client: httpx.AsyncClient, organizer: Person
) -> None:
    moscow = timezone(timedelta(hours=3))
    response = await call(
        client,
        organizer,
        "POST",
        "/api/contests",
        json=contest_body(
            submission_deadline=SUBMISSION_DEADLINE.astimezone(moscow).isoformat(),
        ),
    )
    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["submission_deadline"])
    assert stored == SUBMISSION_DEADLINE
    assert stored.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    ("submission", "voting"),
    [
        (SUBMISSION_DEADLINE, SUBMISSION_DEADLINE),  # равные
        (VOTING_DEADLINE, SUBMISSION_DEADLINE),  # перепутанные
        (SUBMISSION_DEADLINE, SUBMISSION_DEADLINE + MICROSECOND - MICROSECOND),
    ],
)
async def test_voting_must_close_strictly_after_submission(
    client: httpx.AsyncClient, organizer: Person, submission: datetime, voting: datetime
) -> None:
    response = await call(
        client,
        organizer,
        "POST",
        "/api/contests",
        json=contest_body(submission_deadline=iso(submission), voting_deadline=iso(voting)),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "deadlines_order"


async def test_deadlines_one_microsecond_apart_are_allowed(
    client: httpx.AsyncClient, organizer: Person
) -> None:
    response = await call(
        client,
        organizer,
        "POST",
        "/api/contests",
        json=contest_body(voting_deadline=iso(SUBMISSION_DEADLINE + MICROSECOND)),
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    ("offset", "status"),
    [
        (-MICROSECOND, 422),  # уже в прошлом
        (timedelta(0), 422),  # ровно сейчас: приём на этот момент уже закрыт
        (MICROSECOND, 201),
    ],
)
async def test_submission_deadline_must_be_in_the_future(
    client: httpx.AsyncClient, organizer: Person, offset: timedelta, status: int
) -> None:
    response = await call(
        client,
        organizer,
        "POST",
        "/api/contests",
        json=contest_body(
            submission_deadline=iso(NOW + offset), voting_deadline=iso(NOW + timedelta(days=1))
        ),
    )
    assert response.status_code == status
    if status == 422:
        assert response.json()["code"] == "deadline_in_past"


@pytest.mark.parametrize(
    "topic",
    ["", "   ", "тема\x00с NUL", "тема‮с разворотом", "тема\nс переводом", "т" * 201],
)
async def test_bad_topic_is_rejected(
    client: httpx.AsyncClient, organizer: Person, topic: str
) -> None:
    response = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(topic=topic)
    )
    assert response.status_code == 422
    assert response.json()["code"] in {"invalid_contest", "validation_error"}


async def test_topic_of_maximum_length_and_unicode_normalization(
    client: httpx.AsyncClient, organizer: Person
) -> None:
    longest = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(topic="т" * 200)
    )
    assert longest.status_code == 201
    decomposed = "Ёлка"  # «Ё» разложенная: после NFC сравнивается как обычная
    normalized = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(topic=f"  {decomposed}  ")
    )
    assert normalized.json()["topic"] == "Ёлка"


async def test_description_may_be_empty_but_not_too_long(
    client: httpx.AsyncClient, organizer: Person
) -> None:
    empty = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(description="")
    )
    assert empty.status_code == 201
    too_long = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(description="о" * 10_001)
    )
    assert too_long.status_code == 422
    assert too_long.json()["code"] == "invalid_contest"


async def test_unknown_field_is_rejected(client: httpx.AsyncClient, organizer: Person) -> None:
    response = await call(
        client, organizer, "POST", "/api/contests", json=contest_body(winner_idea_id=1)
    )
    assert response.status_code == 422


async def test_list_is_sorted_and_paginated(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest
) -> None:
    day = timedelta(days=1)
    early = await new_contest(topic="Первый", voting_deadline=VOTING_DEADLINE)
    late = await new_contest(topic="Второй", voting_deadline=VOTING_DEADLINE + 5 * day)
    same_as_early = await new_contest(topic="Третий", voting_deadline=VOTING_DEADLINE)

    response = await call(client, anna, "GET", "/api/contests")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    # voting_deadline по убыванию, при равенстве — id по убыванию.
    assert [item["id"] for item in body["items"]] == [late, same_as_early, early]
    assert set(body["items"][0]) == {
        "id",
        "topic",
        "description",
        "submission_deadline",
        "voting_deadline",
        "created_at",
        "phase",
    }

    page = await call(client, anna, "GET", "/api/contests", params={"limit": 1, "offset": 1})
    assert [item["id"] for item in page.json()["items"]] == [same_as_early]
    assert page.json()["total"] == 3
    beyond = await call(client, anna, "GET", "/api/contests", params={"offset": 10})
    assert beyond.json()["items"] == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}])
async def test_list_rejects_bad_paging(
    client: httpx.AsyncClient, anna: Person, params: dict[str, object]
) -> None:
    response = await call(client, anna, "GET", "/api/contests", params=params)
    assert response.status_code == 422


async def test_list_shows_phase_at_server_time(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest, clock: FrozenClock
) -> None:
    await new_contest()
    clock.set(SUBMISSION_DEADLINE)
    response = await call(client, anna, "GET", "/api/contests")
    assert response.json()["items"][0]["phase"] == "voting"
    assert datetime.fromisoformat(response.json()["server_time"]) == SUBMISSION_DEADLINE


async def test_anonymous_cannot_read_contests(
    client: httpx.AsyncClient, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    assert (await call(client, None, "GET", "/api/contests")).status_code == 401
    assert (await call(client, None, "GET", f"/api/contests/{contest_id}")).status_code == 401


async def test_unknown_contest_is_404(client: httpx.AsyncClient, anna: Person) -> None:
    response = await call(client, anna, "GET", "/api/contests/999999")
    assert response.status_code == 404
    assert response.json()["code"] == "contest_not_found"


@pytest.mark.parametrize(
    ("moment", "phase", "actions"),
    [
        (NOW, "submission", ["submit_idea"]),
        (SUBMISSION_DEADLINE - MICROSECOND, "submission", ["submit_idea"]),
        (SUBMISSION_DEADLINE, "voting", ["vote"]),
        (VOTING_DEADLINE - MICROSECOND, "voting", ["vote"]),
        (VOTING_DEADLINE, "finished", ["view_results"]),
        (VOTING_DEADLINE + MICROSECOND, "finished", ["view_results"]),
    ],
)
async def test_card_phase_and_actions_on_deadline_boundaries(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    clock: FrozenClock,
    moment: datetime,
    phase: str,
    actions: list[str],
) -> None:
    contest_id = await new_contest()
    clock.set(moment)
    response = await call(client, anna, "GET", f"/api/contests/{contest_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == phase
    assert body["allowed_actions"] == actions
    assert datetime.fromisoformat(body["server_time"]).astimezone(UTC) == moment


async def test_organizer_sees_results_action_in_every_phase(
    client: httpx.AsyncClient, organizer: Person, new_contest: NewContest, clock: FrozenClock
) -> None:
    contest_id = await new_contest()
    for moment in (NOW, SUBMISSION_DEADLINE, VOTING_DEADLINE):
        clock.set(moment)
        response = await call(client, organizer, "GET", f"/api/contests/{contest_id}")
        assert response.json()["allowed_actions"] == ["view_results"]
