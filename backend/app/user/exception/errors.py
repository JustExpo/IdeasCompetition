"""Ошибки регистрации и участия пользователя."""

from app.common.exception import AppError, OrganizerCannotParticipateError

__all__ = [
    "EmailDomainNotAllowedError",
    "EmailTakenError",
    "InvalidEmailError",
    "InvalidNameError",
    "InvalidPasswordError",
    "OrganizerCannotParticipateError",
]


class EmailTakenError(AppError):
    code = "email_taken"
    status = 409


class EmailDomainNotAllowedError(AppError):
    code = "email_domain_not_allowed"
    status = 422


class InvalidEmailError(AppError):
    code = "invalid_email"
    status = 422


class InvalidNameError(AppError):
    code = "invalid_name"
    status = 422


class InvalidPasswordError(AppError):
    code = "invalid_password"
    status = 422
