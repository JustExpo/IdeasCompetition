"""Конкурсы: создание, список, карточка (CLAUDE.md §8.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.common.model import Actor, ContestId
from app.contest import service
from app.contest.controller.schemas import (
    ContestDetailResponse,
    ContestListResponse,
    ContestResponse,
    CreateContestRequest,
    LimitQuery,
    OffsetQuery,
)
from app.core.access import Policy, get_current_actor, require

router = APIRouter(prefix="/api/contests", tags=["contests"])

CurrentActor = Annotated[Actor, Depends(get_current_actor)]


@router.post("", status_code=201, dependencies=[require(Policy.ORGANIZER)])
async def post_contest(
    body: CreateContestRequest, request: Request, actor: CurrentActor
) -> ContestDetailResponse:
    state = request.app.state
    details = await service.create_contest(
        state.database,
        state.clock,
        actor,
        topic=body.topic,
        description=body.description,
        submission_deadline=body.submission_deadline,
        voting_deadline=body.voting_deadline,
    )
    return ContestDetailResponse.from_details(details)


@router.get("", dependencies=[require(Policy.AUTHENTICATED)])
async def get_contests(
    request: Request,
    limit: Annotated[LimitQuery, Query()] = 20,
    offset: Annotated[OffsetQuery, Query()] = 0,
) -> ContestListResponse:
    state = request.app.state
    page = await service.list_contests(state.database, state.clock, limit=limit, offset=offset)
    return ContestListResponse(
        items=[ContestResponse.from_contest(contest, phase) for contest, phase in page.items],
        total=page.total,
        server_time=page.server_time,
    )


@router.get("/{contest_id}", dependencies=[require(Policy.AUTHENTICATED)])
async def get_contest(
    contest_id: int, request: Request, actor: CurrentActor
) -> ContestDetailResponse:
    state = request.app.state
    details = await service.get_contest(state.database, state.clock, actor, ContestId(contest_id))
    return ContestDetailResponse.from_details(details)
