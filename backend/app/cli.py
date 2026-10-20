"""Команды оператора (CLAUDE.md §9.1): `python -m app.cli create-organizer`."""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from app.auth.service import PasswordService, ensure_organizer
from app.core.clock import SystemClock
from app.core.config import load_settings
from app.core.db import Database
from app.core.logging import configure_logging


async def create_organizer() -> str:
    """Создаёт организатора из окружения; повторный вызов ничего не меняет."""
    settings = load_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    database = Database(settings.database_url.get_secret_value())
    try:
        ensured = await ensure_organizer(
            database,
            PasswordService(),
            SystemClock(),
            email=settings.organizer_email,
            name=settings.organizer_name,
            password=settings.organizer_password.get_secret_value(),
        )
    finally:
        await database.dispose()
    return "организатор создан" if ensured.created else "организатор уже существует"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_subparsers(dest="command", required=True).add_parser(
        "create-organizer", help="создать организатора из ORGANIZER_* (идемпотентно)"
    )
    parser.parse_args(argv)
    sys.stdout.write(asyncio.run(create_organizer()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
