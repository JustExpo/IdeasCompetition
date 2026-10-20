"""Вход, выход, сессии и политики на реальном PostgreSQL (CLAUDE.md §9.1–§9.2, IC-007)."""

import asyncio
import hashlib
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.controller.dependencies import COOKIE_MAX_AGE_S
from app.auth.service import SESSION_LIFETIME, PasswordService, ensure_organizer
from app.common.model import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.core.access import Policy, require
from app.core.config import Settings
from app.core.db import Database
from app.main import create_app
from app.user import service as user_service
from app.user.exception import EmailTakenError
from app.user.model import UserRole
from tests.fakes import FrozenClock
from tests.unit.core.test_config import apply_env, base_env

pytestmark = pytest.mark.commits

ORIGIN = "http://127.0.0.1:8000"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
PASSWORD = "correct-horse-battery"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    apply_env(monkeypatch, base_env())
    return Settings()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def passwords() -> PasswordService:
    return PasswordService()


@pytest.fixture
def app(
    settings: Settings, database: Database, clock: FrozenClock, passwords: PasswordService
) -> FastAPI:
    application = create_app(settings, database, clock=clock, passwords=passwords)

    @application.get("/api/probe/organizer", dependencies=[require(Policy.ORGANIZER)])
    async def organizer_probe() -> dict[str, str]:
        return {"ok": "organizer"}

    @application.get("/api/probe/employee", dependencies=[require(Policy.EMPLOYEE)])
    async def employee_probe() -> dict[str, str]:
        return {"ok": "employee"}

    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=ORIGIN, headers={"Origin": ORIGIN}
    ) as http:
        yield http


async def create_user(
    database: Database,
    passwords: PasswordService,
    *,
    email: str = "anna@example.com",
    password: str = PASSWORD,
    role: UserRole = UserRole.EMPLOYEE,
    active: bool = True,
    password_hash: str | None = None,
) -> int:
    hashed = password_hash or await passwords.hash_password(password)

    async def work(session: AsyncSession) -> int:
        ensured = await user_service.ensure_user(
            session, email=email, name="Анна", password_hash=hashed, role=role, now=NOW
        )
        if not active:
            await session.execute(
                text("UPDATE users SET is_active = false WHERE id = :id"), {"id": ensured.user.id}
            )
        return int(ensured.user.id)

    return await database.run_in_transaction(work)


def cookie_of(response: httpx.Response, name: str = "sid") -> str:
    return response.cookies[name]


async def log_in(
    client: httpx.AsyncClient, email: str = "anna@example.com", password: str = PASSWORD
) -> httpx.Response:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    client.cookies.clear()  # куки передаём явно: тест сам решает, чья это сессия
    return response


async def get_with(client: httpx.AsyncClient, path: str, token: str | None) -> httpx.Response:
    headers = {} if token is None else {"cookie": f"sid={token}"}
    return await client.get(path, headers=headers)


async def test_login_returns_profile_and_sets_secure_flags_cookie(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    user_id = await create_user(database, passwords)
    response = await log_in(client)
    assert response.status_code == 200
    assert response.json() == {
        "id": user_id,
        "email": "anna@example.com",
        "name": "Анна",
        "role": "employee",
    }
    header = response.headers["set-cookie"]
    assert header.startswith("sid=")
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert "Path=/" in header
    assert f"Max-Age={COOKIE_MAX_AGE_S}" in header
    assert COOKIE_MAX_AGE_S == int(SESSION_LIFETIME.total_seconds()) == 7 * 24 * 3600
    assert "Secure" not in header  # dev по http: Secure-cookie браузер не сохранил бы


async def test_me_requires_a_valid_session(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    token = cookie_of(await log_in(client))
    ok = await get_with(client, "/api/auth/me", token)
    assert ok.status_code == 200
    assert ok.json()["email"] == "anna@example.com"
    for missing in (None, "not-a-real-token"):
        response = await get_with(client, "/api/auth/me", missing)
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"


async def test_unknown_email_and_wrong_password_look_identical(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    wrong_password = await log_in(client, password="wrong-password-123")
    unknown_email = await log_in(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401

    def shape(response: httpx.Response) -> dict[str, object]:
        body = response.json()
        body.pop("request_id")
        return body  # type: ignore[no-any-return]

    assert shape(wrong_password) == shape(unknown_email)
    assert shape(wrong_password)["code"] == "invalid_credentials"
    assert "set-cookie" not in wrong_password.headers
    assert "set-cookie" not in unknown_email.headers


async def test_email_is_case_and_space_insensitive(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    response = await log_in(client, email="  ANNA@Example.COM ")
    assert response.status_code == 200


async def test_every_login_issues_a_new_token_and_both_work(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    first = cookie_of(await log_in(client))
    second = cookie_of(await log_in(client))
    assert first != second
    assert (await get_with(client, "/api/auth/me", first)).status_code == 200
    assert (await get_with(client, "/api/auth/me", second)).status_code == 200


async def test_only_token_hash_is_stored(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    token = cookie_of(await log_in(client))

    async def stored(session: AsyncSession) -> list[bytes]:
        rows = await session.execute(text("SELECT token_hash FROM sessions"))
        return [bytes(row[0]) for row in rows]

    assert await database.run_in_transaction(stored) == [hashlib.sha256(token.encode()).digest()]


@pytest.mark.parametrize(
    ("offset", "valid"),
    [
        (SESSION_LIFETIME - timedelta(microseconds=1), True),
        (SESSION_LIFETIME, False),
        (SESSION_LIFETIME + timedelta(microseconds=1), False),
    ],
    ids=["expires_at-1µs", "expires_at", "expires_at+1µs"],
)
async def test_session_expires_exactly_at_expires_at(
    client: httpx.AsyncClient,
    database: Database,
    passwords: PasswordService,
    clock: FrozenClock,
    offset: timedelta,
    valid: bool,
) -> None:
    await create_user(database, passwords)
    token = cookie_of(await log_in(client))
    clock.set(NOW + offset)
    response = await get_with(client, "/api/auth/me", token)
    assert response.status_code == (200 if valid else 401)


async def test_logout_revokes_session_and_clears_cookie(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    token = cookie_of(await log_in(client))
    response = await client.post("/api/auth/logout", headers={"cookie": f"sid={token}"})
    assert response.status_code == 204
    assert "sid=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert (await get_with(client, "/api/auth/me", token)).status_code == 401
    again = await client.post("/api/auth/logout", headers={"cookie": f"sid={token}"})
    assert again.status_code == 401


async def test_logout_without_session_is_401(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/auth/logout")).status_code == 401


async def test_logout_leaves_other_sessions_of_the_user_alone(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords)
    first = cookie_of(await log_in(client))
    second = cookie_of(await log_in(client))
    await client.post("/api/auth/logout", headers={"cookie": f"sid={first}"})
    assert (await get_with(client, "/api/auth/me", second)).status_code == 200


async def test_deactivation_takes_effect_on_the_next_request(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    user_id = await create_user(database, passwords)
    token = cookie_of(await log_in(client))
    assert (await get_with(client, "/api/auth/me", token)).status_code == 200

    async def deactivate(session: AsyncSession) -> None:
        await session.execute(
            text("UPDATE users SET is_active = false WHERE id = :id"), {"id": user_id}
        )

    await database.run_in_transaction(deactivate)
    assert (await get_with(client, "/api/auth/me", token)).status_code == 401
    assert (await log_in(client)).status_code == 401


async def test_inactive_user_gets_the_same_login_error(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords, active=False)
    response = await log_in(client)
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_role_change_takes_effect_on_the_next_request(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    user_id = await create_user(database, passwords)
    token = cookie_of(await log_in(client))
    assert (await get_with(client, "/api/probe/organizer", token)).status_code == 403

    async def promote(session: AsyncSession) -> None:
        await session.execute(
            text("UPDATE users SET role = 'organizer' WHERE id = :id"), {"id": user_id}
        )

    await database.run_in_transaction(promote)
    assert (await get_with(client, "/api/probe/organizer", token)).status_code == 200


@pytest.mark.parametrize(
    ("length", "ok"),
    [
        (PASSWORD_MIN_LENGTH, True),
        (PASSWORD_MAX_LENGTH, True),
        (PASSWORD_MAX_LENGTH + 1, False),
    ],
)
async def test_password_length_boundaries_at_login(
    client: httpx.AsyncClient,
    database: Database,
    passwords: PasswordService,
    length: int,
    ok: bool,
) -> None:
    password = "p" * length
    if length <= PASSWORD_MAX_LENGTH:
        await create_user(database, passwords, password=password)
    response = await log_in(client, password=password)
    assert response.status_code == (200 if ok else 401)
    if not ok:
        assert response.json()["code"] == "invalid_credentials"


async def test_unknown_or_extra_fields_are_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "x", "admin": True}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_login_needs_allowed_origin(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


async def test_weak_hash_is_upgraded_on_successful_login(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    await create_user(database, passwords, password_hash=weak)
    assert (await log_in(client)).status_code == 200

    async def stored_hash(session: AsyncSession) -> str:
        return str(await session.scalar(text("SELECT password_hash FROM users")))

    upgraded = await database.run_in_transaction(stored_hash)
    assert upgraded != weak
    assert not passwords.needs_rehash(upgraded)
    assert (await log_in(client)).status_code == 200


async def test_policies_work_with_real_sessions(
    client: httpx.AsyncClient, database: Database, passwords: PasswordService
) -> None:
    await create_user(database, passwords, email="emp@example.com")
    await create_user(database, passwords, email="org@example.com", role=UserRole.ORGANIZER)
    employee = cookie_of(await log_in(client, email="emp@example.com"))
    organizer = cookie_of(await log_in(client, email="org@example.com"))

    assert (await get_with(client, "/api/probe/employee", employee)).status_code == 200
    assert (await get_with(client, "/api/probe/organizer", employee)).status_code == 403
    assert (await get_with(client, "/api/probe/organizer", organizer)).status_code == 200
    denied = await get_with(client, "/api/probe/employee", organizer)
    assert denied.status_code == 403
    assert denied.json()["code"] == "organizer_cannot_participate"
    assert (await get_with(client, "/api/probe/organizer", None)).status_code == 401


class CountingHasher:
    """Настоящий Argon2, который запоминает наибольшее число одновременных вычислений."""

    def __init__(self) -> None:
        self._inner = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0

    def hash(self, password: str) -> str:
        return self._inner.hash(password)

    def verify(self, hash: str, password: str) -> bool:
        with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            return self._inner.verify(hash, password)
        finally:
            with self._lock:
                self.in_flight -= 1

    def check_needs_rehash(self, hash: str) -> bool:
        return self._inner.check_needs_rehash(hash)


async def test_ten_simultaneous_logins_respect_the_hashing_semaphore(
    settings: Settings, database: Database, clock: FrozenClock
) -> None:
    hasher = CountingHasher()
    limited = PasswordService(concurrency=4, hasher=hasher)
    await create_user(database, limited)
    app = create_app(settings, database, clock=clock, passwords=limited)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=ORIGIN, headers={"Origin": ORIGIN}
    ) as client:
        responses = await asyncio.gather(*(log_in(client) for _ in range(10)))
    assert [r.status_code for r in responses] == [200] * 10
    assert 1 <= hasher.max_in_flight <= 4
    assert len({cookie_of(r) for r in responses}) == 10


async def test_prod_cookie_is_host_prefixed_and_secure(
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    clock: FrozenClock,
    passwords: PasswordService,
) -> None:
    prod_origin = "https://ideas.example.com"
    apply_env(
        monkeypatch,
        base_env(
            APP_ENV="prod",
            PUBLIC_BASE_URL=prod_origin,
            ORGANIZER_PASSWORD="a-long-production-password",
        ),
    )
    app = create_app(Settings(), database, clock=clock, passwords=passwords)
    await create_user(database, passwords)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url=prod_origin, headers={"Origin": prod_origin}
    ) as client:
        response = await client.post(
            "/api/auth/login", json={"email": "anna@example.com", "password": PASSWORD}
        )
        assert response.status_code == 200
        header = response.headers["set-cookie"]
        assert header.startswith("__Host-sid=")
        assert "Secure" in header
        assert "HttpOnly" in header
        token = header.split(";")[0].split("=", 1)[1]
        me = await client.get("/api/auth/me", headers={"cookie": f"__Host-sid={token}"})
        assert me.status_code == 200
        plain = await client.get("/api/auth/me", headers={"cookie": f"sid={token}"})
        assert plain.status_code == 401  # обычное имя cookie в prod не принимается


async def count_users(database: Database) -> int:
    async def work(session: AsyncSession) -> int:
        return int(await session.scalar(text("SELECT count(*) FROM users")) or 0)

    return await database.run_in_transaction(work)


async def test_organizer_is_created_once_and_password_is_kept(
    client: httpx.AsyncClient,
    database: Database,
    passwords: PasswordService,
    clock: FrozenClock,
) -> None:
    kwargs = {"email": "Boss@Example.com", "name": "Организатор", "password": PASSWORD}
    first = await ensure_organizer(database, passwords, clock, **kwargs)
    second = await ensure_organizer(
        database, passwords, clock, **{**kwargs, "password": "another-password-1"}
    )
    assert (first.created, second.created) == (True, False)
    assert first.user.id == second.user.id
    assert await count_users(database) == 1
    assert (await log_in(client, email="boss@example.com")).status_code == 200  # старый пароль
    assert (
        await log_in(client, email="boss@example.com", password="another-password-1")
    ).status_code == 401


async def test_organizer_email_taken_by_employee_is_not_promoted(
    database: Database, passwords: PasswordService, clock: FrozenClock
) -> None:
    await create_user(database, passwords, email="boss@example.com")
    with pytest.raises(EmailTakenError):
        await ensure_organizer(
            database,
            passwords,
            clock,
            email="boss@example.com",
            name="Организатор",
            password=PASSWORD,
        )

    async def role(session: AsyncSession) -> str:
        return str(await session.scalar(text("SELECT role FROM users")))

    assert await database.run_in_transaction(role) == "employee"


async def test_restart_does_not_duplicate_organizer(
    settings: Settings, clock: FrozenClock, passwords: PasswordService, database_url: str
) -> None:
    for _ in range(2):  # два старта приложения подряд
        fresh = Database(database_url)
        app = create_app(
            settings, fresh, clock=clock, passwords=passwords, bootstrap_organizer=True
        )
        async with app.router.lifespan_context(app):
            pass
    check = Database(database_url)
    try:
        assert await count_users(check) == 1
    finally:
        await check.dispose()


async def test_database_enforces_user_and_session_constraints(database: Database) -> None:
    async def add(session: AsyncSession, email: str, role: str = "employee") -> None:
        await session.execute(
            text(
                "INSERT INTO users (email, name, password_hash, role, created_at) "
                "VALUES (:email, 'n', 'h', :role, now())"
            ),
            {"email": email, "role": role},
        )

    await database.run_in_transaction(lambda s: add(s, "dup@example.com"))
    with pytest.raises(IntegrityError, match="uq_users_email_lower"):
        await database.run_in_transaction(lambda s: add(s, "DUP@example.com"))
    with pytest.raises(IntegrityError, match="ck_users_role"):
        await database.run_in_transaction(lambda s: add(s, "x@example.com", role="admin"))
    with pytest.raises(IntegrityError, match="ck_users_email_length"):
        await database.run_in_transaction(lambda s: add(s, "x@"))


async def test_deleting_user_removes_sessions_and_token_hash_is_unique(
    database: Database, passwords: PasswordService
) -> None:
    user_id = await create_user(database, passwords)

    async def add_session(session: AsyncSession, token_hash: bytes) -> None:
        await session.execute(
            text(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) "
                "VALUES (:h, :u, now(), now() + interval '1 day')"
            ),
            {"h": token_hash, "u": user_id},
        )

    await database.run_in_transaction(lambda s: add_session(s, b"a" * 32))
    with pytest.raises(IntegrityError, match="uq_sessions_token_hash"):
        await database.run_in_transaction(lambda s: add_session(s, b"a" * 32))

    async def delete_user(session: AsyncSession) -> int:
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        return int(await session.scalar(text("SELECT count(*) FROM sessions")) or 0)

    assert await database.run_in_transaction(delete_user) == 0


async def test_cli_create_organizer_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, database_url: str, database: Database
) -> None:
    from app import cli

    apply_env(monkeypatch, base_env(DATABASE_URL=database_url))
    first = await cli.create_organizer()
    second = await cli.create_organizer()
    assert (first, second) == ("организатор создан", "организатор уже существует")
    assert await count_users(database) == 1
