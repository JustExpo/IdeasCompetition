"""Запуск сервера в контейнере: блокировка → миграции → uvicorn (CLAUDE.md §7.4, §11.4, §12.2).

Блокировка берётся ДО миграций: иначе второй экземпляр (`compose run`, локальный uvicorn,
другой checkout) успел бы мигрировать общую БД под работающим `app`. Shell-entrypoint
удержать session lock на время работы сервера не может, поэтому запуск — на Python.
"""

import asyncio
import os
import signal
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Final

import uvicorn
from alembic import command
from alembic.config import Config
from starlette.datastructures import State

from app.core.config import Settings, load_settings
from app.core.db import Database, DatabaseNotReadyError, SchemaMismatchError
from app.core.logging import configure_logging, get_logger, shutdown_logging
from app.core.singleton import AnotherInstanceError, SingletonLock
from app.main import create_app

HOST: Final = "0.0.0.0"  # noqa: S104 — слушаем внутри контейнера; наружу порт публикует compose на 127.0.0.1
PORT: Final = 8000
GRACEFUL_SHUTDOWN_S: Final = 10
BACKEND_DIR: Final = Path(__file__).resolve().parents[2]
STARTUP_FAILURE_EXIT_CODE: Final = 1
HANDLED_SIGNALS: Final = (signal.SIGINT, signal.SIGTERM)

_log = get_logger(__name__)


class DrainingServer(uvicorn.Server):
    """uvicorn, который при SIGTERM/SIGINT сперва переводит `/api/health` в 503."""

    def __init__(self, config: uvicorn.Config, app_state: State) -> None:
        super().__init__(config)
        self._app_state = app_state

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        # Штатный uvicorn после остановки повторно посылает себе пойманный сигнал, и процесс
        # умирает по SIGTERM, не дойдя до `finally` лаунчера (снятие блокировки, dispose пула).
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        previous = {sig: signal.signal(sig, self.handle_exit) for sig in HANDLED_SIGNALS}
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        self._app_state.draining = True
        super().handle_exit(sig, frame)


def run_migrations(database_url: str) -> None:
    """`alembic upgrade head` в потоке: env.py запускает собственный event loop."""
    os.environ["DATABASE_URL"] = database_url
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")


async def serve(settings: Settings) -> int:
    url = settings.database_url.get_secret_value()
    database = Database(url)
    singleton = SingletonLock(url) if settings.hold_singleton_lock else None
    monitor: asyncio.Task[None] | None = None
    try:
        await database.wait_until_available()
        if singleton is not None:
            await singleton.acquire()
        await asyncio.to_thread(run_migrations, url)
        await database.ensure_schema_is_current()

        app = create_app(settings, database, singleton)
        server = DrainingServer(
            uvicorn.Config(
                app,
                host=HOST,
                port=PORT,
                workers=1,
                log_config=None,  # логи — через structlog, один формат
                access_log=False,  # журнал запросов пишет RequestContextMiddleware
                timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_S,
                server_header=False,
            ),
            app.state,
        )
        exit_code = 0

        async def stop_after_lock_loss() -> None:
            nonlocal exit_code
            exit_code = STARTUP_FAILURE_EXIT_CODE
            app.state.draining = True
            server.should_exit = True

        if singleton is not None:
            monitor = asyncio.create_task(singleton.monitor(stop_after_lock_loss))
        await server.serve()
        return exit_code
    except (AnotherInstanceError, SchemaMismatchError, DatabaseNotReadyError) as error:
        # Сообщения этих ошибок написаны для оператора и не содержат секретов.
        _log.error("startup_failed", reason=str(error))
        return STARTUP_FAILURE_EXIT_CODE
    finally:
        if monitor is not None:
            monitor.cancel()
        if singleton is not None:
            await singleton.release()
        await database.dispose()


def main() -> None:
    settings = load_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    try:
        code = asyncio.run(serve(settings))
    finally:
        shutdown_logging()
    sys.exit(code)


if __name__ == "__main__":
    main()
