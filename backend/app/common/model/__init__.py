"""common.model — общие типы доменных моделей."""

from app.common.model.password import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    is_password_length_valid,
    normalize_password,
)
from app.common.model.text import MULTILINE_ALLOWED, has_forbidden_chars, normalize_text
from app.common.model.types import ContestId, IdeaId, UserId, require_aware

__all__ = [
    "MULTILINE_ALLOWED",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_LENGTH",
    "ContestId",
    "IdeaId",
    "UserId",
    "has_forbidden_chars",
    "is_password_length_valid",
    "normalize_password",
    "normalize_text",
    "require_aware",
]
