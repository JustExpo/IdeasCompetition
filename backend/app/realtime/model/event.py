"""Сигнал «перечитай данные».

Данных в событии нет: клиент перечитывает их по API со своими правами.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.common.exception import DomainValidationError
from app.common.model import ContestId, IdeaId, UserId


class EventType(StrEnum):
    IDEAS_CHANGED = "ideas_changed"
    IDEA_DELETED = "idea_deleted"
    PHASE_CHANGED = "phase_changed"
    RESULTS_CHANGED = "results_changed"
    SESSION_REVOKED = "session_revoked"


@dataclass(frozen=True, slots=True)
class ContestEvent:
    """`contest_id` задан для событий конкурса; `user_id` — для адресных (отзыв сессии)."""

    type: EventType
    contest_id: ContestId | None = None
    idea_id: IdeaId | None = None
    user_id: UserId | None = None

    def __post_init__(self) -> None:
        if self.type is EventType.SESSION_REVOKED:
            if self.user_id is None:
                raise DomainValidationError("Отзыв сессии адресуется пользователю")
            return
        if self.contest_id is None:
            raise DomainValidationError("Событие конкурса должно указывать конкурс")
        if self.type is EventType.IDEA_DELETED and self.idea_id is None:
            raise DomainValidationError("Удаление идеи должно указывать идею")
