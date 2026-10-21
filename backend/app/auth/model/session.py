"""Серверная сессия."""

from dataclasses import dataclass
from datetime import datetime

from app.common.model import UserId, require_aware


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
