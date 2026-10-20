"""Блокировка единственного экземпляра и запуск лаунчера на реальном PostgreSQL (§12.2, IC-006)."""

import asyncio
import contextlib
import os
import signal
import socket
from collections.abc import Callable

import asyncpg
import httpx
import pytest

from app.core import launcher
from app.core.config import Settings
from app.core.singleton import AnotherInstanceError, SingletonLock, to_asyncpg_dsn
from tests.unit.core.test_config import apply_env, base_env

# Свой ключ: тест не должен зависеть от того, что держит боевой ключ на общей БД.
TEST_KEY = 0x7E57_10CC


def make_lock(url: str, timeout_s: float = 0.3) -> SingletonLock:
    return SingletonLock(url, key=TEST_KEY, acquire_timeout_s=timeout_s, acquire_interval_s=0.1)


async def test_second_holder_is_refused_with_holder_details(database_url: str) -> None:
    first = make_lock(database_url)
    await first.acquire()
    try:
        with pytest.raises(AnotherInstanceError) as refused:
            await make_lock(database_url).acquire()
    finally:
        await first.release()
    message = str(refused.value)
    assert "Другой экземпляр приложения" in message
    assert "ideas-app-singleton" in message
    assert "pid" in message


async def test_release_frees_lock_for_next_holder(database_url: str) -> None:
    first = make_lock(database_url)
    await first.acquire()
    assert first.held
    assert await first.verify()
    await first.release()
    assert not first.held
    await first.release()  # повторный вызов безопасен

    second = make_lock(database_url)
    await second.acquire()
    await second.release()


async def test_acquire_waits_until_old_instance_releases(database_url: str) -> None:
    old = make_lock(database_url)
    await old.acquire()

    new = make_lock(database_url, timeout_s=5)
    waiting = asyncio.create_task(new.acquire())  # перезапуск: новый ждёт старого
    await asyncio.wait({waiting}, timeout=0.3)
    assert not waiting.done()
    await old.release()
    await asyncio.wait_for(waiting, timeout=5)
    assert new.held
    await new.release()


async def terminate_backend_of(database_url: str, application_name: str) -> None:
    connection = await asyncpg.connect(to_asyncpg_dsn(database_url))
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE application_name = $1 AND pid <> pg_backend_pid()",
            application_name,
        )
    finally:
        await connection.close()


async def test_verify_fails_after_connection_is_killed(database_url: str) -> None:
    lock = make_lock(database_url)
    await lock.acquire()
    await terminate_backend_of(database_url, "ideas-app-singleton")
    assert not await lock.verify()
    await lock.release()


async def test_monitor_reacquires_free_lock(database_url: str) -> None:
    lock = make_lock(database_url)
    await lock.acquire()
    lost = asyncio.Event()

    async def on_lost() -> None:
        lost.set()

    reacquired = asyncio.Event()
    monitor = asyncio.create_task(
        lock.monitor(on_lost, interval_s=0.1, on_reacquired=reacquired.set)
    )
    await terminate_backend_of(database_url, "ideas-app-singleton")
    await asyncio.wait_for(reacquired.wait(), timeout=5)
    assert await lock.verify()
    assert not lost.is_set()
    monitor.cancel()
    await lock.release()


async def test_monitor_reports_loss_when_lock_taken_by_other(database_url: str) -> None:
    lock = make_lock(database_url)
    await lock.acquire()
    lost = asyncio.Event()

    async def on_lost() -> None:
        lost.set()

    thief = make_lock(database_url)
    monitor = asyncio.create_task(lock.monitor(on_lost, interval_s=0.1))
    # Соединение гибнет, и блокировку тут же перехватывает другой процесс.
    await terminate_backend_of(database_url, "ideas-app-singleton")
    await thief.acquire()
    async with asyncio.timeout(5):
        await lost.wait()
    await monitor
    await thief.release()
    await lock.release()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def launcher_settings(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Settings:
    apply_env(monkeypatch, base_env(DATABASE_URL=database_url))
    return Settings()


async def wait_for_health(port: int, ready: Callable[[httpx.Response], bool]) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        async with asyncio.timeout(20):
            while True:
                try:
                    if ready(await client.get("/api/health")):
                        return
                except httpx.TransportError:
                    pass
                # Ожидание готовности порта; это опрос условия, а не фиксированная пауза.
                with contextlib.suppress(TimeoutError):
                    async with asyncio.timeout(0.1):
                        await asyncio.Event().wait()


async def test_launcher_serves_and_releases_lock_on_sigterm(
    monkeypatch: pytest.MonkeyPatch, launcher_settings: Settings, database_url: str
) -> None:
    port = free_port()
    monkeypatch.setattr(launcher, "PORT", port)
    monkeypatch.setattr(launcher, "HOST", "127.0.0.1")
    # Боевой ключ: именно его держит лаунчер.
    server = asyncio.create_task(launcher.serve(launcher_settings))
    try:
        await wait_for_health(port, lambda response: response.status_code == 200)

        # Пока сервер работает, второй экземпляр на той же БД получает отказ.
        with pytest.raises(AnotherInstanceError):
            await SingletonLock(
                database_url, acquire_timeout_s=0.3, acquire_interval_s=0.1
            ).acquire()

        os.kill(os.getpid(), signal.SIGTERM)
        assert await asyncio.wait_for(server, timeout=20) == 0
    finally:
        if not server.done():
            server.cancel()

    # После остановки блокировка свободна сразу: lifespan и finally всё освободили.
    successor = SingletonLock(database_url, acquire_timeout_s=1, acquire_interval_s=0.1)
    await successor.acquire()
    await successor.release()


async def test_launcher_refuses_to_start_when_lock_is_taken(
    monkeypatch: pytest.MonkeyPatch, launcher_settings: Settings, database_url: str
) -> None:
    monkeypatch.setattr("app.core.singleton.ACQUIRE_TIMEOUT_S", 0.3)
    monkeypatch.setattr(launcher, "PORT", free_port())
    holder = SingletonLock(database_url)
    await holder.acquire()
    try:
        # Лаунчер создаёт SingletonLock с таймаутом по умолчанию — подменяем его на короткий.
        monkeypatch.setattr(
            launcher,
            "SingletonLock",
            lambda url: SingletonLock(url, acquire_timeout_s=0.3, acquire_interval_s=0.1),
        )
        assert await launcher.serve(launcher_settings) == launcher.STARTUP_FAILURE_EXIT_CODE
    finally:
        await holder.release()
