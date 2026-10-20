"""ASGI-прослойки запроса (CLAUDE.md §8.1, §9.3, §13).

Чистый ASGI, а не `BaseHTTPMiddleware`: тот буферизует тело и ломает подсчёт его размера.
Порядок снаружи внутрь: контекст запроса → проверка `Origin` → проверка тела → приложение.
Поэтому ответы двух внутренних прослоек тоже получают `X-Request-ID` и заголовки безопасности.
"""

import re
import time
import uuid
from collections.abc import Collection

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.exception import (
    OriginNotAllowedError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.core.access import API_PREFIX
from app.core.http_errors import REQUEST_ID_HEADER, build_problem
from app.core.logging import bind_log_context, clear_log_context, get_logger

MAX_BODY_BYTES = 64 * 1024
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_log = get_logger(__name__)


def _request_id(headers: Headers) -> str:
    """Принять `X-Request-ID` клиента только строгого формата: он попадает в логи и ответы."""
    candidate = headers.get(REQUEST_ID_HEADER, "")
    return candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid.uuid4())


def _request_id_from_scope(scope: Scope) -> str:
    return str(scope.get("state", {}).get("request_id", "-"))


class RequestContextMiddleware:
    """`X-Request-ID`, контекст логов, заголовки безопасности, `no-store` и запись о запросе."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(Headers(scope=scope))
        scope.setdefault("state", {})["request_id"] = request_id
        bind_log_context(request_id=request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_headers(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                if scope["path"].startswith(API_PREFIX):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            route = scope.get("route")
            _log.info(
                "request",
                method=scope["method"],
                route=getattr(route, "path", "unmatched"),
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            clear_log_context()


class OriginGuardMiddleware:
    """CSRF: изменяющий запрос обязан прийти со своего `Origin`; одного SameSite=Lax мало."""

    def __init__(self, app: ASGIApp, allowed_origins: Collection[str]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            origin = Headers(scope=scope).get("origin")
            if origin not in self.allowed_origins:
                error = OriginNotAllowedError("Запрос отклонён: неизвестный источник.")
                response = build_problem(
                    status=error.status,
                    code=error.code,
                    title=error.message,
                    request_id=_request_id_from_scope(scope),
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class BodyGuardMiddleware:
    """Тело ≤ 64 КБ (413) и непустое тело только `application/json` (415)."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        declared = headers.get("content-length")
        chunked = "chunked" in headers.get("transfer-encoding", "").lower()
        has_body = chunked or (declared is not None and declared.strip() != "0")

        rejection: PayloadTooLargeError | UnsupportedMediaTypeError | None = None
        if declared is not None and declared.strip().isdigit() and int(declared) > self.max_bytes:
            rejection = PayloadTooLargeError("Тело запроса слишком большое.")
        elif has_body and not self._is_json(headers):
            rejection = UnsupportedMediaTypeError("Тело запроса должно быть в формате JSON.")
        if rejection is not None:
            response = build_problem(
                status=rejection.status,
                code=rejection.code,
                title=rejection.message,
                request_id=_request_id_from_scope(scope),
            )
            await response(scope, receive, send)
            return

        received = 0
        exceeded = False
        replaced = False

        async def receive_limited() -> Message:
            # Content-Length можно не указать или солгать: считаем фактические байты.
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise PayloadTooLargeError("Тело запроса слишком большое.")
            return message

        async def send_checked(message: Message) -> None:
            # FastAPI превращает любой сбой чтения тела в 400; для превышения лимита ответ
            # подменяется на 413, пока приложение ещё не успело отправить свой.
            nonlocal replaced
            if not exceeded:
                await send(message)
            elif not replaced:
                replaced = True
                await self._too_large_response(scope)(scope, receive, send)

        await self.app(scope, receive_limited, send_checked)

    def _too_large_response(self, scope: Scope) -> Response:
        error = PayloadTooLargeError("Тело запроса слишком большое.")
        return build_problem(
            status=error.status,
            code=error.code,
            title=error.message,
            request_id=_request_id_from_scope(scope),
        )

    @staticmethod
    def _is_json(headers: Headers) -> bool:
        media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        return media_type == "application/json"
