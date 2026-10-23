"""Тестовые часы для e2e (CLAUDE.md §8.2, §9.3, Р14).

Подключаются только в `APP_ENV=e2e` из `app.main`; никто другой этот модуль не импортирует
(контракт import-linter). Часы идут в реальном времени от сдвига, который можно только
увеличивать: браузерный тест переносит конкурс через дедлайны, не дожидаясь их, а сессии и
сроки писем не откатываются назад.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.common.exception import AppError
from app.core.access import Policy, require
from app.core.clock import Clock, SystemClock


class ClockMovesBackError(AppError):
    code = "clock_moves_back"
    status = 400


class OffsetClock:
    """Реальное время плюс сдвиг; сдвиг только растёт."""

    def __init__(self, base: Clock | None = None) -> None:
        self._base = base or SystemClock()
        self._offset = timedelta(0)

    def now(self) -> datetime:
        return self._base.now() + self._offset

    def move_forward_to(self, moment: datetime) -> None:
        current = self.now()
        if moment.astimezone(UTC) <= current:
            raise ClockMovesBackError("Часы можно переводить только вперёд.")
        self._offset += moment.astimezone(UTC) - current


class SetClockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    now: AwareDatetime


router = APIRouter(prefix="/api/__test__", tags=["test"], include_in_schema=False)


@router.post("/clock", status_code=204, dependencies=[require(Policy.E2E_ONLY)])
async def post_clock(body: SetClockRequest, request: Request) -> Response:
    """Перевести часы вперёд и сразу выполнить тик планировщика: финал и письма без ожидания."""
    state = request.app.state
    clock: OffsetClock = state.clock
    clock.move_forward_to(body.now)
    await state.scheduler.run_tick()
    return Response(status_code=204)
