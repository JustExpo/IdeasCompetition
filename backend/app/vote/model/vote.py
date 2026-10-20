"""Голос сотрудника за идею."""

from dataclasses import dataclass
from datetime import datetime

from app.common.model import IdeaId, UserId, require_aware


@dataclass(frozen=True, slots=True)
class Vote:
    """Один голос на пару (идея, голосующий). Уникальность держит первичный ключ в БД."""

    idea_id: IdeaId
    voter_id: UserId
    created_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
