"""common.exception — базовое исключение приложения и ошибки уровня запроса."""

from app.common.exception.errors import (
    AppError,
    DomainValidationError,
    ForbiddenError,
    InvalidJsonError,
    NotAuthenticatedError,
    OrganizerCannotParticipateError,
    OriginNotAllowedError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnsupportedMediaTypeError,
)

__all__ = [
    "AppError",
    "DomainValidationError",
    "ForbiddenError",
    "InvalidJsonError",
    "NotAuthenticatedError",
    "OrganizerCannotParticipateError",
    "OriginNotAllowedError",
    "PayloadTooLargeError",
    "ServiceUnavailableError",
    "UnsupportedMediaTypeError",
]
