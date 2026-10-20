"""Серверная сессия и действующее лицо запроса."""

from dataclasses import dataclass
from datetime import datetime

from app.common.model import UserId, require_aware
from app.user.model import UserRole


@dataclass(frozen=True, slots=True)
class Session:
    """Сессия браузера. Токен хранится только хэшем (в dao), здесь его нет."""

    id: int
    user_id: UserId
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.expires_at, "expires_at")
        if self.revoked_at is not None:
            require_aware(self.revoked_at, "revoked_at")

    def is_valid_at(self, now: datetime) -> bool:
        """Сессия действует, пока не отозвана и не истекла (граница expires_at уже не действует)."""
        return self.revoked_at is None and now < self.expires_at


@dataclass(frozen=True, slots=True)
class Actor:
    """Кто выполняет запрос. Роль читается из БД на каждый запрос и не кэшируется."""

    user_id: UserId
    role: UserRole

    @property
    def is_organizer(self) -> bool:
        return self.role is UserRole.ORGANIZER
