"""Кому видны итоги и авторы (CLAUDE.md §9.2, П8)."""

from app.common.model import Actor, ensure_actor_active
from app.contest.model import ContestPhase, can_view_results
from app.result.exception import ResultsNotPublishedError


def can_view_authors(actor: Actor, phase: ContestPhase) -> bool:
    """Авторы раскрываются всем после финала и никому до него — в том числе организатору."""
    return actor.is_active and phase is ContestPhase.FINISHED


def ensure_can_view_results(actor: Actor, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if not can_view_results(actor, phase):
        raise ResultsNotPublishedError("Итоги будут доступны после закрытия голосования.")
