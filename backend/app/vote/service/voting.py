"""Сценарии голосования: отдать и отозвать голос (CLAUDE.md §7.2)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import Actor, ContestId, IdeaId, ensure_actor_active
from app.contest import service as contest_service
from app.contest.model import ContestPhase
from app.core.clock import Clock
from app.core.db import Database
from app.idea import service as idea_service
from app.idea.exception import IdeaNotFoundError
from app.idea.model import Idea, can_view_idea
from app.realtime.service import NULL_EVENT_PUBLISHER, EventPublisher
from app.vote import dao
from app.vote.model import ensure_can_vote, ensure_can_withdraw_vote, plan_vote_events


async def _lock_visible_idea(
    session: AsyncSession, clock: Clock, actor: Actor, idea_id: IdeaId
) -> tuple[Idea, ContestPhase, ContestId]:
    """Заблокировать конкурс и идею и вернуть их вместе с фазой на момент после блокировок.

    Порядок contest → idea (Р6), `now` читается после блокировок (Р4): голос, принятый до
    дедлайна, финализация (`FOR UPDATE` конкурса) гарантированно увидит. Невидимая идея — 404,
    чтобы ответ не раскрывал существование чужой идеи (§7.2).
    """
    ensure_actor_active(actor)
    contest_id = await idea_service.find_idea_contest_id(session, idea_id)
    if contest_id is None:
        raise IdeaNotFoundError("Идея не найдена.")
    contest = await contest_service.lock_contest_for_share(session, contest_id)
    idea = await idea_service.lock_idea_for_share(session, idea_id)
    if idea is None:  # идею успели удалить, пока ждали конкурс
        raise IdeaNotFoundError("Идея не найдена.")
    phase = contest.phase_at(clock.now())
    if not can_view_idea(actor, idea, phase):
        raise IdeaNotFoundError("Идея не найдена.")
    return idea, phase, contest_id


def _publish_vote_events(events: EventPublisher, contest_id: ContestId, actor: Actor) -> None:
    """После commit: организатор пересчитывает цифры, другие вкладки голосующего — отметки."""
    for planned in plan_vote_events(contest_id, actor.user_id):
        events.publish(planned)


async def cast_vote(
    database: Database,
    clock: Clock,
    actor: Actor,
    idea_id: IdeaId,
    events: EventPublisher = NULL_EVENT_PUBLISHER,
) -> None:
    """Проголосовать за идею. Повторный голос и голос из второй вкладки — не ошибка (П5)."""

    async def work(session: AsyncSession) -> tuple[ContestId, bool]:
        idea, phase, contest_id = await _lock_visible_idea(session, clock, actor, idea_id)
        ensure_can_vote(actor, idea, phase)
        # Фаза уже проверена по часам после блокировок; здесь время нужно только для `created_at`.
        inserted = await dao.insert_vote_if_absent(session, idea.id, actor.user_id, clock.now())
        return contest_id, inserted

    contest_id, inserted = await database.run_in_transaction(work)
    if inserted:  # повтор ничего не изменил: сигнал не нужен
        _publish_vote_events(events, contest_id, actor)


async def withdraw_vote(
    database: Database,
    clock: Clock,
    actor: Actor,
    idea_id: IdeaId,
    events: EventPublisher = NULL_EVENT_PUBLISHER,
) -> None:
    """Отозвать голос до закрытия голосования. Отзыв несуществующего голоса — тоже 204 (П6)."""

    async def work(session: AsyncSession) -> tuple[ContestId, bool]:
        idea, phase, contest_id = await _lock_visible_idea(session, clock, actor, idea_id)
        ensure_can_withdraw_vote(actor, phase)
        return contest_id, await dao.delete_vote(session, idea.id, actor.user_id)

    contest_id, removed = await database.run_in_transaction(work)
    if removed:
        _publish_vote_events(events, contest_id, actor)
