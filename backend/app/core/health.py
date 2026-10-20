"""Временный `/api/health` без БД; проверка БД и блокировки добавляется в IC-005."""

from fastapi import APIRouter

from app.core.access import Policy, require

router = APIRouter(dependencies=[require(Policy.PUBLIC)])


@router.get("/api/health")
async def get_health() -> dict[str, str]:
    return {"status": "ok"}
