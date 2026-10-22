"""Схемы запросов и ответов конкурсов."""

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.contest.model import (
    TIE_BREAK_RULE_TEXT,
    Contest,
    ContestAction,
    ContestDetails,
    ContestPhase,
)


class CreateContestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Верхние пределы — защита от гигантских значений; точные длины проверяет contest.model.
    topic: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=50_000)
    # AwareDatetime: время без часового пояса отклоняется с 422 (CLAUDE.md §8.1).
    submission_deadline: AwareDatetime
    voting_deadline: AwareDatetime


class ContestResponse(BaseModel):
    """Конкурс в списке."""

    model_config = ConfigDict(extra="forbid")

    id: int
    topic: str
    description: str
    submission_deadline: datetime
    voting_deadline: datetime
    created_at: datetime
    phase: ContestPhase

    @classmethod
    def from_contest(cls, contest: Contest, phase: ContestPhase) -> "ContestResponse":
        return cls(
            id=contest.id,
            topic=contest.topic,
            description=contest.description,
            submission_deadline=contest.schedule.submission_deadline,
            voting_deadline=contest.schedule.voting_deadline,
            created_at=contest.created_at,
            phase=phase,
        )


class ContestDetailResponse(ContestResponse):
    """Карточка конкурса: клиент не дублирует правила фаз, а читает `allowed_actions`."""

    server_time: datetime
    allowed_actions: list[ContestAction]
    tie_break_rule: str = TIE_BREAK_RULE_TEXT

    @classmethod
    def from_details(cls, details: ContestDetails) -> "ContestDetailResponse":
        base = ContestResponse.from_contest(details.contest, details.phase)
        return cls(
            **base.model_dump(),
            server_time=details.server_time,
            # Порядок фиксирован: ответ не должен зависеть от хэшей множества.
            allowed_actions=sorted(details.actions),
        )


class ContestListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ContestResponse]
    total: int
    server_time: datetime


LimitQuery = Annotated[int, Field(ge=1, le=100)]
OffsetQuery = Annotated[int, Field(ge=0)]
