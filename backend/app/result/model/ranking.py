"""Подсчёт мест и правило ничьей (П10)."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from app.common.exception import DomainValidationError
from app.common.model import ContestId, IdeaId, UserId, require_aware


@dataclass(frozen=True, slots=True)
class IdeaScore:
    """Число голосов за идею на момент подсчёта."""

    idea_id: IdeaId
    title: str = field(repr=False)
    author_id: UserId = field(repr=False)
    submitted_at: datetime
    votes: int

    def __post_init__(self) -> None:
        require_aware(self.submitted_at, "submitted_at")
        if self.votes < 0:
            raise DomainValidationError("Число голосов не может быть отрицательным")


@dataclass(frozen=True, slots=True)
class RankedIdea:
    """Место идеи в итогах. Места уникальны: ничью разрешает время подачи."""

    place: int
    score: IdeaScore


@dataclass(frozen=True, slots=True)
class ContestResults:
    """Итоги конкурса. До финала (`is_final=False`) авторов не показывают никому."""

    contest_id: ContestId
    ranking: tuple[RankedIdea, ...]
    is_final: bool

    @property
    def winner(self) -> RankedIdea | None:
        return self.ranking[0] if self.ranking else None


def rank_ideas(scores: Iterable[IdeaScore]) -> tuple[RankedIdea, ...]:
    """Больше голосов — выше; при равенстве выше поданная раньше; затем по id (детерминизм).

    При нуле голосов у всех побеждает самая ранняя идея — то же правило без исключений.
    """
    ordered = sorted(scores, key=lambda s: (-s.votes, s.submitted_at, str(s.idea_id)))
    return tuple(
        RankedIdea(place=index, score=score) for index, score in enumerate(ordered, start=1)
    )
