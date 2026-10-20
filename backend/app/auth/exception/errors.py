"""Ошибки аутентификации (кто вы) и авторизации (что вам можно)."""

from app.common.exception import AppError


class AuthenticationRequiredError(AppError):
    """Нет сессии, она истекла или отозвана."""

    code = "authentication_required"
    status = 401


class InvalidCredentialsError(AppError):
    """Неверный e-mail или пароль. Текст не уточняет, что именно, чтобы не раскрывать аккаунты."""

    code = "invalid_credentials"
    status = 401


class ForbiddenError(AppError):
    """Роль не позволяет действие."""

    code = "forbidden"
    status = 403
