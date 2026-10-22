"""Кому видны итоги и авторы (CLAUDE.md §9.2, П8)."""

from app.common.model import Actor, ensure_actor_active
from app.contest.model import ContestPhase, can_view_authors, can_view_results
from app.result.exception import ResultsNotPublishedError

# Правило раскрытия авторов живёт в contest.model (его читает и список идей); здесь — реэкспорт.
__all__ = ["can_view_authors", "ensure_can_view_results"]


def ensure_can_view_results(actor: Actor, phase: ContestPhase) -> None:
    ensure_actor_active(actor)
    if not can_view_results(actor, phase):
        raise ResultsNotPublishedError("Итоги будут доступны после закрытия голосования.")
