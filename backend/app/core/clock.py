"""Единственное место, где приложение читает системное время (CLAUDE.md §4.3, Р4).

Остальной код получает время через `Clock` или аргументом `now`: так границы дедлайнов
проверяются в тестах без ожидания, а запись в транзакции читает время после блокировок.
"""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Источник текущего момента; всегда возвращает время с часовым поясом UTC."""

    def now(self) -> datetime: ...


class SystemClock:
    """Часы приложения: реальное время в UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)
