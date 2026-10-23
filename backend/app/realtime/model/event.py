"""Сигнал «перечитай данные» и его адресаты.

Данных в событии нет: клиент перечитывает их по API со своими правами. Поэтому утечка через
событие невозможна по построению, а аудиторию (кому слать) вычисляет публикующий сервис по
политике своего модуля (CLAUDE.md §4.2).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

from app.common.exception import DomainValidationError
from app.common.model import ContestId, IdeaId, UserId, UserRole

WIRE_VERSION: Final = 1
MAX_CONNECTIONS_PER_USER: Final = 10
MAX_INCOMING_BYTES: Final = 1024  # клиент шлёт только ping
REVERIFY_INTERVAL_S: Final = 60.0

# Коды закрытия WebSocket (4000–4999 — прикладные).
CLOSE_GOING_AWAY: Final = 1012  # перезапуск сервиса: клиент переподключается и перечитывает данные
CLOSE_NOT_AUTHENTICATED: Final = 4401
CLOSE_FORBIDDEN: Final = 4403
CLOSE_MESSAGE_TOO_BIG: Final = 1009

PING: Final = "ping"
PONG_MESSAGE: Final = {"v": WIRE_VERSION, "type": "pong"}


class EventType(StrEnum):
    IDEAS_CHANGED = "ideas_changed"
    IDEA_DELETED = "idea_deleted"
    RESULTS_CHANGED = "results_changed"
    SESSION_REVOKED = "session_revoked"


@dataclass(frozen=True, slots=True)
class ContestEvent:
    """`contest_id` задан для событий конкурса; `session_revoked` его не имеет."""

    type: EventType
    contest_id: ContestId | None = None
    idea_id: IdeaId | None = None

    def __post_init__(self) -> None:
        if self.type is EventType.SESSION_REVOKED:
            return
        if self.contest_id is None:
            raise DomainValidationError("Событие конкурса должно указывать конкурс")
        if self.type is EventType.IDEA_DELETED and self.idea_id is None:
            raise DomainValidationError("Удаление идеи должно указывать идею")

    def to_wire(self) -> dict[str, Any]:
        """Сообщение для клиента: версия, тип, конкурс и (для удаления) идея. Ничего больше."""
        message: dict[str, Any] = {"v": WIRE_VERSION, "type": self.type.value}
        if self.contest_id is not None:
            message["contest_id"] = int(self.contest_id)
        if self.idea_id is not None:
            message["idea_id"] = str(self.idea_id)
        return message


@dataclass(frozen=True, slots=True)
class Audience:
    """Кому слать: перечисленным пользователям и/или всем вошедшим с указанной ролью."""

    users: frozenset[UserId] = field(default_factory=frozenset)
    roles: frozenset[UserRole] = field(default_factory=frozenset)

    def includes(self, user_id: UserId, role: UserRole) -> bool:
        return user_id in self.users or role in self.roles


@dataclass(frozen=True, slots=True)
class PlannedEvent:
    """Событие вместе с адресатами: так публикующий сервис отдаёт `realtime` готовое решение."""

    event: ContestEvent
    audience: Audience
