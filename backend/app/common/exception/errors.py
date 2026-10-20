"""Базовые исключения. Каждое несёт стабильный код, по которому ветвится frontend."""

from typing import ClassVar


class AppError(Exception):
    """Ошибка приложения, понятная пользователю.

    `code` — стабильный lower_snake_case код из контракта API (CLAUDE.md §8.1),
    `status` — HTTP-статус, в который её переведёт handler.
    """

    code: ClassVar[str] = "app_error"
    status: ClassVar[int] = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DomainValidationError(AppError):
    """Данные нарушают правило предметной области."""

    code = "validation_error"
    status = 422
