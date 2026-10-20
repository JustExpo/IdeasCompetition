"""Ошибки входа. Нет сессии (401) и запрет по роли (403) — общие, в `app.common.exception`."""

from app.common.exception import AppError


class InvalidCredentialsError(AppError):
    """Неверный e-mail или пароль. Текст не уточняет, что именно, чтобы не раскрывать аккаунты."""

    code = "invalid_credentials"
    status = 401
