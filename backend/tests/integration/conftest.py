"""Фикстуры integration-тестов: реальный PostgreSQL, схема из миграций.

Изоляция: обычные тесты работают в транзакции с откатом (`session`). Тесты, которым нужен
настоящий commit (гонки, повторы, блокировки), помечаются `@pytest.mark.commits`: после них
все таблицы приложения очищаются. Повтор транзакции внутри savepoint ведёт себя иначе, чем
настоящий, поэтому проверять его можно только в `commits`-тестах (спецификация IC-005).
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.db import Base, Database
from tests.integration.database import resolve_test_database_url

BACKEND_DIR = Path(__file__).parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Всё из tests/integration получает маркер integration: `pytest -m integration`."""
    here = Path(__file__).parent
    for item in items:
        if here in item.path.parents:
            item.add_marker(pytest.mark.integration)


async def _reset_schema(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    return resolve_test_database_url()


@pytest.fixture(scope="session", autouse=True)
def migrated_schema(database_url: str) -> Iterator[None]:
    """Один раз за прогон: пустая схема и `alembic upgrade head` — как при реальном запуске."""
    asyncio.run(_reset_schema(database_url))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
async def database(database_url: str) -> AsyncIterator[Database]:
    db = Database(database_url)
    yield db
    await db.dispose()


@pytest.fixture
async def session(database: Database) -> AsyncIterator[AsyncSession]:
    """Сессия в транзакции, которая откатывается; `commit()` внутри — лишь savepoint."""
    async with database.engine.connect() as connection:
        outer = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as test_session:
            yield test_session
        await outer.rollback()


async def truncate_all_tables(database_url: str) -> None:
    tables = [table.name for table in Base.metadata.sorted_tables]
    if not tables:
        return
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables_around_commits(
    request: pytest.FixtureRequest, database_url: str
) -> AsyncIterator[None]:
    # Очистка и до теста: другой тест (например, запуск лаунчера) мог оставить строки с
    # настоящим commit, а commits-тест рассчитывает на пустые таблицы и порядок id.
    commits = request.node.get_closest_marker("commits") is not None
    if commits:
        await truncate_all_tables(database_url)
    yield
    if commits:
        await truncate_all_tables(database_url)


@pytest.fixture
async def probe_table(database: Database) -> AsyncIterator[str]:
    """Служебная таблица для проверки блокировок: у предметных модулей таблиц ещё нет."""
    async with database.engine.begin() as connection:
        await connection.execute(
            text("CREATE TABLE db_probe (id int PRIMARY KEY, value int NOT NULL)")
        )
    yield "db_probe"
    async with database.engine.begin() as connection:
        await connection.execute(text("DROP TABLE IF EXISTS db_probe"))
