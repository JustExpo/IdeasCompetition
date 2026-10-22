"""Список идей конкурса. Живёт в `vote`, потому что в фазе голосования к нему добавляется голос
текущего пользователя (`my_vote`, IC-013), а `idea` не должен читать чужие голоса (§4.2)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import Actor, ContestId
from app.core.clock import Clock
from app.core.db import Database
from app.idea import service as idea_service
from app.idea.model import IdeaListing


async def list_contest_ideas(
    database: Database, clock: Clock, actor: Actor, contest_id: ContestId
) -> IdeaListing:
    async def work(session: AsyncSession) -> IdeaListing:
        return await idea_service.list_contest_ideas(session, actor, contest_id, clock.now())

    return await database.run_in_transaction(work)
