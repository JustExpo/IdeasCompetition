"""Идентификаторы сущностей и проверка времени, общие для всех модулей."""

from datetime import datetime
from typing import NewType
from uuid import UUID

from app.common.exception import DomainValidationError

UserId = NewType("UserId", int)
ContestId = NewType("ContestId", int)
# Идея получает случайный UUIDv4, а не порядковый номер: по последовательным
# номерам можно вычислить автора в фазе голосования (CLAUDE.md, Р7).
IdeaId = NewType("IdeaId", UUID)


def require_aware(value: datetime, field: str) -> None:
    """Отклоняет время без часового пояса: все моменты в системе хранятся в UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"Поле {field} должно содержать часовой пояс")
