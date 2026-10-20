"""`/api/health` — готовность: БД отвечает, схема на ревизии приложения, блокировка единственного
экземпляра удержана и сервер не останавливается, иначе 503 (CLAUDE.md §11.4).

Причина наружу не отдаётся (§9.3): она пишется в лог.
"""

from fastapi import APIRouter, Request

from app.common.exception import ServiceUnavailableError
from app.core.access import Policy, require
from app.core.db import Database
from app.core.singleton import SingletonLock

router = APIRouter(dependencies=[require(Policy.PUBLIC)])


@router.get("/api/health")
async def get_health(request: Request) -> dict[str, str]:
    state = request.app.state
    # При SIGTERM сначала 503, чтобы балансировщик и healthcheck перестали слать запросы.
    if state.draining:
        raise ServiceUnavailableError("Сервер останавливается.")
    singleton: SingletonLock | None = state.singleton
    if singleton is not None and not await singleton.verify():
        raise ServiceUnavailableError("Блокировка единственного экземпляра потеряна.")
    database: Database = state.database
    await database.check_ready()
    return {"status": "ok"}
