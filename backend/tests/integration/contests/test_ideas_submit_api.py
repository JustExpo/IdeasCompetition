"""Подача идеи: идемпотентный повтор, границы дедлайна, лимиты, гонки (Ф2, П2; IC-011)."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.core.db import Database
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    MICROSECOND,
    NOW,
    SUBMISSION_DEADLINE,
    Person,
    call,
)

pytestmark = pytest.mark.commits

NewContest = Callable[..., Awaitable[int]]
NewIdea = Callable[..., Awaitable[httpx.Response]]


async def count_ideas(database: Database) -> int:
    async def work(session: object) -> int:
        result = await session.execute(text("SELECT count(*) FROM ideas"))  # type: ignore[attr-defined]
        return int(result.scalar_one())

    return await database.run_in_transaction(work)


async def test_employee_submits_idea(
    anna: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    response = await new_idea(anna, contest_id)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id",
        "contest_id",
        "title",
        "description",
        "version",
        "submitted_at",
        "updated_at",
    }
    assert body["contest_id"] == contest_id
    assert body["version"] == 1
    assert body["submitted_at"] == body["updated_at"]
    assert datetime.fromisoformat(body["submitted_at"]) == NOW


async def test_identifier_is_a_random_uuid_not_a_sequence(
    anna: Person, boris: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    first = (await new_idea(anna, contest_id)).json()["id"]
    second = (await new_idea(boris, contest_id)).json()["id"]
    assert len(first) == len(second) == 36
    assert first[14] == second[14] == "4"  # версия 4: случайный, а не порядковый номер (Р7)


async def test_same_key_and_body_returns_the_same_idea(
    anna: Person, new_contest: NewContest, new_idea: NewIdea, database: Database
) -> None:
    contest_id = await new_contest()
    key = str(uuid4())
    first = await new_idea(anna, contest_id, client_request_id=key)
    again = await new_idea(anna, contest_id, client_request_id=key)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json() == again.json()
    assert await count_ideas(database) == 1


async def test_same_key_with_other_body_or_contest_is_an_error(
    anna: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    other_contest = await new_contest(topic="Другой конкурс")
    key = str(uuid4())
    assert (await new_idea(anna, contest_id, client_request_id=key)).status_code == 201
    for kwargs in (
        {"contest_id": contest_id, "title": "Другое название"},
        {"contest_id": contest_id, "description": "Другое описание"},
        {"contest_id": other_contest},
    ):
        response = await new_idea(anna, client_request_id=key, **kwargs)
        assert response.status_code == 422
        assert response.json()["code"] == "idempotency_key_reused"


async def test_idempotency_key_is_per_author(
    anna: Person, boris: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    key = str(uuid4())
    assert (await new_idea(anna, contest_id, client_request_id=key)).status_code == 201
    # Чужой ключ ничего не раскрывает и не мешает: у Бориса это его первая идея.
    assert (await new_idea(boris, contest_id, client_request_id=key)).status_code == 201


@pytest.mark.parametrize(
    ("moment", "status"),
    [
        (SUBMISSION_DEADLINE - MICROSECOND, 201),
        (SUBMISSION_DEADLINE, 409),
        (SUBMISSION_DEADLINE + MICROSECOND, 409),
    ],
)
async def test_submission_closes_exactly_at_the_deadline(
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    clock: FrozenClock,
    moment: datetime,
    status: int,
) -> None:
    contest_id = await new_contest()
    clock.set(moment)
    response = await new_idea(anna, contest_id)
    assert response.status_code == status
    if status == 409:
        assert response.json()["code"] == "submission_closed"


async def test_retry_after_the_deadline_returns_the_accepted_idea(
    anna: Person, new_contest: NewContest, new_idea: NewIdea, clock: FrozenClock
) -> None:
    contest_id = await new_contest()
    key = str(uuid4())
    first = await new_idea(anna, contest_id, client_request_id=key)
    clock.set(SUBMISSION_DEADLINE)
    again = await new_idea(anna, contest_id, client_request_id=key)
    # Ответ на принятый запрос мог потеряться по сети: повтор после дедлайна — не 409 (П2).
    assert again.status_code == 200
    assert again.json() == first.json()
    fresh = await new_idea(anna, contest_id)
    assert fresh.status_code == 409


async def test_organizer_and_anonymous_cannot_submit(
    client: httpx.AsyncClient, organizer: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    response = await new_idea(organizer, contest_id)
    assert response.status_code == 403
    assert response.json()["code"] == "organizer_cannot_participate"
    anonymous = await call(
        client,
        None,
        "POST",
        f"/api/contests/{contest_id}/ideas",
        json={"title": "t", "description": "d", "client_request_id": str(uuid4())},
    )
    assert anonymous.status_code == 401


async def test_unknown_contest_is_404(anna: Person, new_idea: NewIdea) -> None:
    response = await new_idea(anna, 999_999)
    assert response.status_code == 404
    assert response.json()["code"] == "contest_not_found"


async def test_twenty_first_idea_of_an_author_is_rejected(
    anna: Person, boris: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    other_contest = await new_contest(topic="Другой")
    for number in range(20):
        assert (await new_idea(anna, contest_id, title=f"Идея {number}")).status_code == 201
    over = await new_idea(anna, contest_id, title="Лишняя")
    assert over.status_code == 409
    assert over.json()["code"] == "idea_limit_reached"
    # Предел — на автора и на конкурс: другой автор и другой конкурс не затронуты.
    assert (await new_idea(boris, contest_id)).status_code == 201
    assert (await new_idea(anna, other_contest)).status_code == 201


async def test_contest_is_full(
    monkeypatch: pytest.MonkeyPatch,
    anna: Person,
    boris: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    monkeypatch.setattr("app.idea.service.ideas.IDEAS_PER_CONTEST_LIMIT", 2)
    contest_id = await new_contest()
    assert (await new_idea(anna, contest_id)).status_code == 201
    assert (await new_idea(boris, contest_id)).status_code == 201
    full = await new_idea(anna, contest_id)
    assert full.status_code == 409
    assert full.json()["code"] == "contest_full"


@pytest.mark.parametrize(
    ("title", "description"),
    [
        ("", "описание"),
        ("   ", "описание"),
        ("название", "   "),
        ("на\x00звание", "описание"),
        ("название", "опи\x00сание"),
        ("название", "опи‮сание"),
        ("на\nзвание", "описание"),  # перевод строки допустим только в описании
        ("н" * 201, "описание"),
        ("название", "о" * 10_001),
    ],
)
async def test_invalid_text_is_rejected(
    anna: Person, new_contest: NewContest, new_idea: NewIdea, title: str, description: str
) -> None:
    contest_id = await new_contest()
    response = await new_idea(anna, contest_id, title=title, description=description)
    assert response.status_code == 422
    assert response.json()["code"] in {"invalid_idea", "validation_error"}


async def test_lone_surrogate_is_rejected(
    client: httpx.AsyncClient,
    anna: Person,
    new_contest: NewContest,
    database: Database,
) -> None:
    contest_id = await new_contest()
    # Одиночный суррогат нельзя закодировать в UTF-8, поэтому шлём JSON-экранирование вручную.
    head = '{"title": "плохой\\ud800символ", "description": "d", "client_request_id": "'
    raw = (head + str(uuid4()) + '"}').encode()
    response = await client.post(
        f"/api/contests/{contest_id}/ideas",
        content=raw,
        headers={"cookie": f"sid={anna.cookie}", "content-type": "application/json"},
    )
    assert response.status_code in {400, 422}
    assert await count_ideas(database) == 0


async def test_text_of_maximum_length_is_accepted_and_normalized(
    anna: Person, new_contest: NewContest, new_idea: NewIdea
) -> None:
    contest_id = await new_contest()
    longest = await new_idea(anna, contest_id, title="н" * 200, description="о\nп\tи" * 100)
    assert longest.status_code == 201
    normalized = await new_idea(anna, contest_id, title="  Ёлка  ", description=" текст ")
    assert normalized.json()["title"] == "Ёлка"
    assert normalized.json()["description"] == "текст"


async def test_missing_key_and_unknown_fields_are_rejected(
    client: httpx.AsyncClient, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    path = f"/api/contests/{contest_id}/ideas"
    no_key = await call(client, anna, "POST", path, json={"title": "t", "description": "d"})
    assert no_key.status_code == 422
    extra = await call(
        client,
        anna,
        "POST",
        path,
        json={
            "title": "t",
            "description": "d",
            "client_request_id": str(uuid4()),
            "author_id": 1,
        },
    )
    assert extra.status_code == 422
    bad_key = await call(
        client,
        anna,
        "POST",
        path,
        json={"title": "t", "description": "d", "client_request_id": "not-a-uuid"},
    )
    assert bad_key.status_code == 422


async def test_parallel_retries_with_one_key_create_a_single_idea(
    anna: Person, new_contest: NewContest, new_idea: NewIdea, database: Database
) -> None:
    contest_id = await new_contest()
    key = str(uuid4())
    responses = await asyncio.gather(
        *(new_idea(anna, contest_id, client_request_id=key) for _ in range(8))
    )
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] * 7 + [201]
    assert len({response.json()["id"] for response in responses}) == 1
    assert await count_ideas(database) == 1


async def test_parallel_submissions_with_distinct_keys_are_all_accepted(
    anna: Person, boris: Person, new_contest: NewContest, new_idea: NewIdea, database: Database
) -> None:
    contest_id = await new_contest()
    responses = await asyncio.gather(
        *(new_idea(person, contest_id) for person in (anna, boris) for _ in range(4))
    )
    assert {response.status_code for response in responses} == {201}
    assert await count_ideas(database) == 8


async def test_idea_text_never_reaches_the_logs(
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
    capsys: pytest.CaptureFixture[str],
) -> None:
    contest_id = await new_contest()
    await new_idea(anna, contest_id, title="Секретное название", description="Секретный текст")
    captured = capsys.readouterr()
    assert "Секретное название" not in captured.out + captured.err
    assert "Секретный текст" not in captured.out + captured.err
