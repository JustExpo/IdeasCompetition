"""Вход, выход и определение действующего лица по сессии (CLAUDE.md §9.1)."""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import dao
from app.auth.exception import InvalidCredentialsError
from app.auth.model import Actor
from app.auth.service.passwords import PasswordService
from app.common.model import PASSWORD_MAX_LENGTH, normalize_password
from app.core.clock import Clock
from app.core.db import Database
from app.core.logging import get_logger
from app.user import service as user_service
from app.user.model import User

SESSION_LIFETIME: Final = timedelta(days=7)  # абсолютный срок, без продления

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Результат входа: токен для cookie и пользователь для ответа."""

    token: str = field(repr=False)
    expires_at: datetime
    user: User


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> bytes:
    """SHA-256 достаточно: токен случайный (256 бит), подбирать по словарю нечего."""
    return hashlib.sha256(token.encode("utf-8")).digest()


async def log_in(
    database: Database,
    passwords: PasswordService,
    clock: Clock,
    *,
    email: str,
    password: str,
) -> IssuedSession:
    """Проверить e-mail и пароль и выдать новую сессию.

    Неизвестный адрес, неверный пароль, неактивный пользователь и слишком длинный пароль
    дают одну и ту же ошибку. Хэширование идёт вне транзакции, чтобы не держать соединение
    пула на время вычисления.
    """
    normalized = normalize_password(password)
    if len(normalized) > PASSWORD_MAX_LENGTH:
        raise InvalidCredentialsError("Неверный e-mail или пароль.")

    credentials = await database.run_in_transaction(
        lambda session: user_service.find_credentials(session, email)
    )
    if credentials is None or not credentials.user.is_active:
        await passwords.verify_unknown_account(normalized)
        raise InvalidCredentialsError("Неверный e-mail или пароль.")
    if not await passwords.verify_password(credentials.password_hash, normalized):
        raise InvalidCredentialsError("Неверный e-mail или пароль.")

    upgraded_hash = (
        await passwords.hash_password(normalized)
        if passwords.needs_rehash(credentials.password_hash)
        else None
    )
    token = generate_session_token()
    user_id = credentials.user.id

    async def issue(session: AsyncSession) -> IssuedSession:
        now = clock.now()  # после проверки пароля: срок отсчитывается от момента выдачи
        if upgraded_hash is not None:
            await user_service.replace_password_hash(session, user_id, upgraded_hash)
        user = await user_service.get_user(session, user_id)
        if user is None or not user.is_active:  # деактивирован, пока считался хэш
            raise InvalidCredentialsError("Неверный e-mail или пароль.")
        expires_at = now + SESSION_LIFETIME
        await dao.insert_session(
            session,
            token_hash=hash_session_token(token),
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
        )
        return IssuedSession(token=token, expires_at=expires_at, user=user)

    issued = await database.run_in_transaction(issue)
    _log.info("login_succeeded", user_id=int(user_id))
    return issued


async def resolve_actor(database: Database, clock: Clock, token: str) -> Actor | None:
    """Действующее лицо по токену; `None` — сессии нет, истекла, отозвана или пользователь отключён.

    Роль и `is_active` читаются из БД на каждый запрос и не кэшируются: смена прав
    действует со следующего запроса.
    """

    async def work(session: AsyncSession) -> Actor | None:
        now = clock.now()
        found = await dao.select_active_session(session, hash_session_token(token), now)
        if found is None:
            return None
        user = await user_service.get_user(session, found.user_id)
        if user is None or not user.is_active:
            return None
        return Actor(user_id=user.id, role=user.role)

    return await database.run_in_transaction(work)


async def log_out(database: Database, clock: Clock, token: str) -> None:
    """Отозвать сессию по токену; повторный выход безопасен."""

    async def work(session: AsyncSession) -> None:
        await dao.revoke_session(session, hash_session_token(token), clock.now())

    await database.run_in_transaction(work)


async def get_current_user(database: Database, actor: Actor) -> User:
    """Профиль действующего лица (для `GET /api/auth/me`)."""
    user = await database.run_in_transaction(
        lambda session: user_service.get_user(session, actor.user_id)
    )
    if user is None:  # пользователь исчез между проверкой сессии и чтением
        raise InvalidCredentialsError("Сессия недействительна.")
    return user
