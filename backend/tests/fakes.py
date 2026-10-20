"""Подставные реализации для тестов: управляемые часы."""

from datetime import datetime, timedelta

from app.common.model import require_aware


class FrozenClock:
    """Часы, которые стоят на месте, пока тест не сдвинет их (реализует `app.core.clock.Clock`)."""

    def __init__(self, start: datetime) -> None:
        require_aware(start, "start")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        require_aware(moment, "moment")
        self._now = moment

    def advance(self, delta: timedelta) -> None:
        self._now += delta
