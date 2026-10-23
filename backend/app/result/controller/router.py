"""Итоги конкурса и экран организатора (CLAUDE.md §8.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.common.model import Actor, ContestId
from app.core.access import Policy, get_current_actor, require
from app.result import service
from app.result.controller.schemas import (
    DashboardResponse,
    ResultsResponse,
    build_dashboard_response,
    build_results_response,
)

router = APIRouter(tags=["results"])

CurrentActor = Annotated[Actor, Depends(get_current_actor)]


@router.get("/api/contests/{contest_id}/results", dependencies=[require(Policy.AUTHENTICATED)])
async def get_contest_results(
    contest_id: int, request: Request, actor: CurrentActor
) -> ResultsResponse:
    state = request.app.state
    view = await service.get_results(state.database, state.clock, actor, ContestId(contest_id))
    return build_results_response(view)


@router.get(
    "/api/organizer/contests/{contest_id}/dashboard", dependencies=[require(Policy.ORGANIZER)]
)
async def get_dashboard(
    contest_id: int, request: Request, actor: CurrentActor
) -> DashboardResponse:
    state = request.app.state
    view = await service.get_results(state.database, state.clock, actor, ContestId(contest_id))
    return build_dashboard_response(view)
