"""Схемы списка идей по фазам: анонимность закреплена типом ответа (CLAUDE.md §9.3).

В фазе голосования нет ни автора, ни времени подачи — схема их просто не содержит
(`extra="forbid"`, точный набор ключей проверяет contract-тест); авторы появляются только в
схеме завершённого конкурса.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.contest.model import ContestPhase
from app.idea.model import IdeaListing, ListedIdea


class OwnIdeaItem(BaseModel):
    """Приём идей: пользователь видит только свои идеи, поэтому версия и время ему известны."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str
    version: int
    submitted_at: datetime
    updated_at: datetime


class VotingIdeaItem(BaseModel):
    """Голосование: идея без автора и без времени подачи (по нему вычисляется автор)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str
    is_mine: bool


class FinishedIdeaItem(BaseModel):
    """Итоги: авторы раскрыты."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str
    is_mine: bool
    author_name: str
    submitted_at: datetime


class SubmissionIdeasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["submission"] = "submission"
    items: list[OwnIdeaItem]


class VotingIdeasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["voting"] = "voting"
    items: list[VotingIdeaItem]


class FinishedIdeasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["finished"] = "finished"
    items: list[FinishedIdeaItem]


IdeasResponse = Annotated[
    SubmissionIdeasResponse | VotingIdeasResponse | FinishedIdeasResponse,
    Field(discriminator="phase"),
]


def _own_item(listed: ListedIdea) -> OwnIdeaItem:
    idea = listed.idea
    return OwnIdeaItem(
        id=idea.id,
        title=idea.content.title,
        description=idea.content.description,
        version=idea.version,
        submitted_at=idea.submitted_at,
        updated_at=idea.updated_at,
    )


def _voting_item(listed: ListedIdea) -> VotingIdeaItem:
    idea = listed.idea
    return VotingIdeaItem(
        id=idea.id,
        title=idea.content.title,
        description=idea.content.description,
        is_mine=listed.is_mine,
    )


def _finished_item(listed: ListedIdea) -> FinishedIdeaItem:
    idea = listed.idea
    if listed.author_name is None:  # недостижимо: после финала политика раскрывает авторов
        raise RuntimeError("в завершённом конкурсе у идеи нет имени автора")
    return FinishedIdeaItem(
        id=idea.id,
        title=idea.content.title,
        description=idea.content.description,
        is_mine=listed.is_mine,
        author_name=listed.author_name,
        submitted_at=idea.submitted_at,
    )


def build_ideas_response(
    listing: IdeaListing,
) -> SubmissionIdeasResponse | VotingIdeasResponse | FinishedIdeasResponse:
    if listing.phase is ContestPhase.SUBMISSION:
        return SubmissionIdeasResponse(items=[_own_item(i) for i in listing.ideas])
    if listing.phase is ContestPhase.VOTING:
        return VotingIdeasResponse(items=[_voting_item(i) for i in listing.ideas])
    return FinishedIdeasResponse(items=[_finished_item(i) for i in listing.ideas])
