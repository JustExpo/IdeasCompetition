"""Кто и когда видит, правит и удаляет идею (CLAUDE.md §7.2, §9.2).

Порядок проверок во всех `ensure_*`: личность (401) → видимость и авторство (404, чтобы не
раскрывать чужую идею) → роль (403) → фаза (409). Отключённый пользователь — 401.
"""

from app.common.exception import OrganizerCannotParticipateError
from app.common.model import Actor, ContestId, UserRole, ensure_actor_active
from app.contest.model import ContestPhase, can_submit_ideas
from app.idea.exception import IdeaLockedError, IdeaNotFoundError, SubmissionClosedError
from app.idea.model.idea import Idea
from app.realtime.model import Audience, ContestEvent, EventType, PlannedEvent


def can_view_idea(actor: Actor, idea: Idea, phase: ContestPhase) -> bool:
    """Во время приёма идею видит только автор (П3); дальше — все вошедшие (без автора в ответе)."""
    if not actor.is_active:
        return False
    if phase is ContestPhase.SUBMISSION:
        return idea.is_authored_by(actor.user_id)
    return True


def can_edit_idea(actor: Actor, idea: Idea, phase: ContestPhase) -> bool:
    """Править может только автор и только до закрытия приёма (Ф2)."""
    return can_submit_ideas(actor, phase) and idea.is_authored_by(actor.user_id)


def can_delete_idea(actor: Actor, idea: Idea, phase: ContestPhase) -> bool:
    """Автор удаляет идею в приёме и в голосовании (П11); после финала идеи неизменны."""
    return (
        actor.is_active
        and actor.is_employee
        and idea.is_authored_by(actor.user_id)
        and phase is not ContestPhase.FINISHED
    )


def ensure_can_submit_idea(actor: Actor, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if actor.is_organizer:
        raise OrganizerCannotParticipateError("Организатор не подаёт идеи.")
    if not can_submit_ideas(actor, phase):
        raise SubmissionClosedError("Приём идей закрыт.")


def ensure_can_edit_idea(actor: Actor, idea: Idea, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if not idea.is_authored_by(actor.user_id):
        raise IdeaNotFoundError("Идея не найдена.")
    if actor.is_organizer:  # недостижимо при корректных данных (организатор не автор), но надёжнее
        raise OrganizerCannotParticipateError("Организатор не правит идеи.")
    if not can_edit_idea(actor, idea, phase):
        raise SubmissionClosedError("Приём идей закрыт.")


def ensure_can_delete_idea(actor: Actor, idea: Idea, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if not idea.is_authored_by(actor.user_id):
        raise IdeaNotFoundError("Идея не найдена.")
    if actor.is_organizer:
        raise OrganizerCannotParticipateError("Организатор не удаляет идеи.")
    if not can_delete_idea(actor, idea, phase):
        raise IdeaLockedError("Конкурс завершён, идею нельзя удалить.")


_ORGANIZERS = Audience(roles=frozenset({UserRole.ORGANIZER}))
_EVERYONE = Audience(roles=frozenset({UserRole.EMPLOYEE, UserRole.ORGANIZER}))


def plan_idea_events(
    contest_id: ContestId, idea: Idea, phase: ContestPhase, *, deleted: bool
) -> tuple[PlannedEvent, ...]:
    """Кому сообщить об изменении идеи (П3, П7, П11; CLAUDE.md §8.2).

    В приёме идея видна только автору, поэтому и сигнал получает только он; организатору уходит
    `results_changed` (у него меняются счётчики), но не сигнал об идее. Удаление в голосовании
    видят все: идея исчезает из общего списка вместе с голосами. После финала идеи неизменны.
    """
    if phase is ContestPhase.FINISHED:
        return ()
    results_changed = PlannedEvent(
        ContestEvent(EventType.RESULTS_CHANGED, contest_id=contest_id), _ORGANIZERS
    )
    if phase is ContestPhase.SUBMISSION:
        author_changed = PlannedEvent(
            ContestEvent(EventType.IDEAS_CHANGED, contest_id=contest_id),
            Audience(users=frozenset({idea.author_id})),
        )
        return (author_changed, results_changed)
    if deleted:
        deleted_for_all = PlannedEvent(
            ContestEvent(EventType.IDEA_DELETED, contest_id=contest_id, idea_id=idea.id),
            _EVERYONE,
        )
        return (deleted_for_all, results_changed)
    return ()
