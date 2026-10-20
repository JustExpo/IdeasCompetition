"""common.exception — базовое исключение приложения и ошибки уровня запроса."""

from app.common.exception.errors import (
    AppError,
    DomainValidationError,
    InvalidJsonError,
    NotAuthenticatedError,
    OriginNotAllowedError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnsupportedMediaTypeError,
)

__all__ = [
    "AppError",
    "DomainValidationError",
    "InvalidJsonError",
    "NotAuthenticatedError",
    "OriginNotAllowedError",
    "PayloadTooLargeError",
    "ServiceUnavailableError",
    "UnsupportedMediaTypeError",
]
