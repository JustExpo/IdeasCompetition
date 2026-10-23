"""Запросы к таблице конкурсов. Транзакцией управляет service."""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId, IdeaId, UserId
from app.contest.dao.tables import ContestRow
from app.contest.model import Contest, ContestRound, ContestSchedule


def _to_contest(row: ContestRow) -> Contest:
    return Contest(
        id=ContestId(row.id),
        topic=row.topic,
        description=row.description,
        schedule=ContestSchedule(row.submission_deadline, row.voting_deadline),
        created_by=UserId(row.created_by),
        created_at=row.created_at,
        finalized_at=row.finalized_at,
        winner_idea_id=None if row.winner_idea_id is None else IdeaId(row.winner_idea_id),
    )


async def insert_contest(
    session: AsyncSession,
    *,
    topic: str,
    description: str,
    schedule: ContestSchedule,
    created_by: UserId,
    created_at: datetime,
) -> Contest:
    row = ContestRow(
        topic=topic,
        description=description,
        submission_deadline=schedule.submission_deadline,
        voting_deadline=schedule.voting_deadline,
        created_by=created_by,
        created_at=created_at,
    )
    session.add(row)
    await session.flush()
    return _to_contest(row)


async def select_contest(
    session: AsyncSession,
    contest_id: ContestId,
    *,
    lock_for_share: bool = False,
    lock_for_update: bool = False,
) -> Contest | None:
    """`FOR SHARE` не даёт финализации (`FOR UPDATE`) закончиться посреди записи (Р6)."""
    statement = select(ContestRow).where(ContestRow.id == contest_id)
    if lock_for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    elif lock_for_share:
        # populate_existing: блокирующее чтение обязано вернуть актуальную строку, а не копию
        # из identity map сессии.
        statement = statement.with_for_update(read=True).execution_options(populate_existing=True)
    row = (await session.execute(statement)).scalar_one_or_none()
    return None if row is None else _to_contest(row)


async def select_contests_page(session: AsyncSession, *, limit: int, offset: int) -> list[Contest]:
    statement = (
        select(ContestRow)
        .order_by(ContestRow.voting_deadline.desc(), ContestRow.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_to_contest(row) for row in (await session.execute(statement)).scalars()]


async def count_contests(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(ContestRow)) or 0)


async def select_unfinalized_contest_ids(session: AsyncSession, now: datetime) -> list[ContestId]:
    """Конкурсы, у которых голосование закончилось, а итог ещё не зафиксирован."""
    statement = (
        select(ContestRow.id)
        .where(ContestRow.finalized_at.is_(None), ContestRow.voting_deadline <= now)
        .order_by(ContestRow.id)
    )
    return [ContestId(value) for value in await session.scalars(statement)]


async def update_contest_finalization(
    session: AsyncSession, contest_id: ContestId, *, finalized_at: datetime, winner: IdeaId | None
) -> bool:
    """Зафиксировать итог один раз; `False`, если его уже зафиксировал другой тик."""
    statement = (
        update(ContestRow)
        .where(ContestRow.id == contest_id, ContestRow.finalized_at.is_(None))
        .values(finalized_at=finalized_at, winner_idea_id=winner)
        .returning(ContestRow.id)
    )
    return (await session.execute(statement)).first() is not None


async def select_contests_with_deadline_between(
    session: AsyncSession, contest_round: ContestRound, start: datetime, end: datetime
) -> list[Contest]:
    """Конкурсы, дедлайн раунда которых лежит в `(start, end]` (окно напоминания, П9)."""
    column = (
        ContestRow.submission_deadline
        if contest_round is ContestRound.SUBMISSION
        else ContestRow.voting_deadline
    )
    statement = select(ContestRow).where(column > start, column <= end).order_by(ContestRow.id)
    return [_to_contest(row) for row in (await session.execute(statement)).scalars()]
