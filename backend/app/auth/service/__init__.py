"""auth.service — вход, выход, сессии и организатор из окружения."""

from app.auth.service.organizer import ensure_organizer
from app.auth.service.passwords import PasswordService
from app.auth.service.sessions import (
    SESSION_LIFETIME,
    IssuedSession,
    get_current_user,
    hash_session_token,
    log_in,
    log_out,
    resolve_actor,
)

__all__ = [
    "SESSION_LIFETIME",
    "IssuedSession",
    "PasswordService",
    "ensure_organizer",
    "get_current_user",
    "hash_session_token",
    "log_in",
    "log_out",
    "resolve_actor",
]
