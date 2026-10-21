"""Роль и действующее лицо запроса — общие для политик всех модулей (CLAUDE.md §9.2)."""

from dataclasses import dataclass
from enum import StrEnum

from app.common.exception import NotAuthenticatedError
from app.common.model.types import UserId


class UserRole(StrEnum):
    """Роль определяет, что пользователь может делать в конкурсе."""

    EMPLOYEE = "employee"  # подаёт идеи и голосует
    ORGANIZER = "organizer"  # создаёт конкурсы и видит экран организатора, сам не участвует


@dataclass(frozen=True, slots=True)
class Actor:
    """Кто выполняет запрос. Роль читается из БД на каждый запрос и не кэшируется.

    Отключённому пользователю сессия не выдаётся (`resolve_actor` возвращает `None`), поэтому
    `is_active=False` в норме не встречается; политики всё равно отказывают ему: вторая преграда.
    """

    user_id: UserId
    role: UserRole
    is_active: bool = True

    @property
    def is_organizer(self) -> bool:
        return self.role is UserRole.ORGANIZER

    @property
    def is_employee(self) -> bool:
        return self.role is UserRole.EMPLOYEE


def ensure_actor_active(actor: Actor) -> None:
    """Отключённый пользователь — как будто сессии нет (401)."""
    if not actor.is_active:
        raise NotAuthenticatedError("Учётная запись отключена.")
