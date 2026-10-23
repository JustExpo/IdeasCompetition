"""Итоги конкурса в виде, готовом к показу: места, счётчики и (после финала) имена авторов."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.common.model import UserId
from app.result.model.ranking import ContestResults


@dataclass(frozen=True, slots=True)
class ContestResultsView:
    """Результат `result.service`: все числа взяты из одной транзакции и согласованы между собой.

    `author_names` пуст до финала (политика `can_view_authors`); скрыт из repr: связка
    автор ↔ идея не должна попадать в логи (CLAUDE.md §13).
    """

    results: ContestResults
    ideas_count: int
    voters_count: int
    author_names: Mapping[UserId, str] = field(default_factory=dict, repr=False)
