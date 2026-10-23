"""Внутрипроцессная шина событий и реестр открытых WebSocket-соединений (Р8).

Приложение работает одним процессом (`workers=1`), поэтому LISTEN/NOTIFY и брокер не нужны:
сервис публикует событие после commit, шина кладёт его в очередь каждого подходящего соединения.
Очередь ограничена. Событие — только сигнал «перечитай», поэтому при переполнении новое
событие отбрасывается: в очереди уже лежит непрочитанный сигнал, а клиент перечитывает всё.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Final, Protocol

from app.common.model import ContestId, UserId, UserRole
from app.core.logging import get_logger
from app.realtime.exception import TooManyConnectionsError
from app.realtime.model import (
    MAX_CONNECTIONS_PER_USER,
    Audience,
    ContestEvent,
    EventType,
    PlannedEvent,
)

QUEUE_SIZE: Final = 16

_log = get_logger(__name__)


class EventPublisher(Protocol):
    """Порт публикации: сервисы модулей зависят от него, а не от шины (CLAUDE.md §3.3, Р2)."""

    def publish(self, planned: PlannedEvent) -> None: ...

    def revoke_session(self, session_key: bytes) -> None: ...


class NullEventPublisher:
    """Ничего не публикует: значение по умолчанию там, где открытых вкладок нет (CLI, тесты)."""

    def publish(self, planned: PlannedEvent) -> None:
        return None

    def revoke_session(self, session_key: bytes) -> None:
        return None


NULL_EVENT_PUBLISHER: Final = NullEventPublisher()


@dataclass(eq=False, slots=True)
class Subscription:
    """Одно открытое соединение: кому оно принадлежит и какой конкурс слушает."""

    contest_id: ContestId
    user_id: UserId
    role: UserRole
    session_key: bytes
    queue: asyncio.Queue[ContestEvent | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE)
    )

    def push(self, event: ContestEvent) -> None:
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            _log.warning("event_dropped_queue_full")

    def close(self) -> None:
        """Разбудить обработчик соединения: `None` в очереди означает «закрывайся»."""
        while True:
            try:
                self.queue.put_nowait(None)
                return
            except asyncio.QueueFull:
                self.queue.get_nowait()


class EventHub:
    def __init__(self, max_per_user: int = MAX_CONNECTIONS_PER_USER) -> None:
        self._max_per_user = max_per_user
        self._by_user: defaultdict[UserId, set[Subscription]] = defaultdict(set)

    def subscribe(
        self, contest_id: ContestId, user_id: UserId, role: UserRole, session_key: bytes
    ) -> Subscription:
        if len(self._by_user[user_id]) >= self._max_per_user:
            raise TooManyConnectionsError("Слишком много открытых соединений.")
        subscription = Subscription(contest_id, user_id, role, session_key)
        self._by_user[user_id].add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        connections = self._by_user.get(subscription.user_id)
        if connections is None:
            return
        connections.discard(subscription)
        if not connections:
            del self._by_user[subscription.user_id]

    def connection_count(self, user_id: UserId | None = None) -> int:
        if user_id is not None:
            return len(self._by_user.get(user_id, ()))
        return sum(len(connections) for connections in self._by_user.values())

    def publish(self, planned: PlannedEvent) -> None:
        """Разослать событие подходящим соединениям; вызывается после commit."""
        event, audience = planned.event, planned.audience
        for subscription in self._targets(event, audience):
            subscription.push(event)

    def revoke_session(self, session_key: bytes) -> None:
        """Выход в одной вкладке закрывает соединения этой сессии, но не других сессий."""
        notice = ContestEvent(EventType.SESSION_REVOKED)
        for connections in list(self._by_user.values()):
            for subscription in list(connections):
                if subscription.session_key == session_key:
                    subscription.push(notice)
                    subscription.close()

    def close_all(self) -> None:
        """Остановка сервиса: закрыть все соединения; клиенты переподключатся (1012)."""
        for connections in list(self._by_user.values()):
            for subscription in list(connections):
                subscription.close()

    def _targets(self, event: ContestEvent, audience: Audience) -> list[Subscription]:
        return [
            subscription
            for connections in self._by_user.values()
            for subscription in connections
            if subscription.contest_id == event.contest_id
            and audience.includes(subscription.user_id, subscription.role)
        ]
