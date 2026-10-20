"""Вход, выход, профиль (CLAUDE.md §8.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth import service
from app.auth.controller.dependencies import (
    COOKIE_MAX_AGE_S,
    get_current_actor,
    is_secure_cookie,
    session_cookie_name,
)
from app.auth.controller.schemas import LoginRequest, UserResponse
from app.auth.model import Actor
from app.core.access import Policy, require
from app.core.clock import Clock
from app.core.db import Database

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", dependencies=[require(Policy.PUBLIC)])
async def post_login(body: LoginRequest, request: Request, response: Response) -> UserResponse:
    state = request.app.state
    database: Database = state.database
    clock: Clock = state.clock
    issued = await service.log_in(
        database, state.passwords, clock, email=body.email, password=body.password
    )
    response.set_cookie(
        session_cookie_name(state.settings),
        issued.token,
        max_age=COOKIE_MAX_AGE_S,
        path="/",
        httponly=True,
        samesite="lax",
        secure=is_secure_cookie(state.settings),
    )
    return UserResponse.from_user(issued.user)


@router.post("/logout", status_code=204, dependencies=[require(Policy.AUTHENTICATED)])
async def post_logout(request: Request, response: Response) -> None:
    state = request.app.state
    name = session_cookie_name(state.settings)
    token = request.cookies.get(name)
    if token:  # политика уже проверила, что cookie есть; страховка от гонки
        await service.log_out(state.database, state.clock, token)
    response.delete_cookie(
        name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=is_secure_cookie(state.settings),
    )


@router.get("/me", dependencies=[require(Policy.AUTHENTICATED)])
async def get_me(
    request: Request, actor: Annotated[Actor, Depends(get_current_actor)]
) -> UserResponse:
    user = await service.get_current_user(request.app.state.database, actor)
    return UserResponse.from_user(user)
