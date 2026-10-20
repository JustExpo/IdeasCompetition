"""common.model — общие типы доменных моделей."""

from app.common.model.text import MULTILINE_ALLOWED, has_forbidden_chars, normalize_text
from app.common.model.types import ContestId, IdeaId, UserId, require_aware

__all__ = [
    "MULTILINE_ALLOWED",
    "ContestId",
    "IdeaId",
    "UserId",
    "has_forbidden_chars",
    "normalize_text",
    "require_aware",
]
