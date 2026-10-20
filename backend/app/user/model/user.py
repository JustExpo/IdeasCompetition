"""Пользователь сервиса и его роль."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.common.model import UserId, require_aware


class UserRole(StrEnum):
    """Роль определяет, что пользователь может делать в конкурсе."""

    EMPLOYEE = "employee"  # подаёт идеи и голосует
    ORGANIZER = "organizer"  # создаёт конкурсы и видит экран организатора, сам не участвует


@dataclass(frozen=True, slots=True)
class User:
    """Учётная запись. Хэш пароля сюда не входит: он живёт только в dao и auth.

    E-mail и имя скрыты из repr, чтобы персональные данные не попадали в логи.
    """

    id: UserId
    email: str = field(repr=False)
    name: str = field(repr=False)
    role: UserRole
    is_active: bool
    created_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")

    @property
    def can_participate(self) -> bool:
        """Подавать идеи и голосовать может только активный сотрудник."""
        return self.is_active and self.role is UserRole.EMPLOYEE
