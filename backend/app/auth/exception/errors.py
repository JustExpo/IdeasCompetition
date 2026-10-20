"""Ошибки входа. Нет сессии (401) и запрет по роли (403) — общие, в `app.common.exception`."""

from app.common.exception import AppError


class InvalidCredentialsError(AppError):
    """Неверный e-mail или пароль. Текст не уточняет, что именно, чтобы не раскрывать аккаунты."""

    code = "invalid_credentials"
    status = 401


class TooManyAttemptsError(AppError):
    """Слишком много попыток; клиент повторяет позже (заголовок Retry-After)."""

    code = "too_many_attempts"
    status = 429


class TooManyLoginAttemptsError(TooManyAttemptsError):
    retry_after = 15 * 60


class TooManyRegistrationsError(TooManyAttemptsError):
    retry_after = 60 * 60
