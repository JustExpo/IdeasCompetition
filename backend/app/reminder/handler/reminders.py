"""Тик планировщика: напоминания за сутки до закрытия раунда."""

from app.core.clock import Clock
from app.core.db import Database
from app.reminder.service import enqueue_due_reminders


async def run_reminders(
    database: Database, clock: Clock, *, public_base_url: str, display_tz: str
) -> None:
    await enqueue_due_reminders(
        database, clock, public_base_url=public_base_url, display_tz=display_tz
    )
