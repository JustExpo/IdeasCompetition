"""Сквозные проверки HTTP-слоя `create_app` без БД: формат ошибок, прослойки, Origin."""

import json
import re
import uuid
from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI, Request, Response
from pydantic import BaseModel, ConfigDict
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.exception import DomainValidationError
from app.core.access import (
    Policy,
    RequirePolicy,
    RoutePolicyError,
    ensure_routes_have_policy,
    require,
)
from app.core.config import Settings
from app.core.middleware import (
    MAX_BODY_BYTES,
    BodyGuardMiddleware,
    OriginGuardMiddleware,
    RequestContextMiddleware,
)
from app.main import create_app
from tests.fakes import ReadyDatabase

from .test_config import apply_env, base_env, clean_env  # noqa: F401 — clean_env: autouse-фикстура

ORIGIN = "http://127.0.0.1:8000"
JSON_HEADERS = {"Origin": ORIGIN, "Content-Type": "application/json"}
SECRET_VALUE = "zz-secret-value-77"
DB_URL = "postgresql+asyncpg://ideas@127.0.0.1:1/ideas"


class Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


def build_probe_router() -> APIRouter:
    router = APIRouter(prefix="/api/_probe")

    @router.post("/echo", dependencies=[require(Policy.PUBLIC)])
    async def echo(payload: Echo) -> dict[str, int]:
        return {"count": payload.count}

    @router.get("/boom", dependencies=[require(Policy.PUBLIC)])
    async def boom() -> None:
        raise RuntimeError(f"SELECT * FROM ideas WHERE secret = '{SECRET_VALUE}'")  # noqa: S608

    @router.get("/domain", dependencies=[require(Policy.PUBLIC)])
    async def domain() -> None:
        raise DomainValidationError("Название слишком длинное.")

    @router.get("/secure", dependencies=[require(Policy.EMPLOYEE)])
    async def secure() -> dict[str, str]:
        return {"status": "ok"}

    return router


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    apply_env(monkeypatch, base_env())
    application = create_app(Settings(), database=ReadyDatabase(DB_URL))
    application.include_router(build_probe_router())
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # raise_app_exceptions=False: ответ 500 проверяем как клиент, а не ловим исключение сервера.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as http:
        yield http


def assert_problem(response: httpx.Response, status: int, code: str) -> dict[str, object]:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, object] = response.json()
    assert body["status"] == status
    assert body["code"] == code
    assert isinstance(body["title"], str)
    assert body["title"]
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert isinstance(body["errors"], list)
    return body


async def test_health_is_public_and_carries_security_headers(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    uuid.UUID(response.headers["X-Request-ID"])


async def test_client_request_id_is_kept_when_format_is_valid(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.parametrize("value", ["bad id with spaces", "x" * 65, "idé", "a;b"])
async def test_client_request_id_of_foreign_format_is_replaced(
    client: httpx.AsyncClient, value: str
) -> None:
    response = await client.get("/api/health", headers={b"X-Request-ID": value.encode()})

    uuid.UUID(response.headers["X-Request-ID"])


async def test_400_for_malformed_json(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/_probe/echo", content=b'{"count": ', headers=JSON_HEADERS)

    assert_problem(response, 400, "invalid_json")


async def test_401_when_policy_needs_login_and_no_auth_exists_yet(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/_probe/secure")

    assert_problem(response, 401, "not_authenticated")


async def test_403_for_unsafe_request_without_origin(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/_probe/echo", json={"count": 1}, headers={"Content-Type": "application/json"}
    )

    assert_problem(response, 403, "origin_not_allowed")


async def test_403_for_unsafe_request_from_foreign_origin(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/_probe/echo", json={"count": 1}, headers={"Origin": "https://evil.example"}
    )

    assert_problem(response, 403, "origin_not_allowed")


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
async def test_every_unsafe_method_needs_origin(client: httpx.AsyncClient, method: str) -> None:
    response = await client.request(method, "/api/_probe/echo")

    assert_problem(response, 403, "origin_not_allowed")


async def test_safe_request_without_origin_passes(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200


async def test_unsafe_request_from_own_origin_passes(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/_probe/echo", json={"count": 7}, headers={"Origin": ORIGIN})

    assert response.status_code == 200
    assert response.json() == {"count": 7}


async def test_dev_frontend_origin_is_allowed_only_in_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_env(
        monkeypatch, base_env(APP_ENV="e2e", DATABASE_URL=base_env()["DATABASE_URL"] + "_e2e")
    )
    application = create_app(Settings(), database=ReadyDatabase(DB_URL))
    application.include_router(build_probe_router())
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as http:
        response = await http.post(
            "/api/_probe/echo", json={"count": 1}, headers={"Origin": "http://localhost:5173"}
        )

    assert_problem(response, 403, "origin_not_allowed")


async def test_404_for_unknown_path(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/nope")

    assert_problem(response, 404, "not_found")


async def test_405_for_wrong_method(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/health", headers={"Origin": ORIGIN})

    assert_problem(response, 405, "method_not_allowed")


async def test_413_when_content_length_exceeds_limit(client: httpx.AsyncClient) -> None:
    payload = json.dumps({"count": 1, "pad": "x" * MAX_BODY_BYTES})

    response = await client.post("/api/_probe/echo", content=payload, headers=JSON_HEADERS)

    assert_problem(response, 413, "payload_too_large")


async def test_413_when_chunked_body_exceeds_limit_without_content_length(
    client: httpx.AsyncClient,
) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(3):
            yield b" " * (MAX_BODY_BYTES // 2)

    response = await client.post("/api/_probe/echo", content=chunks(), headers=JSON_HEADERS)

    assert_problem(response, 413, "payload_too_large")


async def test_body_of_exactly_the_limit_is_not_rejected_as_too_large(
    client: httpx.AsyncClient,
) -> None:
    head = b'{"count": 1}'
    payload = head + b" " * (MAX_BODY_BYTES - len(head))

    response = await client.post("/api/_probe/echo", content=payload, headers=JSON_HEADERS)

    assert response.status_code == 200


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded"])
async def test_415_for_non_json_body(client: httpx.AsyncClient, content_type: str) -> None:
    response = await client.post(
        "/api/_probe/echo",
        content=b"count=1",
        headers={"Origin": ORIGIN, "Content-Type": content_type},
    )

    assert_problem(response, 415, "unsupported_media_type")


async def test_415_for_multipart_upload(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/_probe/echo", files={"file": ("a.txt", b"data")}, headers={"Origin": ORIGIN}
    )

    assert_problem(response, 415, "unsupported_media_type")


async def test_json_content_type_with_charset_is_accepted(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/_probe/echo",
        content=b'{"count": 2}',
        headers={"Origin": ORIGIN, "Content-Type": "application/json; charset=utf-8"},
    )

    assert response.status_code == 200


async def test_empty_body_needs_no_content_type(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/_probe/echo", headers={"Origin": ORIGIN})

    # Тело пустое, поэтому 415 нет; обязательное поле не прислано, поэтому 422 от приложения.
    assert_problem(response, 422, "validation_error")


async def test_422_lists_fields_without_echoing_sent_values(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/_probe/echo", json={"count": SECRET_VALUE, "extra": 1}, headers={"Origin": ORIGIN}
    )

    body = assert_problem(response, 422, "validation_error")
    assert SECRET_VALUE not in response.text
    assert body["errors"] == [
        {"field": "count", "code": "int_parsing"},
        {"field": "extra", "code": "extra_forbidden"},
    ]


async def test_app_error_is_translated_by_its_code_and_status(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/_probe/domain")

    body = assert_problem(response, 422, "validation_error")
    assert body["title"] == "Название слишком длинное."


async def test_500_hides_stack_and_internal_details(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/_probe/boom")

    body = assert_problem(response, 500, "internal_error")
    assert SECRET_VALUE not in response.text
    assert "SELECT" not in response.text
    assert "Traceback" not in response.text
    assert body["detail"] is None


async def test_every_problem_has_a_stable_shape(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/nope")

    assert set(response.json()) == {
        "type",
        "title",
        "status",
        "code",
        "detail",
        "request_id",
        "errors",
    }
    assert re.fullmatch(r"urn:ideas-competition:error:[a-z_]+", response.json()["type"])


@pytest.fixture
def bare_app() -> FastAPI:
    return FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


def test_create_app_passes_its_own_route_check(app: FastAPI) -> None:
    ensure_routes_have_policy(app)


def test_route_without_policy_fails_with_its_path(bare_app: FastAPI) -> None:
    @bare_app.get("/api/forgotten")
    async def forgotten() -> None: ...

    with pytest.raises(RoutePolicyError, match="/api/forgotten"):
        ensure_routes_have_policy(bare_app)


def test_public_route_outside_allow_list_fails(bare_app: FastAPI) -> None:
    @bare_app.get("/api/secret-but-public", dependencies=[require(Policy.PUBLIC)])
    async def leaked() -> None: ...

    with pytest.raises(RoutePolicyError, match="allow-list"):
        ensure_routes_have_policy(bare_app)


def test_policy_set_on_router_counts_for_its_routes(bare_app: FastAPI) -> None:
    router = APIRouter(dependencies=[require(Policy.ORGANIZER)])

    @router.get("/api/organizer/ping")
    async def ping() -> None: ...

    bare_app.include_router(router)

    ensure_routes_have_policy(bare_app)


def test_routes_outside_api_need_no_policy(bare_app: FastAPI) -> None:
    @bare_app.get("/assets/app.js")
    async def asset() -> None: ...

    ensure_routes_have_policy(bare_app)


def test_websocket_route_without_policy_fails(bare_app: FastAPI) -> None:
    @bare_app.websocket("/api/contests/1/events")
    async def events() -> None: ...

    with pytest.raises(RoutePolicyError, match="/api/contests/1/events"):
        ensure_routes_have_policy(bare_app)


def test_all_problems_are_reported_at_once(bare_app: FastAPI) -> None:
    @bare_app.get("/api/one")
    async def one() -> None: ...

    @bare_app.get("/api/two")
    async def two() -> None: ...

    with pytest.raises(RoutePolicyError) as info:
        ensure_routes_have_policy(bare_app)

    assert "/api/one" in str(info.value)
    assert "/api/two" in str(info.value)


def test_plain_starlette_route_under_api_fails(bare_app: FastAPI) -> None:
    async def plain(_request: Request) -> Response:
        return Response()

    bare_app.router.routes.append(Route("/api/plain", plain))

    with pytest.raises(RoutePolicyError, match="/api/plain"):
        ensure_routes_have_policy(bare_app)


def test_route_with_other_dependencies_besides_policy_passes(bare_app: FastAPI) -> None:
    async def other_dependency() -> None: ...

    @bare_app.get(
        "/api/organizer/other",
        dependencies=[Depends(other_dependency), require(Policy.ORGANIZER)],
    )
    async def other() -> None: ...

    ensure_routes_have_policy(bare_app)


async def test_require_policy_public_lets_request_through() -> None:
    await RequirePolicy(Policy.PUBLIC)()


@pytest.mark.parametrize(
    "build",
    [
        lambda app: RequestContextMiddleware(app),
        lambda app: OriginGuardMiddleware(app, allowed_origins=[ORIGIN]),
        lambda app: BodyGuardMiddleware(app),
    ],
    ids=["context", "origin", "body"],
)
async def test_middlewares_pass_non_http_scopes_through(
    build: Callable[[ASGIApp], ASGIApp],
) -> None:
    seen: list[str] = []

    async def inner(scope: Scope, _receive: Receive, _send: Send) -> None:
        seen.append(scope["type"])

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(_message: Message) -> None: ...

    await build(inner)({"type": "lifespan"}, receive, send)

    assert seen == ["lifespan"]


async def test_body_guard_passes_non_request_messages_through() -> None:
    async def inner(_scope: Scope, receive: Receive, send: Send) -> None:
        await send(await receive())

    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    await BodyGuardMiddleware(inner)(scope, receive, send)

    assert sent == [{"type": "http.disconnect"}]
