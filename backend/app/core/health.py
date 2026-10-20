"""`/api/health` — готовность: БД отвечает и схема на ревизии приложения, иначе 503.

Блокировка единственного экземпляра (§12.2) добавляется в IC-006.
"""

from fastapi import APIRouter, Request

from app.core.access import Policy, require
from app.core.db import Database

router = APIRouter(dependencies=[require(Policy.PUBLIC)])


@router.get("/api/health")
async def get_health(request: Request) -> dict[str, str]:
    database: Database = request.app.state.database
    await database.check_ready()
    return {"status": "ok"}
