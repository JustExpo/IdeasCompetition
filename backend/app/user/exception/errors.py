"""Ошибки регистрации и участия пользователя."""

from app.common.exception import AppError, OrganizerCannotParticipateError

__all__ = ["EmailDomainNotAllowedError", "EmailTakenError", "OrganizerCannotParticipateError"]


class EmailTakenError(AppError):
    code = "email_taken"
    status = 409


class EmailDomainNotAllowedError(AppError):
    code = "email_domain_not_allowed"
    status = 422
