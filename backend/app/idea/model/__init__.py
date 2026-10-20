"""idea.model — доменные модели идеи."""

from app.idea.model.idea import (
    DESCRIPTION_MAX_LENGTH,
    IDEAS_PER_AUTHOR_LIMIT,
    IDEAS_PER_CONTEST_LIMIT,
    TITLE_MAX_LENGTH,
    Idea,
    IdeaContent,
)

__all__ = [
    "DESCRIPTION_MAX_LENGTH",
    "IDEAS_PER_AUTHOR_LIMIT",
    "IDEAS_PER_CONTEST_LIMIT",
    "TITLE_MAX_LENGTH",
    "Idea",
    "IdeaContent",
]
