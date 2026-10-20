"""Чистые части блокировки экземпляра и участие блокировки/остановки в `/api/health`."""

import httpx
import pytest

from app.core.config import Settings
from app.core.singleton import ADVISORY_LOCK_KEY, SingletonLock, split_lock_key, to_asyncpg_dsn
from app.main import create_app
from tests.fakes import ReadyDatabase
from tests.unit.core.test_config import apply_env, base_env


class StubLock(SingletonLock):
    def __init__(self, *, alive: bool) -> None:
        super().__init__("postgresql://x@127.0.0.1/x")
        self.alive = alive

    async def verify(self) -> bool:
        return self.alive


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    apply_env(monkeypatch, base_env())
    return Settings()


async def get_health(
    settings: Settings, singleton: SingletonLock | None, *, draining: bool = False
) -> httpx.Response:
    app = create_app(settings, ReadyDatabase("postgresql+asyncpg://x@127.0.0.1/x"), singleton)
    app.state.draining = draining
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        return await client.get("/api/health")


def test_to_asyncpg_dsn_drops_dialect_prefix() -> None:
    assert (
        to_asyncpg_dsn("postgresql+asyncpg://u:p@db:5432/ideas") == "postgresql://u:p@db:5432/ideas"
    )


def test_split_lock_key_matches_pg_locks_layout() -> None:
    high, low = split_lock_key(ADVISORY_LOCK_KEY)
    assert (high << 32) | low == ADVISORY_LOCK_KEY
    assert split_lock_key(0x1_0000_0002) == (1, 2)


def test_new_lock_is_not_held() -> None:
    assert SingletonLock("postgresql://x@127.0.0.1/x").held is False


async def test_health_ok_without_singleton(settings: Settings) -> None:
    assert (await get_health(settings, None)).status_code == 200


async def test_health_ok_when_lock_is_held(settings: Settings) -> None:
    assert (await get_health(settings, StubLock(alive=True))).status_code == 200


async def test_health_503_when_lock_is_lost(settings: Settings) -> None:
    response = await get_health(settings, StubLock(alive=False))
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
    assert response.headers["retry-after"] == "5"


async def test_health_503_while_draining(settings: Settings) -> None:
    assert (await get_health(settings, None, draining=True)).status_code == 503
