"""Что можно делать в конкурсе в зависимости от роли и фазы (CLAUDE.md §9.2).

Чистые функции без I/O: фаза приходит готовой (`ContestSchedule.phase_at(now)`), поэтому границы
дедлайнов проверяются там, а здесь — только правила «роль × фаза». Отключённому пользователю
отказывают все предикаты.
"""

from enum import StrEnum

from app.common.model import Actor
from app.contest.model.contest import ContestPhase


class ContestAction(StrEnum):
    """Действия уровня конкурса; фронт показывает кнопки по ним и не дублирует правила фаз."""

    SUBMIT_IDEA = "submit_idea"
    VOTE = "vote"
    VIEW_RESULTS = "view_results"


def can_submit_ideas(actor: Actor, phase: ContestPhase) -> bool:
    """Идеи подаёт только активный сотрудник и только пока идёт приём (организатор не участвует)."""
    return actor.is_active and actor.is_employee and phase is ContestPhase.SUBMISSION


def can_vote_in_contest(actor: Actor, phase: ContestPhase) -> bool:
    """Голосует активный сотрудник в фазе голосования (идею проверяет `vote.model.can_vote`)."""
    return actor.is_active and actor.is_employee and phase is ContestPhase.VOTING


def can_view_results(actor: Actor, phase: ContestPhase) -> bool:
    """Организатор видит итоги всегда, остальные — после закрытия голосования (П8)."""
    return actor.is_active and (actor.is_organizer or phase is ContestPhase.FINISHED)


def can_view_authors(actor: Actor, phase: ContestPhase) -> bool:
    """Авторы раскрываются всем после финала и никому до него — в том числе организатору.

    Правило лежит в `contest`, а не в `result`: список идей (модуль `vote`) тоже решает, показывать
    ли авторов, а `vote` не может импортировать вышестоящий `result` (§4.2).
    """
    return actor.is_active and phase is ContestPhase.FINISHED


def allowed_actions(actor: Actor, phase: ContestPhase) -> frozenset[ContestAction]:
    actions = {
        ContestAction.SUBMIT_IDEA: can_submit_ideas(actor, phase),
        ContestAction.VOTE: can_vote_in_contest(actor, phase),
        ContestAction.VIEW_RESULTS: can_view_results(actor, phase),
    }
    return frozenset(action for action, allowed in actions.items() if allowed)
