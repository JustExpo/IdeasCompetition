"""Подключение integration-тестов к БД и защита от запуска на «живой» базе."""

import os

from sqlalchemy.engine import make_url

TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
# Порт 5433 — БД из compose на хосте (CLAUDE.md §11.1); пароль только для локальной тестовой БД.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://ideas:ideas-test-only@127.0.0.1:5433/ideas_test"  # gitleaks:allow
)
TEST_DATABASE_SUFFIX = "_test"


def ensure_test_database_url(url: str) -> str:
    """Вернуть `url`, если база тестовая; иначе отказаться: фикстуры стирают схему целиком."""
    name = make_url(url).database or ""
    if not name.endswith(TEST_DATABASE_SUFFIX):
        raise RuntimeError(
            f"Integration-тесты работают только с БД, имя которой оканчивается на "
            f"'{TEST_DATABASE_SUFFIX}'; получено '{name}'."
        )
    return url


def resolve_test_database_url() -> str:
    return ensure_test_database_url(
        os.environ.get(TEST_DATABASE_URL_ENV, DEFAULT_TEST_DATABASE_URL)
    )
