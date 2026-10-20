"""common.exception — базовое исключение приложения."""

from app.common.exception.errors import AppError, DomainValidationError

__all__ = ["AppError", "DomainValidationError"]
