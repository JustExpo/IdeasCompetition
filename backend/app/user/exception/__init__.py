"""user.exception — исключения модуля пользователей."""

from app.user.exception.errors import (
    EmailDomainNotAllowedError,
    EmailTakenError,
    OrganizerCannotParticipateError,
)

__all__ = ["EmailDomainNotAllowedError", "EmailTakenError", "OrganizerCannotParticipateError"]
