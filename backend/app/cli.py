"""Команды оператора и разработчика: `python -m app.cli create-organizer | export-openapi`."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.auth.service import PasswordService, ensure_organizer
from app.core.clock import SystemClock
from app.core.config import Settings, load_settings
from app.core.db import Database
from app.core.logging import configure_logging
from app.main import create_app

# Значения нужны только для сборки приложения: БД не подключается, секретов здесь нет.
_OPENAPI_SETTINGS: dict[str, str] = {
    "app_env": "dev",
    "database_url": "postgresql+asyncpg://openapi:openapi@127.0.0.1:1/openapi",
    "organizer_email": "organizer@example.com",
    "organizer_password": "openapi-export-only-password",
    "organizer_name": "Организатор",
    "allowed_email_domains": "example.com",
    "public_base_url": "http://127.0.0.1:8000",
    "smtp_host": "127.0.0.1",
    "smtp_port": "1025",
    "mail_from": "ideas@example.com",
}


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


def build_openapi_document() -> dict[str, Any]:
    """OpenAPI-контракт (CLAUDE.md §8.1) без БД, сети и окружения: `create_app` ничего не
    подключает до запуска lifespan, а `model_validate` не читает переменные окружения."""
    settings = Settings.model_validate(_OPENAPI_SETTINGS)
    document: dict[str, Any] = create_app(settings).openapi()
    return document


def render_openapi(document: dict[str, Any]) -> str:
    """Стабильный текст: ключи отсортированы, чтобы `git diff` показывал только смысловые правки."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def export_openapi(output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi(build_openapi_document()), encoding="utf-8")
    return f"контракт записан: {output}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "create-organizer", help="создать организатора из ORGANIZER_* (идемпотентно)"
    )
    export = commands.add_parser("export-openapi", help="записать OpenAPI-контракт (без БД)")
    export.add_argument("--output", type=Path, required=True, help="путь к openapi.json")
    args = parser.parse_args(argv)
    if args.command == "export-openapi":
        sys.stdout.write(export_openapi(args.output) + "\n")
    else:
        sys.stdout.write(asyncio.run(create_organizer()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
