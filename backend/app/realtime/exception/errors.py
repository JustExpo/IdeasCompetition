"""Ошибки реального времени."""

from app.common.exception import AppError


class TooManyConnectionsError(AppError):
    """У пользователя уже открыто предельное число WebSocket-соединений (CLAUDE.md §9.3)."""

    code = "too_many_connections"
    status = 429
