"""Фоновые задачи в процессе приложения: один цикл, тик раз в `SCHEDULER_INTERVAL_S` и сразу при
старте (CLAUDE.md §8.4).

Корректность держат условные UPDATE и уникальные ключи в задачах; advisory lock тика лишь
экономит работу при втором процессе (например, локальный запуск рядом с контейнером).
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.core.logging import get_logger

# Отличается от ключа singleton-блокировки (`core/singleton.py`): это блокировка одного тика.
TICK_LOCK_KEY: Final = 0x4944454154

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """Именованная задача тика. Имя попадает в лог; сама задача идемпотентна."""

    name: str
    run: Callable[[], Awaitable[None]]


class Scheduler:
    def __init__(self, database: Database, jobs: Sequence[ScheduledJob], interval_s: float) -> None:
        self._database = database
        self._jobs = tuple(jobs)
        self._interval_s = interval_s
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def run_tick(self) -> bool:
        """Один тик: задачи по очереди под `pg_try_advisory_xact_lock`.

        Возвращает `False`, если тик занят другим процессом (пропуск). Ошибка одной задачи
        логируется и не мешает остальным и следующим тикам. Блокировка держится транзакцией
        тика, поэтому снимается сама при любом исходе, в том числе при обрыве соединения.
        """

        async def work(session: AsyncSession) -> bool:
            # Эта транзакция только держит блокировку, пока задачи работают на своих соединениях;
            # без отключения таймаута сервер оборвал бы её как «простаивающую» через 30 с.
            await session.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))
            acquired = await session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": TICK_LOCK_KEY}
            )
            if not acquired:
                return False
            for job in self._jobs:
                try:
                    await job.run()
                except Exception as error:  # noqa: BLE001 — единственное место, где это нужно
                    _log.error("job_failed", job=job.name, error_type=type(error).__name__)
            return True

        return await self._database.run_in_transaction(work)

    async def _run_forever(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.run_tick()
            except Exception as error:  # noqa: BLE001 — недоступная БД не должна ронять цикл
                _log.error("tick_failed", error_type=type(error).__name__)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval_s)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run_forever(), name="scheduler")

    async def stop(self, grace_s: float = 10.0) -> None:
        """Остановиться между тиками; текущему тику даётся `grace_s` секунд (§11.4).

        Не успел — тик отменяется, транзакция откатывается. Письма, взятые в отправку, вернутся
        в очередь по истечении аренды (доставка at-least-once), итоги и отметки не потеряются.
        """
        self._stopping.set()
        task, self._task = self._task, None
        if task is None:
            return
        _done, pending = await asyncio.wait({task}, timeout=grace_s)
        if pending:
            _log.warning("tick_cancelled_on_shutdown")
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
