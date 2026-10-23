"""Факт отправки напоминания: одно на (конкурс, раунд, сотрудник) — П9."""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.common.model import ContestId, UserId, require_aware
from app.contest.model import ContestRound

REMINDER_LEAD_TIME = timedelta(hours=24)


def reminder_window_contains(deadline: datetime, now: datetime) -> bool:
    """Окно напоминания: `deadline − 24h ≤ now < deadline`."""
    require_aware(deadline, "deadline")
    require_aware(now, "now")
    return deadline - REMINDER_LEAD_TIME <= now < deadline


@dataclass(frozen=True, slots=True)
class Reminder:
    contest_id: ContestId
    round: ContestRound
    user_id: UserId
    created_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")


def select_reminder_recipients(
    employees: Iterable[UserId], participants: Collection[UserId]
) -> tuple[UserId, ...]:
    """Активные сотрудники, которые ещё не участвовали в раунде (по текущему состоянию, П9).

    Организатор и отключённые в `employees` не входят: фильтр делает вызывающий запрос.
    """
    taken = set(participants)
    return tuple(sorted({user_id for user_id in employees if user_id not in taken}))
