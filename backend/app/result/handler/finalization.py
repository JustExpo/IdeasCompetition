"""Тик планировщика: финализация конкурсов с закрытым голосованием."""

from app.core.clock import Clock
from app.core.db import Database
from app.result.service import finalize_due_contests


async def run_finalization(database: Database, clock: Clock, *, public_base_url: str) -> None:
    await finalize_due_contests(database, clock, public_base_url=public_base_url)
