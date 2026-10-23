"""Сценарии над учётными записями. Вызывающий открывает транзакцию (`run_in_transaction`)."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import UserId
from app.user import dao
from app.user.exception import EmailTakenError
from app.user.model import EnsuredUser, User, UserCredentials, UserRole, normalize_email


async def ensure_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    password_hash: str,
    role: UserRole,
    now: datetime,
) -> EnsuredUser:
    """Создать учётную запись, если адреса ещё нет; существующую не меняет (идемпотентно).

    Пароль и роль существующей записи не перезаписываются: повторный запуск не должен
    сбрасывать пароль, который организатор уже сменил, и не повышает сотрудника до организатора.
    """
    address = normalize_email(email)
    created = await dao.insert_user_if_absent(
        session, email=address, name=name, password_hash=password_hash, role=role, created_at=now
    )
    credentials = await dao.select_credentials_by_email(session, address)
    if credentials is None:  # недостижимо: запись либо вставлена, либо уже была
        raise RuntimeError("учётная запись не найдена после вставки")
    return EnsuredUser(credentials.user, created)


async def register_employee(
    session: AsyncSession, *, email: str, name: str, password_hash: str, now: datetime
) -> User:
    """Создать сотрудника; занятый адрес (в любом регистре) — `EmailTakenError`."""
    created = await dao.insert_user_if_absent(
        session,
        email=email,
        name=name,
        password_hash=password_hash,
        role=UserRole.EMPLOYEE,
        created_at=now,
    )
    if not created:
        raise EmailTakenError("Этот адрес уже зарегистрирован.")
    credentials = await dao.select_credentials_by_email(session, email)
    if credentials is None:  # недостижимо: запись только что вставлена в этой транзакции
        raise RuntimeError("учётная запись не найдена после вставки")
    return credentials.user


async def find_credentials(session: AsyncSession, email: str) -> UserCredentials | None:
    return await dao.select_credentials_by_email(session, normalize_email(email))


async def get_user(session: AsyncSession, user_id: UserId) -> User | None:
    return await dao.select_user_by_id(session, user_id)


async def get_user_names(session: AsyncSession, user_ids: Collection[UserId]) -> dict[UserId, str]:
    """Только имена, без e-mail: ими подписывают авторов идей после финала."""
    return await dao.select_user_names(session, user_ids)


async def replace_password_hash(session: AsyncSession, user_id: UserId, password_hash: str) -> None:
    await dao.update_password_hash(session, user_id, password_hash)


async def get_users(session: AsyncSession, user_ids: Collection[UserId]) -> dict[UserId, User]:
    """Учётные записи целиком (с e-mail): только для постановки писем, наружу не отдаются."""
    return await dao.select_users_by_ids(session, user_ids)


async def list_active_employees(session: AsyncSession) -> list[User]:
    return await dao.select_active_employees(session)
