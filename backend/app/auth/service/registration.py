"""Саморегистрация сотрудника с автоматическим входом (CLAUDE.md §9.1, Р11)."""

from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service.passwords import PasswordService
from app.auth.service.rate_limit import AttemptLimiter
from app.auth.service.sessions import IssuedSession, generate_session_token, open_session
from app.common.model import normalize_password
from app.core.clock import Clock
from app.core.db import Database
from app.core.logging import get_logger
from app.user import service as user_service
from app.user.model import ensure_registration_valid

_log = get_logger(__name__)


async def register_employee(
    database: Database,
    passwords: PasswordService,
    clock: Clock,
    limiter: AttemptLimiter,
    *,
    client_ip: str,
    allowed_domains: Iterable[str],
    email: str,
    name: str,
    password: str,
) -> IssuedSession:
    """Создать сотрудника и сразу выдать ему сессию.

    Каждая попытка (в том числе с ошибкой в данных) считается в лимите по IP. Данные
    проверяются до хэширования: Argon2 дорогой, и неверный запрос не должен занимать слот.
    """
    limiter.ensure_registration_allowed(client_ip)
    password = normalize_password(password)
    registration = ensure_registration_valid(
        email=email, name=name, password=password, allowed_domains=allowed_domains
    )
    password_hash = await passwords.hash_password(password)
    token = generate_session_token()

    async def create(session: AsyncSession) -> IssuedSession:
        now = clock.now()
        user = await user_service.register_employee(
            session,
            email=registration.email,
            name=registration.name,
            password_hash=password_hash,
            now=now,
        )
        return await open_session(session, user, token, now)

    issued = await database.run_in_transaction(create)
    _log.info("employee_registered", user_id=int(issued.user.id))
    return issued
