"""Схемы итогов. Авторы есть только в схеме завершённого конкурса (CLAUDE.md §9.3)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.result.model import ContestResultsView, RankedIdea


class ResultItem(BaseModel):
    """Место идеи без автора: так итоги видит организатор до финала."""

    model_config = ConfigDict(extra="forbid")

    place: int
    idea_id: UUID
    title: str
    votes: int


class FinalResultItem(BaseModel):
    """Место идеи после финала: автор раскрыт."""

    model_config = ConfigDict(extra="forbid")

    place: int
    idea_id: UUID
    title: str
    votes: int
    author_name: str


class InProgressResultsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["in_progress"] = "in_progress"
    results: list[ResultItem]


class FinalResultsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["final"] = "final"
    results: list[FinalResultItem]


ResultsResponse = Annotated[
    InProgressResultsResponse | FinalResultsResponse, Field(discriminator="status")
]


class DashboardResponse(BaseModel):
    """Экран организатора (Ф5): числа и текущие места; авторов нет и после финала."""

    model_config = ConfigDict(extra="forbid")

    ideas_count: int
    voters_count: int
    results: list[ResultItem]


def _item(ranked: RankedIdea) -> ResultItem:
    score = ranked.score
    return ResultItem(
        place=ranked.place, idea_id=score.idea_id, title=score.title, votes=score.votes
    )


def build_results_response(
    view: ContestResultsView,
) -> InProgressResultsResponse | FinalResultsResponse:
    ranking = view.results.ranking
    if not view.results.is_final:
        return InProgressResultsResponse(results=[_item(ranked) for ranked in ranking])
    items = []
    for ranked in ranking:
        name = view.author_names.get(ranked.score.author_id)
        if name is None:  # недостижимо: после финала политика раскрывает авторов
            raise RuntimeError("в завершённом конкурсе у идеи нет имени автора")
        items.append(
            FinalResultItem(
                place=ranked.place,
                idea_id=ranked.score.idea_id,
                title=ranked.score.title,
                votes=ranked.score.votes,
                author_name=name,
            )
        )
    return FinalResultsResponse(results=items)


def build_dashboard_response(view: ContestResultsView) -> DashboardResponse:
    return DashboardResponse(
        ideas_count=view.ideas_count,
        voters_count=view.voters_count,
        results=[_item(ranked) for ranked in view.results.ranking],
    )
