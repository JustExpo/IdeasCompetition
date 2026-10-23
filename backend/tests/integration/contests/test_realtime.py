"""События реального времени: кому, когда и только после commit (П3, П5, П7, П11; IC-024)."""

import secrets
import sys
from collections.abc import Awaitable, Callable
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import dao as auth_dao
from app.auth.service import hash_session_token
from app.auth.service.sessions import open_session
from app.core.db import Database
from app.realtime.controller import router as realtime_router
from app.user import service as user_service
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import (
    SUBMISSION_DEADLINE,
    Person,
    call,
)
from tests.integration.contests.mailbox import run_to_voting
from tests.integration.contests.ws_client import WebSocketClient

pytestmark = pytest.mark.commits

NewContest = Callable[..., Awaitable[int]]
NewIdea = Callable[..., Awaitable[httpx.Response]]


async def sync(*clients: WebSocketClient) -> None:
    """Дождаться, пока сервер обработал всё, что уже лежало в очередях: ping → pong."""
    for ws in clients:
        await ws.send_text("ping")
        assert (await ws.receive_json())["type"] == "pong"


async def test_anonymous_gets_close_4401(app: FastAPI, new_contest: NewContest) -> None:
    contest_id = await new_contest()
    async with WebSocketClient(app, contest_id) as ws:
        assert ws.accepted
        assert await ws.expect_close() == 4401


async def test_foreign_origin_is_rejected_before_accept(
    app: FastAPI, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    for origin in ("https://evil.example", None):
        async with WebSocketClient(app, contest_id, person=anna, origin=origin) as ws:
            assert not ws.accepted
            assert ws.close_code == 1008


async def test_hello_carries_build_and_ping_gets_pong(
    app: FastAPI, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    async with WebSocketClient(app, contest_id, person=anna) as ws:
        assert await ws.receive_json() == {"v": 1, "type": "hello", "build": "dev"}
        await ws.send_text("ping")
        assert await ws.receive_json() == {"v": 1, "type": "pong"}


async def test_every_response_carries_the_build_header(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.headers["x-app-build"] == "dev"


async def test_submission_events_reach_only_author_and_organizer(
    app: FastAPI,
    client: httpx.AsyncClient,
    anna: Person,
    boris: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    async with (
        WebSocketClient(app, contest_id, person=anna) as a,
        WebSocketClient(app, contest_id, person=boris) as b,
        WebSocketClient(app, contest_id, person=organizer) as o,
    ):
        for ws in (a, b, o):
            assert (await ws.receive_json())["type"] == "hello"

        response = await new_idea(anna, contest_id)
        assert response.status_code == 201

        assert await a.receive_json() == {"v": 1, "type": "ideas_changed", "contest_id": contest_id}
        assert await o.receive_json() == {
            "v": 1,
            "type": "results_changed",
            "contest_id": contest_id,
        }
        await sync(b)  # П3: чужая подача Борису не видна даже как сигнал
        await b.expect_silence()
        await sync(a, o)
        await a.expect_silence()
        await o.expect_silence()


async def test_edit_signals_author_and_organizer(
    app: FastAPI,
    client: httpx.AsyncClient,
    anna: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    created = (await new_idea(anna, contest_id)).json()
    async with (
        WebSocketClient(app, contest_id, person=anna) as a,
        WebSocketClient(app, contest_id, person=organizer) as o,
    ):
        await a.receive_json()
        await o.receive_json()
        response = await call(
            client,
            anna,
            "PATCH",
            f"/api/ideas/{created['id']}",
            json={"title": "Другое", "description": "Описание", "version": created["version"]},
        )
        assert response.status_code == 200
        assert (await a.receive_json())["type"] == "ideas_changed"
        assert (await o.receive_json())["type"] == "results_changed"


async def test_repeated_submission_sends_no_second_signal(
    app: FastAPI,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    key = str(uuid4())
    async with WebSocketClient(app, contest_id, person=anna) as a:
        await a.receive_json()
        assert (await new_idea(anna, contest_id, client_request_id=key)).status_code == 201
        assert (await a.receive_json())["type"] == "ideas_changed"
        assert (await new_idea(anna, contest_id, client_request_id=key)).status_code == 200
        await sync(a)
        await a.expect_silence()


async def test_rejected_write_publishes_nothing(
    app: FastAPI,
    clock: FrozenClock,
    anna: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest_id = await new_contest()
    clock.set(SUBMISSION_DEADLINE)
    async with (
        WebSocketClient(app, contest_id, person=anna) as a,
        WebSocketClient(app, contest_id, person=organizer) as o,
    ):
        await a.receive_json()
        await o.receive_json()
        assert (await new_idea(anna, contest_id)).status_code == 409
        await sync(a, o)
        await a.expect_silence()
        await o.expect_silence()


async def test_deleting_in_voting_reaches_everyone_and_organizer_recounts(
    app: FastAPI,
    client: httpx.AsyncClient,
    clock: FrozenClock,
    anna: Person,
    boris: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    idea_id = contest.ideas["Идея Анны"]
    async with (
        WebSocketClient(app, contest.id, person=anna) as a,
        WebSocketClient(app, contest.id, person=boris) as b,
        WebSocketClient(app, contest.id, person=organizer) as o,
    ):
        for ws in (a, b, o):
            await ws.receive_json()
        assert (await call(client, anna, "DELETE", f"/api/ideas/{idea_id}")).status_code == 204

        for ws in (a, b, o):
            assert await ws.receive_json() == {
                "v": 1,
                "type": "idea_deleted",
                "contest_id": contest.id,
                "idea_id": idea_id,
            }
        assert (await o.receive_json())["type"] == "results_changed"


async def test_vote_signals_organizer_and_voters_other_tab_only(
    app: FastAPI,
    client: httpx.AsyncClient,
    clock: FrozenClock,
    anna: Person,
    boris: Person,
    organizer: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    anna_idea = contest.ideas["Идея Анны"]
    async with (
        WebSocketClient(app, contest.id, person=anna) as a,
        WebSocketClient(app, contest.id, person=boris) as b_tab_1,
        WebSocketClient(app, contest.id, person=boris) as b_tab_2,
        WebSocketClient(app, contest.id, person=organizer) as o,
    ):
        for ws in (a, b_tab_1, b_tab_2, o):
            await ws.receive_json()
        assert (await call(client, boris, "PUT", f"/api/ideas/{anna_idea}/vote")).status_code == 204

        assert (await o.receive_json())["type"] == "results_changed"
        assert (await b_tab_1.receive_json())["type"] == "ideas_changed"
        assert (await b_tab_2.receive_json())["type"] == "ideas_changed"
        await sync(a)  # автор идеи не узнаёт, кто и когда голосовал
        await a.expect_silence()

        # Повторный голос ничего не меняет: сигнала нет. Отзыв — есть.
        assert (await call(client, boris, "PUT", f"/api/ideas/{anna_idea}/vote")).status_code == 204
        assert (
            await call(client, boris, "DELETE", f"/api/ideas/{anna_idea}/vote")
        ).status_code == 204
        assert (await o.receive_json())["type"] == "results_changed"
        await sync(o)
        await o.expect_silence()


async def test_signals_are_per_contest(
    app: FastAPI,
    anna: Person,
    new_contest: NewContest,
    new_idea: NewIdea,
) -> None:
    first = await new_contest()
    second = await new_contest(topic="Другой конкурс")
    async with WebSocketClient(app, second, person=anna) as other:
        await other.receive_json()
        assert (await new_idea(anna, first)).status_code == 201
        await sync(other)
        await other.expect_silence()


async def test_connection_limit_per_user(
    app: FastAPI, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    opened = [WebSocketClient(app, contest_id, person=anna) for _ in range(10)]
    try:
        for ws in opened:
            await ws.connect()
            assert ws.accepted
            assert (await ws.receive_json())["type"] == "hello"
        eleventh = WebSocketClient(app, contest_id, person=anna)
        await eleventh.connect()
        assert await eleventh.expect_close() == 4403
        await eleventh.disconnect()
    finally:
        for ws in opened:
            await ws.disconnect()
    assert app.state.events.connection_count() == 0


async def test_logout_closes_only_that_sessions_sockets(
    app: FastAPI,
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    anna: Person,
    new_contest: NewContest,
) -> None:
    contest_id = await new_contest()
    other_token = await _second_session(database, clock, anna)
    async with (
        WebSocketClient(app, contest_id, person=anna) as here,
        WebSocketClient(app, contest_id, cookie=other_token) as elsewhere,
    ):
        await here.receive_json()
        await elsewhere.receive_json()
        assert (await call(client, anna, "POST", "/api/auth/logout")).status_code == 204

        assert (await here.receive_json())["type"] == "session_revoked"
        assert await here.expect_close() == 4401
        await sync(elsewhere)
        await elsewhere.expect_silence()


async def test_revoked_session_is_noticed_by_periodic_check(
    app: FastAPI,
    database: Database,
    clock: FrozenClock,
    anna: Person,
    new_contest: NewContest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Пакет реэкспортирует `router`, поэтому модуль берём из sys.modules, а не по пути атрибутов.
    monkeypatch.setattr(sys.modules["app.realtime.controller.router"], "REVERIFY_INTERVAL_S", 0.05)
    contest_id = await new_contest()
    async with WebSocketClient(app, contest_id, person=anna) as ws:
        await ws.receive_json()
        # Отзыв мимо шины (как сделал бы оператор через CLI): сообщит только перепроверка.
        await database.run_in_transaction(
            lambda session: auth_dao.revoke_session(
                session, hash_session_token(anna.cookie), clock.now()
            )
        )
        assert await ws.expect_close() == 4401


async def test_shutdown_closes_sockets_with_1012(
    app: FastAPI, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    async with WebSocketClient(app, contest_id, person=anna) as ws:
        await ws.receive_json()
        app.state.events.close_all()
        assert await ws.expect_close() == 1012


async def test_oversized_and_unknown_messages_close_the_socket(
    app: FastAPI, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    async with WebSocketClient(app, contest_id, person=anna) as ws:
        await ws.receive_json()
        await ws.send_text("x" * 1025)
        assert await ws.expect_close() == 1009
    async with WebSocketClient(app, contest_id, person=anna) as ws:
        await ws.receive_json()
        await ws.send_text("hello")
        assert await ws.expect_close() == 1008


async def test_disconnect_frees_the_slot(
    app: FastAPI, anna: Person, new_contest: NewContest
) -> None:
    contest_id = await new_contest()
    async with WebSocketClient(app, contest_id, person=anna) as ws:
        await ws.receive_json()
        assert app.state.events.connection_count(anna.id) == 1
    assert app.state.events.connection_count(anna.id) == 0


async def test_websocket_route_declares_a_policy() -> None:
    # `create_app` падает на маршруте без политики; здесь проверяем, что маршрут вообще есть.
    assert any(
        getattr(route, "path", "") == "/api/contests/{contest_id}/events"
        for route in realtime_router.routes
    )


async def _second_session(database: Database, clock: FrozenClock, person: Person) -> str:
    token = secrets.token_urlsafe(32)

    async def work(session: AsyncSession) -> None:
        user = await user_service.get_user(session, person.id)
        assert user is not None
        await open_session(session, user, token, clock.now())

    await database.run_in_transaction(work)
    return token
