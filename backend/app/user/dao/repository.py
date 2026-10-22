"""Запросы к таблице пользователей. Транзакцией управляет service."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import UserId
from app.user.dao.tables import UserRow
from app.user.model import User, UserCredentials, UserRole


def _to_user(row: UserRow) -> User:
    return User(
        id=UserId(row.id),
        email=row.email,
        name=row.name,
        role=UserRole(row.role),
        is_active=row.is_active,
        created_at=row.created_at,
    )


async def insert_user_if_absent(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    password_hash: str,
    role: UserRole,
    created_at: datetime,
) -> bool:
    """Вставить учётную запись; `False`, если адрес (без учёта регистра) уже занят."""
    statement = (
        pg_insert(UserRow)
        .values(
            email=email,
            name=name,
            password_hash=password_hash,
            role=role.value,
            created_at=created_at,
        )
        .on_conflict_do_nothing()
        .returning(UserRow.id)
    )
    return (await session.execute(statement)).scalar_one_or_none() is not None


async def select_credentials_by_email(session: AsyncSession, email: str) -> UserCredentials | None:
    row = (
        await session.execute(select(UserRow).where(func.lower(UserRow.email) == email))
    ).scalar_one_or_none()
    return None if row is None else UserCredentials(_to_user(row), row.password_hash)


async def select_user_by_id(session: AsyncSession, user_id: UserId) -> User | None:
    row = await session.get(UserRow, user_id)
    return None if row is None else _to_user(row)


async def select_user_names(
    session: AsyncSession, user_ids: Collection[UserId]
) -> dict[UserId, str]:
    if not user_ids:
        return {}
    rows = await session.execute(select(UserRow.id, UserRow.name).where(UserRow.id.in_(user_ids)))
    return {UserId(user_id): name for user_id, name in rows}


async def update_password_hash(session: AsyncSession, user_id: UserId, password_hash: str) -> None:
    await session.execute(
        update(UserRow).where(UserRow.id == user_id).values(password_hash=password_hash)
    )
