"""Список идей конкурса в том виде, в каком его вправе увидеть конкретный пользователь."""

from dataclasses import dataclass, field

from app.contest.model import ContestPhase
from app.idea.model.idea import Idea


@dataclass(frozen=True, slots=True)
class ListedIdea:
    """Идея в списке. Имя автора есть только там, где политика раскрывает авторов (после финала);
    скрыто из repr: связка автор ↔ идея не должна попадать в логи (CLAUDE.md §13)."""

    idea: Idea
    is_mine: bool
    author_name: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class IdeaListing:
    phase: ContestPhase
    ideas: tuple[ListedIdea, ...]
