"""Вход, выход, профиль (CLAUDE.md §8.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth import service
from app.auth.controller.dependencies import (
    COOKIE_MAX_AGE_S,
    is_secure_cookie,
    session_cookie_name,
)
from app.auth.controller.schemas import LoginRequest, RegisterRequest, UserResponse
from app.auth.model import Actor
from app.auth.service import IssuedSession
from app.core.access import Policy, get_current_actor, require
from app.core.clock import Clock
from app.core.db import Database

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # Заголовкам прокси (X-Forwarded-For) не верим: перед приложением прокси нет, а подделка
    # заголовка дала бы обход лимита.
    return request.client.host if request.client else "unknown"


def _set_session_cookie(request: Request, response: Response, issued: IssuedSession) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        session_cookie_name(settings),
        issued.token,
        max_age=COOKIE_MAX_AGE_S,
        path="/",
        httponly=True,
        samesite="lax",
        secure=is_secure_cookie(settings),
    )


@router.post("/login", dependencies=[require(Policy.PUBLIC)])
async def post_login(body: LoginRequest, request: Request, response: Response) -> UserResponse:
    state = request.app.state
    database: Database = state.database
    clock: Clock = state.clock
    issued = await service.log_in(
        database,
        state.passwords,
        clock,
        limiter=state.limiter,
        client_ip=_client_ip(request),
        email=body.email,
        password=body.password,
    )
    _set_session_cookie(request, response, issued)
    return UserResponse.from_user(issued.user)


@router.post("/register", status_code=201, dependencies=[require(Policy.PUBLIC)])
async def post_register(
    body: RegisterRequest, request: Request, response: Response
) -> UserResponse:
    state = request.app.state
    issued = await service.register_employee(
        state.database,
        state.passwords,
        state.clock,
        state.limiter,
        client_ip=_client_ip(request),
        allowed_domains=state.settings.allowed_email_domains,
        email=body.email,
        name=body.name,
        password=body.password,
    )
    _set_session_cookie(request, response, issued)
    return UserResponse.from_user(issued.user)


@router.post("/logout", status_code=204, dependencies=[require(Policy.AUTHENTICATED)])
async def post_logout(request: Request, response: Response) -> None:
    state = request.app.state
    name = session_cookie_name(state.settings)
    token = request.cookies.get(name)
    if token:  # политика уже проверила, что cookie есть; страховка от гонки
        await service.log_out(state.database, state.clock, token, events=state.events)
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
