"""Доступ к PostgreSQL: пул, транзакции с повтором, проверка схемы (CLAUDE.md §7.2–§7.4).

Все записи идут через `Database.run_in_transaction`; `commit()` вне этого модуля запрещён.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, text
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.common.exception import ServiceUnavailableError
from app.core.logging import get_logger

T = TypeVar("T")

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MAX_DEADLOCK_RETRIES = 3
HEALTH_TIMEOUT_S = 1.0

# Соглашение об именах нужно, чтобы dao переводил IntegrityError в доменную ошибку
# по имени ограничения (CLAUDE.md §4.2), а Alembic давал стабильные имена.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Сбои, при которых запрос стоит повторить позже: связь, остановка сервера,
# таймаут блокировки и запроса (SQLSTATE по документации PostgreSQL).
_UNAVAILABLE_SQLSTATES = frozenset({"57P01", "57P02", "57P03", "55P03", "57014"})
_RETRYABLE_SQLSTATES = frozenset({"40P01", "40001"})  # дедлок, сбой сериализации

_log = get_logger(__name__)
_jitter = random.SystemRandom()


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class SchemaMismatchError(RuntimeError):
    """Ревизия схемы БД не совпадает с той, что знает приложение."""


class DatabaseNotReadyError(RuntimeError):
    """БД не стала доступной за отведённое время при старте."""


def _sqlstate(error: sa_exc.DBAPIError) -> str | None:
    state = getattr(error.orig, "sqlstate", None)
    return state if isinstance(state, str) else None


def is_retryable_conflict(error: BaseException) -> bool:
    return isinstance(error, sa_exc.DBAPIError) and _sqlstate(error) in _RETRYABLE_SQLSTATES


def is_database_unavailable(error: BaseException) -> bool:
    if isinstance(error, OSError | TimeoutError | sa_exc.TimeoutError | sa_exc.InterfaceError):
        return True
    if isinstance(error, sa_exc.DBAPIError):
        state = _sqlstate(error)
        return state is not None and (state.startswith("08") or state in _UNAVAILABLE_SQLSTATES)
    return False


def expected_schema_revision() -> str:
    """Единственная «голова» миграций, которую знает этот код."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise SchemaMismatchError("В migrations/versions нет ни одной ревизии.")
    return head


def describe_schema_mismatch(current: str | None, expected: str) -> str | None:
    """Сообщение о несовпадении ревизий или `None`, если схема подходит."""
    if current == expected:
        return None
    if current is None:
        return f"БД без миграций, приложению нужна {expected}: выполните `alembic upgrade head`."
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    known = {rev.revision for rev in ScriptDirectory.from_config(config).walk_revisions()}
    if current not in known:
        return f"БД на ревизии {current}, приложению известна {expected}."
    return (
        f"БД на ревизии {current}, приложению нужна {expected}: выполните `alembic upgrade head`."
    )


class Database:
    """Пул соединений и транзакции. Создание не подключается к БД."""

    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_size=10,
            max_overflow=5,
            pool_timeout=5,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={
                "timeout": 5,
                "server_settings": {
                    "statement_timeout": "5000",
                    "lock_timeout": "2000",
                    "idle_in_transaction_session_timeout": "30000",
                    "application_name": "ideas-app",
                    "timezone": "UTC",
                },
            },
        )
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def run_in_transaction(self, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
        """Выполнить `work` в одной транзакции (READ COMMITTED) и закоммитить.

        При дедлоке или сбое сериализации транзакция откатывается и `work` вызывается заново
        целиком, до `MAX_DEADLOCK_RETRIES` повторов: поэтому `work` сам читает `Clock` после
        блокировок, а события и письма публикуются только после возврата отсюда (§7.2).
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                async with self._sessions() as session, session.begin():
                    return await work(session)
            except Exception as error:
                if is_retryable_conflict(error) and attempt <= MAX_DEADLOCK_RETRIES:
                    _log.warning("transaction_retry", attempt=attempt)
                    await asyncio.sleep(_jitter.uniform(0.01, 0.05) * attempt)
                    continue
                if is_database_unavailable(error):
                    _log.error("database_unavailable", error_type=type(error).__name__)
                    raise ServiceUnavailableError("База данных временно недоступна.") from error
                raise

    async def read_schema_revision(self) -> str | None:
        async with self.engine.connect() as connection:
            exists = await connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            if exists is None:
                return None
            revision: str | None = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            return revision

    async def ensure_schema_is_current(self) -> None:
        """Бросить `SchemaMismatchError`, если схема БД не на ревизии этого приложения."""
        message = describe_schema_mismatch(
            await self.read_schema_revision(), expected_schema_revision()
        )
        if message is not None:
            raise SchemaMismatchError(message)

    async def check_ready(self) -> None:
        """Готовность для `/api/health`: БД отвечает ≤ 1 с и схема подходит, иначе 503."""
        try:
            async with asyncio.timeout(HEALTH_TIMEOUT_S):
                await self.ensure_schema_is_current()
        except SchemaMismatchError as error:
            _log.error("schema_mismatch", detail=str(error))
            raise ServiceUnavailableError(
                "Схема базы данных не соответствует приложению."
            ) from error
        except Exception as error:
            if is_database_unavailable(error):
                raise ServiceUnavailableError("База данных недоступна.") from error
            raise

    async def wait_until_available(self, timeout_s: float = 60.0, interval_s: float = 1.0) -> None:
        """Дождаться ответа БД при старте (контейнер `db` может подниматься дольше `app`)."""
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                async with self.engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                return
            except Exception as error:
                if not is_database_unavailable(error):
                    raise
                if time.monotonic() + interval_s > deadline:
                    raise DatabaseNotReadyError(
                        f"БД не ответила за {timeout_s:g} с ({type(error).__name__})."
                    ) from error
                await asyncio.sleep(interval_s)

    async def dispose(self) -> None:
        await self.engine.dispose()
