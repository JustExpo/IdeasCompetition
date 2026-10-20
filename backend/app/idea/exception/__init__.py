"""idea.exception — исключения модуля идей."""

from app.idea.exception.errors import (
    ContestFullError,
    IdeaLimitReachedError,
    IdeaLockedError,
    IdeaNotFoundError,
    IdempotencyKeyReusedError,
    InvalidIdeaContentError,
    StaleIdeaVersionError,
    SubmissionClosedError,
)

__all__ = [
    "ContestFullError",
    "IdeaLimitReachedError",
    "IdeaLockedError",
    "IdeaNotFoundError",
    "IdempotencyKeyReusedError",
    "InvalidIdeaContentError",
    "StaleIdeaVersionError",
    "SubmissionClosedError",
]
