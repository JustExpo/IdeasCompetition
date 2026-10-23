"""WebSocket `/api/contests/{id}/events`: сигналы «перечитай» открытой вкладке (CLAUDE.md §8.2).

Данных в сообщениях нет, поэтому права и анонимность проверяются в одном месте — в REST.
Здесь проверяется только, кто подключился, и открыто ли не больше предела соединений.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Final, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.requests import HTTPConnection

from app.common.model import Actor, ContestId
from app.core.access import Policy, require
from app.core.logging import get_logger
from app.realtime.exception import TooManyConnectionsError
from app.realtime.model import (
    CLOSE_FORBIDDEN,
    CLOSE_GOING_AWAY,
    CLOSE_MESSAGE_TOO_BIG,
    CLOSE_NOT_AUTHENTICATED,
    MAX_INCOMING_BYTES,
    PING,
    PONG_MESSAGE,
    REVERIFY_INTERVAL_S,
    WIRE_VERSION,
    EventType,
)
from app.realtime.service import EventHub, Subscription

CLOSE_POLICY_VIOLATION: Final = 1008

router = APIRouter()
_log = get_logger(__name__)

SessionKeyResolver = Callable[[HTTPConnection], bytes | None]
ActorResolver = Callable[[HTTPConnection], Awaitable[Actor | None]]


async def _close(websocket: WebSocket, code: int) -> None:
    # Клиент мог уйти раньше: закрытие уже закрытого соединения — не ошибка.
    with contextlib.suppress(RuntimeError, WebSocketDisconnect):
        await websocket.close(code=code)


async def _pump_events(websocket: WebSocket, subscription: Subscription) -> None:
    """Очередь шины → вкладка. `None` в очереди — остановка сервиса (1012)."""
    while True:
        event = await subscription.queue.get()
        if event is None:
            await _close(websocket, CLOSE_GOING_AWAY)
            return
        await websocket.send_json(event.to_wire())
        if event.type is EventType.SESSION_REVOKED:
            await _close(websocket, CLOSE_NOT_AUTHENTICATED)
            return


async def _read_client(websocket: WebSocket) -> None:
    """Входящие сообщения — только `ping` и не больше 1 КБ; остальное закрывает соединение."""
    while True:
        text = await websocket.receive_text()
        if len(text.encode()) > MAX_INCOMING_BYTES:
            await _close(websocket, CLOSE_MESSAGE_TOO_BIG)
            return
        if text != PING:
            await _close(websocket, CLOSE_POLICY_VIOLATION)
            return
        await websocket.send_json(PONG_MESSAGE)


async def _reverify_session(websocket: WebSocket, resolver: ActorResolver) -> None:
    """Раз в минуту проверить, что сессия жива: отзыв через CLI не проходит через шину."""
    while True:
        await asyncio.sleep(REVERIFY_INTERVAL_S)
        if await resolver(websocket) is None:
            await _close(websocket, CLOSE_NOT_AUTHENTICATED)
            return


@router.websocket("/api/contests/{contest_id}/events", dependencies=[require(Policy.AUTHENTICATED)])
async def contest_events(websocket: WebSocket, contest_id: int) -> None:
    state = websocket.app.state
    # Origin проверяется до `accept` (CSWSH): cookie SameSite=Lax от чужой страницы на
    # WebSocket не защищает, а без Origin браузерное соединение не бывает.
    if websocket.headers.get("origin") not in state.settings.allowed_origins:
        await websocket.close(code=CLOSE_POLICY_VIOLATION)
        return
    await websocket.accept()
    actor = cast("Actor | None", websocket.state.actor)
    session_key: bytes | None = state.session_key_resolver(websocket)
    if actor is None or session_key is None:
        await _close(websocket, CLOSE_NOT_AUTHENTICATED)
        return
    hub: EventHub = state.events
    try:
        subscription = hub.subscribe(ContestId(contest_id), actor.user_id, actor.role, session_key)
    except TooManyConnectionsError:
        await _close(websocket, CLOSE_FORBIDDEN)
        return
    _log.info("ws_connected", contest_id=contest_id)
    try:
        await websocket.send_json(
            {"v": WIRE_VERSION, "type": "hello", "build": state.settings.app_build}
        )
        tasks = {
            asyncio.create_task(_pump_events(websocket, subscription)),
            asyncio.create_task(_read_client(websocket)),
            asyncio.create_task(_reverify_session(websocket, state.actor_resolver)),
        }
        _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            # Обрыв клиента — обычное завершение; остальное не должно пропасть молча.
            if isinstance(result, BaseException) and not isinstance(
                result, asyncio.CancelledError | WebSocketDisconnect | RuntimeError
            ):
                _log.error("ws_failed", error_type=type(result).__name__)
    finally:
        hub.unsubscribe(subscription)
        _log.info("ws_disconnected", contest_id=contest_id)
