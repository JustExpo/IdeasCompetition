"""Тестовые часы e2e: только вперёд и только в режиме e2e (CLAUDE.md §9.3, IC-026)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from app.core.access import list_api_paths
from app.core.clock import SystemClock
from app.core.config import Settings
from app.core.testing import ClockMovesBackError, OffsetClock
from app.main import create_app
from tests.fakes import FrozenClock, ReadyDatabase
from tests.unit.core.test_config import apply_env, base_env, clean_env  # noqa: F401

ORIGIN = "http://127.0.0.1:8000"
E2E_ENV = {
    "APP_ENV": "e2e",
    "DATABASE_URL": "postgresql+asyncpg://u:p@db/ideas_e2e",
    "TEST_CLOCK_ENABLED": "true",
    "RATE_LIMIT_PER_IP_ENABLED": "false",
}


def make_app(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> FastAPI:
    apply_env(monkeypatch, base_env(**overrides))
    return create_app(Settings(), ReadyDatabase("postgresql+asyncpg://x@127.0.0.1/x"))


async def post_clock(app: FastAPI, moment: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=ORIGIN, headers={"Origin": ORIGIN}
    ) as client:
        return await client.post("/api/__test__/clock", json={"now": moment})


def test_offset_clock_moves_forward_and_keeps_running() -> None:
    base = FrozenClock(datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    clock = OffsetClock(base)
    target = datetime(2026, 10, 25, 9, 30, tzinfo=UTC)
    clock.move_forward_to(target)
    assert clock.now() == target
    base.advance(timedelta(seconds=5))  # дальше часы идут в реальном времени
    assert clock.now() == target + timedelta(seconds=5)


@pytest.mark.parametrize("delta", [timedelta(0), timedelta(seconds=-1)])
def test_offset_clock_refuses_to_stand_still_or_go_back(delta: timedelta) -> None:
    base = FrozenClock(datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    clock = OffsetClock(base)
    with pytest.raises(ClockMovesBackError):
        clock.move_forward_to(base.now() + delta)


def test_offset_clock_accepts_any_offset_timezone() -> None:
    base = FrozenClock(datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    clock = OffsetClock(base)
    clock.move_forward_to(datetime.fromisoformat("2026-10-22T15:00:00+03:00"))
    assert clock.now() == datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


async def test_route_does_not_exist_outside_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    app = make_app(monkeypatch)
    assert "/api/__test__/clock" not in list_api_paths(app)
    assert isinstance(app.state.clock, SystemClock)
    response = await post_clock(app, "2030-01-01T00:00:00+00:00")
    assert response.status_code == 404


def test_e2e_mode_uses_offset_clock_and_exposes_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    app = make_app(monkeypatch, **E2E_ENV)
    assert isinstance(app.state.clock, OffsetClock)
    assert "/api/__test__/clock" in list_api_paths(app)


async def test_unsafe_origin_is_still_refused_in_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    app = make_app(monkeypatch, **E2E_ENV)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=ORIGIN, headers={"Origin": "https://evil.example"}
    ) as client:
        response = await client.post("/api/__test__/clock", json={"now": "2030-01-01T00:00:00Z"})
    assert response.status_code == 403
