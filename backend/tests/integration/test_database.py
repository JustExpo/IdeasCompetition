"""Транзакции, повтор при дедлоке, недоступность БД, ревизия схемы (CLAUDE.md §7.2–§7.4)."""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import exc as sa_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exception import ServiceUnavailableError
from app.core.config import Settings
from app.core.db import (
    MAX_DEADLOCK_RETRIES,
    Database,
    DatabaseNotReadyError,
    SchemaMismatchError,
    expected_schema_revision,
)
from app.main import create_app
from tests.unit.core.test_config import apply_env, base_env

DEAD_URL = "postgresql+asyncpg://ideas:x@127.0.0.1:1/ideas_test"
ORIGIN = "http://127.0.0.1:8000"


class FakePostgresError(Exception):
    """Подмена ошибки драйвера: нужен лишь SQLSTATE, как у настоящего asyncpg."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


@pytest.fixture
async def dead_database() -> AsyncIterator[Database]:
    db = Database(DEAD_URL)
    yield db
    await db.dispose()


async def count_rows(database: Database) -> int:
    async with database.engine.connect() as connection:
        return int(await connection.scalar(text("SELECT count(*) FROM db_probe")) or 0)


@pytest.mark.commits
async def test_work_is_committed_on_success(database: Database, probe_table: str) -> None:
    async def work(session: AsyncSession) -> str:
        await session.execute(text("INSERT INTO db_probe VALUES (1, 10)"))
        return "done"

    assert await database.run_in_transaction(work) == "done"
    assert await count_rows(database) == 1


@pytest.mark.commits
async def test_work_is_rolled_back_when_it_raises(database: Database, probe_table: str) -> None:
    async def work(session: AsyncSession) -> None:
        await session.execute(text("INSERT INTO db_probe VALUES (1, 10)"))
        raise ValueError("не сохранять")

    with pytest.raises(ValueError, match="не сохранять"):
        await database.run_in_transaction(work)

    assert await count_rows(database) == 0


@pytest.mark.commits
async def test_deadlock_is_retried_and_both_transactions_succeed(
    database: Database, probe_table: str
) -> None:
    async with database.engine.begin() as connection:
        await connection.execute(text("INSERT INTO db_probe VALUES (1, 0), (2, 0)"))
    barrier = asyncio.Barrier(2)
    attempts = {"a": 0, "b": 0}

    async def worker(name: str, first: int, second: int) -> None:
        async def work(session: AsyncSession) -> None:
            attempts[name] += 1
            update = text("UPDATE db_probe SET value = value + 1 WHERE id = :id")
            await session.execute(update, {"id": first})
            if attempts[name] == 1:
                await barrier.wait()  # обе держат по строке и ждут чужую: дедлок
            await session.execute(update, {"id": second})

        await database.run_in_transaction(work)

    await asyncio.gather(worker("a", 1, 2), worker("b", 2, 1))

    assert sum(attempts.values()) >= 3  # жертва дедлока выполнила работу заново
    async with database.engine.connect() as connection:
        rows = (await connection.execute(text("SELECT value FROM db_probe ORDER BY id"))).all()
    assert [row.value for row in rows] == [2, 2]  # ни одно обновление не потеряно и не удвоено


@pytest.mark.commits
async def test_non_conflict_database_error_is_not_retried(
    database: Database, probe_table: str
) -> None:
    attempts = 0

    async def work(session: AsyncSession) -> None:
        nonlocal attempts
        attempts += 1
        await session.execute(text("INSERT INTO db_probe VALUES (1, 1), (1, 2)"))

    with pytest.raises(sa_exc.IntegrityError):
        await database.run_in_transaction(work)

    assert attempts == 1


async def test_retries_are_limited(database: Database) -> None:
    attempts = 0

    async def work(_session: AsyncSession) -> None:
        nonlocal attempts
        attempts += 1
        raise sa_exc.DBAPIError("UPDATE …", {}, FakePostgresError("40P01"))

    with pytest.raises(sa_exc.DBAPIError):
        await database.run_in_transaction(work)

    assert attempts == MAX_DEADLOCK_RETRIES + 1


async def test_serialization_failure_is_retried_too(database: Database) -> None:
    attempts = 0

    async def work(_session: AsyncSession) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sa_exc.DBAPIError("UPDATE …", {}, FakePostgresError("40001"))
        return "ok"

    assert await database.run_in_transaction(work) == "ok"
    assert attempts == 2


async def test_application_error_passes_through_untouched(database: Database) -> None:
    async def work(_session: AsyncSession) -> None:
        raise KeyError("domain")

    with pytest.raises(KeyError):
        await database.run_in_transaction(work)


async def test_unreachable_database_becomes_service_unavailable(dead_database: Database) -> None:
    async def work(session: AsyncSession) -> None:
        await session.execute(text("SELECT 1"))

    with pytest.raises(ServiceUnavailableError) as info:
        await dead_database.run_in_transaction(work)

    assert info.value.status == 503
    assert info.value.retry_after == 5


async def test_wait_until_available_returns_when_database_answers(database: Database) -> None:
    await database.wait_until_available(timeout_s=5, interval_s=0.1)


async def test_wait_until_available_gives_up_with_clear_error(dead_database: Database) -> None:
    with pytest.raises(DatabaseNotReadyError, match="не ответила"):
        await dead_database.wait_until_available(timeout_s=0.3, interval_s=0.1)


async def test_schema_is_on_the_revision_this_code_expects(database: Database) -> None:
    assert await database.read_schema_revision() == expected_schema_revision()
    await database.ensure_schema_is_current()
    await database.check_ready()


@pytest.mark.commits
async def test_unknown_revision_is_refused_with_both_revisions_in_message(
    database: Database,
) -> None:
    expected = expected_schema_revision()
    async with database.engine.begin() as connection:
        await connection.execute(text("UPDATE alembic_version SET version_num = '9999'"))
    try:
        with pytest.raises(SchemaMismatchError) as info:
            await database.ensure_schema_is_current()
        with pytest.raises(ServiceUnavailableError):
            await database.check_ready()
    finally:
        async with database.engine.begin() as connection:
            await connection.execute(
                text("UPDATE alembic_version SET version_num = :v"), {"v": expected}
            )

    assert str(info.value) == f"БД на ревизии 9999, приложению известна {expected}."


@pytest.mark.commits
async def test_database_without_migrations_is_refused(database: Database) -> None:
    async with database.engine.begin() as connection:
        await connection.execute(text("ALTER TABLE alembic_version RENAME TO alembic_version_off"))
    try:
        with pytest.raises(SchemaMismatchError, match="без миграций"):
            await database.ensure_schema_is_current()
    finally:
        async with database.engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE alembic_version_off RENAME TO alembic_version")
            )


async def test_session_fixture_does_not_leak_uncommitted_changes(
    session: AsyncSession, database: Database
) -> None:
    await session.execute(text("CREATE TABLE leak_probe (id int)"))
    await session.commit()  # внутри фикстуры это только savepoint

    async with database.engine.connect() as other:
        visible = await other.scalar(text("SELECT to_regclass('public.leak_probe')"))

    assert visible is None


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    apply_env(monkeypatch, base_env())
    return Settings()


async def get_health(database: Database, settings: Settings) -> httpx.Response:
    app = create_app(settings, database=database)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        return await client.get("/api/health")


async def test_health_is_ok_when_database_and_schema_are_fine(
    database: Database, settings: Settings
) -> None:
    response = await get_health(database, settings)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_is_503_with_retry_after_when_database_is_down(
    dead_database: Database, settings: Settings
) -> None:
    response = await get_health(dead_database, settings)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json()["code"] == "service_unavailable"


@pytest.mark.commits
async def test_health_is_503_when_schema_revision_is_unknown(
    database: Database, settings: Settings
) -> None:
    expected = expected_schema_revision()
    async with database.engine.begin() as connection:
        await connection.execute(text("UPDATE alembic_version SET version_num = '9999'"))
    try:
        response = await get_health(database, settings)
    finally:
        async with database.engine.begin() as connection:
            await connection.execute(
                text("UPDATE alembic_version SET version_num = :v"), {"v": expected}
            )

    assert response.status_code == 503
    assert "9999" not in response.text  # ревизии — во внутренний лог, не наружу


async def test_wrong_credentials_fail_fast_instead_of_waiting(database_url: str) -> None:
    wrong = Database(database_url.replace("ideas-test-only", "wrong-password"))
    try:
        with pytest.raises(sa_exc.DBAPIError):
            await wrong.wait_until_available(timeout_s=30, interval_s=1)  # не ждём 30 с
        with pytest.raises(sa_exc.DBAPIError):
            await wrong.check_ready()  # ошибка настройки — это 500, а не «подождите»
    finally:
        await wrong.dispose()
