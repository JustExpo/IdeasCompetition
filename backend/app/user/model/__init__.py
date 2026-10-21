"""user.model — доменные модели пользователя."""

from app.user.model.registration import (
    USER_NAME_MAX_LENGTH,
    Registration,
    ensure_registration_valid,
)
from app.user.model.user import EnsuredUser, User, UserCredentials, UserRole, normalize_email

__all__ = [
    "USER_NAME_MAX_LENGTH",
    "EnsuredUser",
    "Registration",
    "User",
    "UserCredentials",
    "UserRole",
    "ensure_registration_valid",
    "normalize_email",
]
