"""Базовая ревизия: пустая схема, от которой растут миграции задач IC-007 и далее.

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Таблиц нет: ревизия нужна, чтобы у приложения была «голова» для проверки схемы."""


def downgrade() -> None:
    """Откатывать нечего."""
