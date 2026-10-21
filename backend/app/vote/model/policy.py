"""Кто и когда голосует и отзывает голос (CLAUDE.md §7.2, §9.2).

Видимость идеи (404) проверяет сервис через `idea.model.can_view_idea` до этих функций: так
ответ не раскрывает чужую идею. Здесь порядок: личность (401) → роль (403) → своя идея (403) →
фаза (409).
"""

from app.common.exception import OrganizerCannotParticipateError
from app.common.model import Actor, ensure_actor_active
from app.contest.model import ContestPhase, can_vote_in_contest
from app.idea.model import Idea
from app.vote.exception import OwnIdeaVoteError, VotingClosedError


def can_vote(actor: Actor, idea: Idea, phase: ContestPhase) -> bool:
    return can_vote_in_contest(actor, phase) and not idea.is_authored_by(actor.user_id)


def can_withdraw_vote(actor: Actor, phase: ContestPhase) -> bool:
    """Отозвать голос можно в тех же условиях, что и отдать его (П6)."""
    return can_vote_in_contest(actor, phase)


def ensure_can_vote(actor: Actor, idea: Idea, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if actor.is_organizer:
        raise OrganizerCannotParticipateError("Организатор не голосует.")
    if idea.is_authored_by(actor.user_id):
        raise OwnIdeaVoteError("За свою идею голосовать нельзя.")
    if not can_vote(actor, idea, phase):
        raise VotingClosedError("Голосование закрыто.")


def ensure_can_withdraw_vote(actor: Actor, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if actor.is_organizer:
        raise OrganizerCannotParticipateError("Организатор не голосует.")
    if not can_withdraw_vote(actor, phase):
        raise VotingClosedError("Голосование закрыто.")
