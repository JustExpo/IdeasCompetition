"""Список идей конкурса (CLAUDE.md §8.2): маршрут в `vote`, потому что в голосовании к нему
добавляется голос текущего пользователя."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.common.model import Actor, ContestId
from app.core.access import Policy, get_current_actor, require
from app.vote import service
from app.vote.controller.schemas import IdeasResponse, build_ideas_response

router = APIRouter(tags=["ideas"])


@router.get("/api/contests/{contest_id}/ideas", dependencies=[require(Policy.AUTHENTICATED)])
async def get_contest_ideas(
    contest_id: int, request: Request, actor: Annotated[Actor, Depends(get_current_actor)]
) -> IdeasResponse:
    state = request.app.state
    listing = await service.list_contest_ideas(
        state.database, state.clock, actor, ContestId(contest_id)
    )
    return build_ideas_response(listing)
