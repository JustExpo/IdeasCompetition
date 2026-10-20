"""Блокировка единственного экземпляра приложения (CLAUDE.md §12.2, решение Р12).

Session advisory lock живёт на отдельном соединении asyncpg (не из пула): пока соединение
открыто, PostgreSQL не отдаст блокировку второму серверу, подключённому к той же БД. Так
отказывает не только второй контейнер, но и локальный uvicorn, IDE и `compose run`.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Final

import asyncpg

from app.core.logging import get_logger

# Произвольная константа проекта; ASCII-коды «IDEAS». Меняется только вместе с runbook.
ADVISORY_LOCK_KEY: Final = 0x4944454153
ACQUIRE_TIMEOUT_S: Final = 30.0
ACQUIRE_INTERVAL_S: Final = 1.0
MONITOR_INTERVAL_S: Final = 10.0
CONNECT_TIMEOUT_S: Final = 5.0

_log = get_logger(__name__)


class AnotherInstanceError(RuntimeError):
    """Блокировку держит другой процесс; сообщение безопасно показывать оператору."""


def to_asyncpg_dsn(sqlalchemy_url: str) -> str:
    """`postgresql+asyncpg://…` → `postgresql://…`: asyncpg не знает префикса диалекта."""
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def split_lock_key(key: int) -> tuple[int, int]:
    """Как PostgreSQL показывает bigint-ключ в `pg_locks`: старшие и младшие 32 бита."""
    return (key >> 32) & 0xFFFFFFFF, key & 0xFFFFFFFF


class SingletonLock:
    def __init__(
        self,
        dsn: str,
        *,
        key: int = ADVISORY_LOCK_KEY,
        acquire_timeout_s: float = ACQUIRE_TIMEOUT_S,
        acquire_interval_s: float = ACQUIRE_INTERVAL_S,
    ) -> None:
        self._dsn = to_asyncpg_dsn(dsn)
        self._key = key
        self._acquire_timeout_s = acquire_timeout_s
        self._acquire_interval_s = acquire_interval_s
        self._connection: asyncpg.Connection | None = None

    @property
    def held(self) -> bool:
        """Быстрая проверка без обращения к БД: соединение с блокировкой ещё открыто."""
        return self._connection is not None and not self._connection.is_closed()

    async def acquire(self) -> None:
        """Взять блокировку; при перезапуске ждём, пока старый экземпляр её отпустит."""
        deadline = time.monotonic() + self._acquire_timeout_s
        while True:
            if await self._try_acquire():
                _log.info("singleton_lock_acquired")
                return
            if time.monotonic() + self._acquire_interval_s > deadline:
                raise AnotherInstanceError(await self._describe_holder())
            await asyncio.sleep(self._acquire_interval_s)

    async def verify(self) -> bool:
        """Проверить в БД, что блокировка по-прежнему за этим соединением."""
        if not self.held or self._connection is None:
            return False
        high, low = split_lock_key(self._key)
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_S):
                return bool(
                    await self._connection.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                        "AND pid = pg_backend_pid() AND classid = $1 AND objid = $2 "
                        "AND objsubid = 1 AND granted)",
                        high,
                        low,
                    )
                )
        except (OSError, TimeoutError, asyncpg.PostgresError, asyncpg.InterfaceError):
            return False

    async def monitor(
        self,
        on_lost: Callable[[], Awaitable[None]],
        interval_s: float = MONITOR_INTERVAL_S,
        on_reacquired: Callable[[], None] | None = None,
    ) -> None:
        """Раз в `interval_s` проверять блокировку; потеряна и не взялась снова — `on_lost`.

        Короткий обрыв соединения с БД блокировку снимает, но если её никто не успел взять,
        она берётся заново (`on_reacquired`) и сервер продолжает работу.
        """
        while True:
            await asyncio.sleep(interval_s)
            if await self.verify():
                continue
            _log.warning("singleton_lock_lost")
            await self._close()
            if not await self._try_acquire():
                _log.error("singleton_lock_taken_by_other")
                await on_lost()
                return
            _log.info("singleton_lock_reacquired")
            if on_reacquired is not None:
                on_reacquired()

    async def release(self) -> None:
        """Закрытие соединения снимает session lock; повторный вызов безопасен."""
        await self._close()

    async def _try_acquire(self) -> bool:
        connection = await self._connect()
        if connection is None:
            return False
        if await connection.fetchval("SELECT pg_try_advisory_lock($1)", self._key):
            self._connection = connection
            return True
        await connection.close()
        return False

    async def _connect(self) -> asyncpg.Connection | None:
        try:
            return await asyncpg.connect(
                self._dsn,
                timeout=CONNECT_TIMEOUT_S,
                server_settings={"application_name": "ideas-app-singleton"},
            )
        except (OSError, TimeoutError, asyncpg.PostgresError, asyncpg.InterfaceError) as error:
            # БД может быть недоступна секунду при перезапуске: это тоже «пока не взяли».
            _log.warning("singleton_connect_failed", error_type=type(error).__name__)
            return None

    async def _close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None and not connection.is_closed():
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT_S):
                    await connection.close()
            except TimeoutError:
                connection.terminate()

    async def _describe_holder(self) -> str:
        """Кто держит блокировку: только служебные поля `pg_stat_activity`, без запросов."""
        text = "Другой экземпляр приложения уже подключён к этой БД."
        connection = await self._connect()
        if connection is None:
            return text
        high, low = split_lock_key(self._key)
        try:
            row = await connection.fetchrow(
                "SELECT a.pid, a.client_addr::text AS addr, a.application_name, a.backend_start "
                "FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE l.locktype = 'advisory' AND l.classid = $1 AND l.objid = $2 "
                "AND l.objsubid = 1 AND l.granted LIMIT 1",
                high,
                low,
            )
        except asyncpg.PostgresError:
            row = None
        finally:
            await connection.close()
        if row is None:
            return text
        return (
            f"{text} Держатель: pid {row['pid']}, адрес {row['addr'] or 'локальный сокет'}, "
            f"приложение {row['application_name']!r}, с {row['backend_start']:%Y-%m-%d %H:%M:%S}Z. "
            "Остановите его (`make down`) и повторите запуск."
        )
