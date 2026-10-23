"""Клиент WebSocket поверх ASGI в том же event loop: сети и портов не нужно, БД — настоящая."""

import asyncio
import contextlib
import json
from typing import Any, Self

from fastapi import FastAPI
from starlette.types import Message

from tests.integration.contests.conftest import ORIGIN, Person

TIMEOUT_S = 3.0


class WebSocketClient:
    def __init__(
        self,
        app: FastAPI,
        contest_id: int,
        *,
        person: Person | None = None,
        cookie: str | None = None,
        origin: str | None = ORIGIN,
    ) -> None:
        token = cookie if cookie is not None else (person.cookie if person else None)
        headers = [(b"host", b"127.0.0.1:8000")]
        if origin is not None:
            headers.append((b"origin", origin.encode()))
        if token is not None:
            headers.append((b"cookie", f"sid={token}".encode()))
        path = f"/api/contests/{contest_id}/events"
        self._scope: dict[str, Any] = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 8000),
            "subprotocols": [],
            "state": {},
        }
        self._app = app
        self._incoming: asyncio.Queue[Message] = asyncio.Queue()
        self._outgoing: asyncio.Queue[Message] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self.accepted = False
        self.close_code: int | None = None

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        await self._incoming.put({"type": "websocket.connect"})
        self._task = asyncio.create_task(
            self._app(self._scope, self._incoming.get, self._outgoing.put)
        )
        first = await self._next_message()
        if first["type"] == "websocket.accept":
            self.accepted = True
        else:
            self.close_code = first.get("code", 1000)

    async def _next_message(self) -> Message:
        return await asyncio.wait_for(self._outgoing.get(), timeout=TIMEOUT_S)

    async def receive_json(self) -> dict[str, Any]:
        message = await self._next_message()
        if message["type"] == "websocket.close":
            self.close_code = message.get("code", 1000)
            raise AssertionError(f"соединение закрыто кодом {self.close_code}")
        return json.loads(message["text"])  # type: ignore[no-any-return]

    async def expect_close(self) -> int:
        """Дождаться закрытия сервером и вернуть код (сообщения до закрытия пропускаются)."""
        while True:
            message = await self._next_message()
            if message["type"] == "websocket.close":
                self.close_code = message.get("code", 1000)
                return self.close_code

    async def send_text(self, text: str) -> None:
        await self._incoming.put({"type": "websocket.receive", "text": text})

    async def expect_silence(self, seconds: float = 0.15) -> None:
        """Убедиться, что сервер ничего не прислал. Перед вызовом нужен ping/pong: так
        все события, отправленные раньше, уже точно дошли."""
        try:
            message = await asyncio.wait_for(self._outgoing.get(), timeout=seconds)
        except TimeoutError:
            return
        raise AssertionError(f"неожиданное сообщение: {message}")

    async def disconnect(self) -> None:
        if self._task is None:
            return
        await self._incoming.put({"type": "websocket.disconnect", "code": 1000})
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(self._task, timeout=TIMEOUT_S)
        self._task = None
