"""Подача и правка идеи (CLAUDE.md §8.2)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.common.model import Actor, ContestId, IdeaId
from app.core.access import Policy, get_current_actor, require
from app.idea import service
from app.idea.controller.schemas import EditIdeaRequest, IdeaResponse, SubmitIdeaRequest

router = APIRouter(tags=["ideas"])

CurrentActor = Annotated[Actor, Depends(get_current_actor)]


@router.post(
    "/api/contests/{contest_id}/ideas",
    status_code=201,
    dependencies=[require(Policy.EMPLOYEE)],
)
async def post_idea(
    contest_id: int,
    body: SubmitIdeaRequest,
    request: Request,
    response: Response,
    actor: CurrentActor,
) -> IdeaResponse:
    state = request.app.state
    submitted = await service.submit_idea(
        state.database,
        state.clock,
        actor,
        ContestId(contest_id),
        client_request_id=body.client_request_id,
        title=body.title,
        description=body.description,
    )
    if not submitted.created:
        response.status_code = 200  # повтор уже принятого запроса (§8.3)
    return IdeaResponse.from_idea(submitted.idea)


@router.patch("/api/ideas/{idea_id}", dependencies=[require(Policy.EMPLOYEE)])
async def patch_idea(
    idea_id: UUID, body: EditIdeaRequest, request: Request, actor: CurrentActor
) -> IdeaResponse:
    state = request.app.state
    idea = await service.edit_idea(
        state.database,
        state.clock,
        actor,
        IdeaId(idea_id),
        title=body.title,
        description=body.description,
        version=body.version,
    )
    return IdeaResponse.from_idea(idea)
