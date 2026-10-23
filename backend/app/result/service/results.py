"""Итоги конкурса: одна функция подсчёта для API, экрана организатора и писем."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import Actor, ContestId, UserId, ensure_actor_active
from app.contest import service as contest_service
from app.contest.model import ContestPhase
from app.core.clock import Clock
from app.core.db import Database
from app.idea import service as idea_service
from app.idea.model import Idea
from app.result.model import (
    ContestResults,
    ContestResultsView,
    IdeaScore,
    RankedIdea,
    can_view_authors,
    ensure_can_view_results,
    rank_ideas,
)
from app.user import service as user_service
from app.vote import service as vote_service


@dataclass(frozen=True, slots=True)
class RankingSnapshot:
    """Идеи, голоса и места конкурса из одной транзакции: источник и для API, и для писем."""

    ideas: tuple[Idea, ...]
    ranking: tuple[RankedIdea, ...]
    voter_ids: frozenset[UserId]


async def rank_contest_ideas(session: AsyncSession, contest_id: ContestId) -> RankingSnapshot:
    ideas = await idea_service.list_all_contest_ideas(session, contest_id)
    idea_ids = [idea.id for idea in ideas]
    votes = await vote_service.count_votes_by_idea(session, idea_ids)
    voter_ids = await vote_service.list_voter_ids(session, idea_ids)
    ranking = rank_ideas(
        IdeaScore(
            idea_id=idea.id,
            title=idea.content.title,
            author_id=idea.author_id,
            submitted_at=idea.submitted_at,
            votes=votes.get(idea.id, 0),
        )
        for idea in ideas
    )
    return RankingSnapshot(ideas=ideas, ranking=ranking, voter_ids=voter_ids)


async def get_results(
    database: Database, clock: Clock, actor: Actor, contest_id: ContestId
) -> ContestResultsView:
    """Итоги и счётчики конкурса. Порядок проверок: 401 → 404 (конкурс) → 403 (до финала) (П8).

    Результаты не хранятся: считаются при каждом запросе по текущим голосам — нет счётчиков,
    а значит нет и потерянных обновлений (§7.1). Организатор до финала видит места без авторов.
    """

    async def work(session: AsyncSession) -> ContestResultsView:
        ensure_actor_active(actor)
        contest = await contest_service.find_contest(session, contest_id)
        now = clock.now()
        phase = contest.phase_at(now)
        ensure_can_view_results(actor, phase)
        snapshot = await rank_contest_ideas(session, contest_id)
        ideas = snapshot.ideas
        names = (
            await user_service.get_user_names(session, {idea.author_id for idea in ideas})
            if can_view_authors(actor, phase)
            else {}
        )
        return ContestResultsView(
            results=ContestResults(
                contest_id=contest_id,
                ranking=snapshot.ranking,
                is_final=phase is ContestPhase.FINISHED,
            ),
            ideas_count=len(ideas),
            voters_count=len(snapshot.voter_ids),
            author_names=names,
        )

    return await database.run_in_transaction(work)
