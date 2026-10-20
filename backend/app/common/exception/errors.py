"""Базовые исключения. Каждое несёт стабильный код, по которому ветвится frontend."""

from typing import ClassVar


class AppError(Exception):
    """Ошибка приложения, понятная пользователю.

    `code` — стабильный lower_snake_case код из контракта API (CLAUDE.md §8.1),
    `status` — HTTP-статус, в который её переведёт handler.
    """

    code: ClassVar[str] = "app_error"
    status: ClassVar[int] = 400
    retry_after: ClassVar[int | None] = None  # секунды для заголовка Retry-After (429, 503)

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DomainValidationError(AppError):
    """Данные нарушают правило предметной области."""

    code = "validation_error"
    status = 422


class InvalidJsonError(AppError):
    """Тело запроса не разбирается как JSON."""

    code = "invalid_json"
    status = 400


class NotAuthenticatedError(AppError):
    """Нет действующей сессии."""

    code = "not_authenticated"
    status = 401


class ForbiddenError(AppError):
    """Роль не позволяет действие (политика маршрута)."""

    code = "forbidden"
    status = 403


class OrganizerCannotParticipateError(ForbiddenError):
    """Организатор видит результаты заранее, поэтому не подаёт идеи и не голосует."""

    code = "organizer_cannot_participate"


class OriginNotAllowedError(AppError):
    """Изменяющий запрос пришёл без `Origin` или с чужим `Origin` (защита от CSRF)."""

    code = "origin_not_allowed"
    status = 403


class PayloadTooLargeError(AppError):
    """Тело запроса больше допустимого."""

    code = "payload_too_large"
    status = 413


class UnsupportedMediaTypeError(AppError):
    """Непустое тело не в формате JSON."""

    code = "unsupported_media_type"
    status = 415


class ServiceUnavailableError(AppError):
    """База данных недоступна или перегружена; клиент может повторить запрос позже."""

    code = "service_unavailable"
    status = 503
    retry_after = 5
