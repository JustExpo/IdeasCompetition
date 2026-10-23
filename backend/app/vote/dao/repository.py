"""Запросы к таблице голосов. Транзакцией управляет service.

Идеи конкурса сюда приходят списком идентификаторов: `vote.dao` не читает таблицу чужого модуля.
"""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import IdeaId, UserId
from app.vote.dao.tables import VoteRow


async def insert_vote_if_absent(
    session: AsyncSession, idea_id: IdeaId, voter_id: UserId, now: datetime
) -> bool:
    """Отдать голос; `False`, если такой голос уже есть (повтор или вторая вкладка — не ошибка)."""
    statement = (
        pg_insert(VoteRow)
        .values(idea_id=idea_id, voter_id=voter_id, created_at=now)
        .on_conflict_do_nothing(index_elements=["idea_id", "voter_id"])
        .returning(VoteRow.idea_id)
    )
    return (await session.execute(statement)).first() is not None


async def delete_vote(session: AsyncSession, idea_id: IdeaId, voter_id: UserId) -> None:
    """Отозвать голос; отсутствие голоса — не ошибка (идемпотентность, П6)."""
    await session.execute(
        delete(VoteRow).where(VoteRow.idea_id == idea_id, VoteRow.voter_id == voter_id)
    )


async def select_voted_idea_ids(
    session: AsyncSession, voter_id: UserId, idea_ids: Collection[IdeaId]
) -> frozenset[IdeaId]:
    """Какие из `idea_ids` пользователь поддержал (отметка `my_vote`)."""
    if not idea_ids:
        return frozenset()
    rows = await session.scalars(
        select(VoteRow.idea_id).where(VoteRow.voter_id == voter_id, VoteRow.idea_id.in_(idea_ids))
    )
    return frozenset(IdeaId(value) for value in rows)


async def count_votes_by_idea(
    session: AsyncSession, idea_ids: Collection[IdeaId]
) -> dict[IdeaId, int]:
    """Голоса за каждую идею из `idea_ids`; идеи без голосов в словарь не попадают."""
    if not idea_ids:
        return {}
    rows = await session.execute(
        select(VoteRow.idea_id, func.count())
        .where(VoteRow.idea_id.in_(idea_ids))
        .group_by(VoteRow.idea_id)
    )
    return {IdeaId(idea_id): count for idea_id, count in rows}


async def count_voters(session: AsyncSession, idea_ids: Collection[IdeaId]) -> int:
    """Сколько разных людей сейчас голосуют за идеи из `idea_ids`."""
    if not idea_ids:
        return 0
    statement = select(func.count(func.distinct(VoteRow.voter_id))).where(
        VoteRow.idea_id.in_(idea_ids)
    )
    return int(await session.scalar(statement) or 0)
