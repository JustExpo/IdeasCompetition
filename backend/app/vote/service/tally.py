"""Подсчёт голосов для итогов: тонкие обёртки над dao, чтобы `result` не импортировал чужой dao."""

from collections.abc import Collection

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import IdeaId, UserId
from app.vote import dao


async def count_votes_by_idea(
    session: AsyncSession, idea_ids: Collection[IdeaId]
) -> dict[IdeaId, int]:
    return await dao.count_votes_by_idea(session, idea_ids)


async def count_voters(session: AsyncSession, idea_ids: Collection[IdeaId]) -> int:
    return await dao.count_voters(session, idea_ids)


async def list_voter_ids(session: AsyncSession, idea_ids: Collection[IdeaId]) -> frozenset[UserId]:
    return await dao.select_voter_ids(session, idea_ids)
