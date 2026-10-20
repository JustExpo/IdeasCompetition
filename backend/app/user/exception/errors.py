"""Ошибки регистрации и участия пользователя."""

from app.common.exception import AppError


class EmailTakenError(AppError):
    code = "email_taken"
    status = 409


class EmailDomainNotAllowedError(AppError):
    code = "email_domain_not_allowed"
    status = 422


class OrganizerCannotParticipateError(AppError):
    """Организатор видит результаты заранее, поэтому не подаёт идеи и не голосует."""

    code = "organizer_cannot_participate"
    status = 403
