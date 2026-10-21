"""user.model — доменные модели пользователя."""

from app.common.model import UserRole  # живёт в common: политики других модулей его используют
from app.user.model.registration import (
    USER_NAME_MAX_LENGTH,
    Registration,
    ensure_registration_valid,
)
from app.user.model.user import EnsuredUser, User, UserCredentials, normalize_email

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
