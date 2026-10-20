"""Перевод исключений в `application/problem+json` (CLAUDE.md §8.1).

Единственное место, где исключение становится HTTP-ответом. Тело ошибки никогда не
содержит стека, SQL и присланных значений полей: они могут быть паролями или текстами идей.
"""

from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exception import AppError, InvalidJsonError
from app.core.logging import get_logger

PROBLEM_CONTENT_TYPE = "application/problem+json"
REQUEST_ID_HEADER = "X-Request-ID"

_log = get_logger(__name__)

# Тексты для ошибок, которые рождает сам Starlette (нет маршрута, метод).
_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    401: ("not_authenticated", "Требуется вход в систему."),
    403: ("forbidden", "Недостаточно прав."),
    404: ("not_found", "Не найдено."),
    405: ("method_not_allowed", "Метод не поддерживается."),
}


def build_problem(
    *,
    status: int,
    code: str,
    title: str,
    request_id: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:ideas-competition:error:{code}",
        "title": title,
        "status": status,
        "code": code,
        "detail": None,
        "request_id": request_id,
        "errors": errors or [],
    }
    return JSONResponse(
        body,
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
        headers={REQUEST_ID_HEADER: request_id},
    )


def request_id_of(request: Request) -> str:
    return str(request.scope.get("state", {}).get("request_id", "-"))


def _problem_for_app_error(request: Request, error: AppError) -> JSONResponse:
    return build_problem(
        status=error.status,
        code=error.code,
        title=error.message,
        request_id=request_id_of(request),
    )


def _problem_for_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    code, title = _HTTP_ERRORS.get(
        error.status_code, ("http_error", HTTPStatus(error.status_code).phrase)
    )
    return build_problem(
        status=error.status_code, code=code, title=title, request_id=request_id_of(request)
    )


def _problem_for_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    details = error.errors()
    if any(item["type"] == "json_invalid" for item in details):
        return _problem_for_app_error(request, InvalidJsonError("Тело запроса — неверный JSON."))
    # Только путь к полю и тип ошибки: сообщение pydantic может процитировать присланное значение.
    errors = [
        {
            "field": ".".join(str(part) for part in item["loc"] if part != "body"),
            "code": str(item["type"]),
        }
        for item in details
    ]
    return build_problem(
        status=422,
        code="validation_error",
        title="Некорректные данные запроса.",
        request_id=request_id_of(request),
        errors=errors,
    )


def _problem_for_unhandled_error(request: Request, error: Exception) -> JSONResponse:
    _log.error("unhandled_error", error_type=type(error).__name__, exc_info=error)
    return build_problem(
        status=500,
        code="internal_error",
        title="Внутренняя ошибка. Попробуйте позже.",
        request_id=request_id_of(request),
    )


def install_error_handlers(app: FastAPI) -> None:
    async def on_app_error(request: Request, error: Exception) -> JSONResponse:
        return _problem_for_app_error(request, cast(AppError, error))

    async def on_http_error(request: Request, error: Exception) -> JSONResponse:
        return _problem_for_http_error(request, cast(StarletteHTTPException, error))

    async def on_validation_error(request: Request, error: Exception) -> JSONResponse:
        return _problem_for_validation_error(request, cast(RequestValidationError, error))

    app.add_exception_handler(AppError, on_app_error)
    app.add_exception_handler(StarletteHTTPException, on_http_error)
    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(Exception, _problem_for_unhandled_error)
