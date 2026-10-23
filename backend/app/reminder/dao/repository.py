"""Запросы к таблице напоминаний. Транзакцией управляет service."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId, UserId
from app.contest.model import ContestRound
from app.reminder.dao.tables import ReminderRow


async def insert_reminders_if_absent(
    session: AsyncSession,
    contest_id: ContestId,
    contest_round: ContestRound,
    user_ids: Collection[UserId],
    now: datetime,
) -> list[UserId]:
    """Отметить напоминания; вернуть тех, кому отметка поставлена именно сейчас.

    Два параллельных тика получат непересекающиеся ответы: письмо ставит тот, чья вставка прошла.
    """
    if not user_ids:
        return []
    statement = (
        pg_insert(ReminderRow)
        .values(
            [
                {
                    "contest_id": contest_id,
                    "round": contest_round.value,
                    "user_id": user_id,
                    "created_at": now,
                }
                for user_id in user_ids
            ]
        )
        .on_conflict_do_nothing(index_elements=["contest_id", "round", "user_id"])
        .returning(ReminderRow.user_id)
    )
    return [UserId(value) for value in (await session.execute(statement)).scalars()]
