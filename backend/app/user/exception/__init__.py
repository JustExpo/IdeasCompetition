"""user.exception — исключения модуля пользователей."""

from app.user.exception.errors import (
    EmailDomainNotAllowedError,
    EmailTakenError,
    InvalidEmailError,
    InvalidNameError,
    InvalidPasswordError,
    OrganizerCannotParticipateError,
)

__all__ = [
    "EmailDomainNotAllowedError",
    "EmailTakenError",
    "InvalidEmailError",
    "InvalidNameError",
    "InvalidPasswordError",
    "OrganizerCannotParticipateError",
]
