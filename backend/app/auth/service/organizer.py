"""Организатор из окружения: создаётся при первом запуске, повторный запуск ничего не меняет."""

from app.auth.service.passwords import PasswordService
from app.common.model import normalize_password
from app.core.clock import Clock
from app.core.db import Database
from app.user import service as user_service
from app.user.exception import EmailTakenError
from app.user.model import EnsuredUser, UserRole, normalize_email


async def ensure_organizer(
    database: Database,
    passwords: PasswordService,
    clock: Clock,
    *,
    email: str,
    name: str,
    password: str,
) -> EnsuredUser:
    """Создать организатора, если его адреса ещё нет.

    Существующий организатор не меняется (пароль, сменённый оператором, не затирается).
    Если адрес занят сотрудником, роль не повышается: это ошибка конфигурации.
    """
    existing = await database.run_in_transaction(
        lambda session: user_service.find_credentials(session, email)
    )
    if existing is None:
        # Хэш считается только когда запись действительно создаётся: повторные старты быстрые.
        password_hash = await passwords.hash_password(normalize_password(password))
        ensured = await database.run_in_transaction(
            lambda session: user_service.ensure_user(
                session,
                email=normalize_email(email),
                name=name,
                password_hash=password_hash,
                role=UserRole.ORGANIZER,
                now=clock.now(),
            )
        )
    else:
        ensured = EnsuredUser(existing.user, created=False)
    if ensured.user.role is not UserRole.ORGANIZER:
        raise EmailTakenError("Адрес ORGANIZER_EMAIL уже принадлежит сотруднику.")
    return ensured
