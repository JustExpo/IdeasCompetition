"""Окружение Alembic: асинхронный движок, транзакция на каждую миграцию (CLAUDE.md §7.4)."""

import asyncio
import importlib
import os
from pathlib import Path

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.db import Base

config = context.config

# Таблицы объявляются в dao каждого модуля; импорт здесь регистрирует их в Base.metadata,
# чтобы `alembic check` видел расхождение моделей и схемы.
for module in ("user", "auth", "contest", "idea", "vote", "result", "reminder", "notification"):
    if (Path(__file__).parents[1] / "app" / module / "dao").is_dir():
        importlib.import_module(f"app.{module}.dao")

target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    # Миграция не должна ждать чужую блокировку дольше 5 с (иначе простой при выкладке).
    connection.execute(text("SET lock_timeout = '5s'"))
    connection.commit()  # закрыть автоначатую транзакцию: дальше по транзакции на миграцию
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
    else:
        asyncio.run(run_async_migrations())


run_migrations_online()
