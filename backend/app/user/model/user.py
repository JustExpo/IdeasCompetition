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


@dataclass(frozen=True, slots=True)
class UserCredentials:
    """Пользователь вместе с хэшем пароля — только для проверки при входе.

    Хэш скрыт из repr: даже хэш не должен попадать в логи.
    """

    user: User
    password_hash: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class EnsuredUser:
    """Результат идемпотентного создания: `created` ложно, если учётная запись уже была."""

    user: User
    created: bool


def normalize_email(email: str) -> str:
    """Единая форма адреса для поиска и уникальности: без пробелов по краям и в нижнем регистре."""
    return email.strip().lower()
