"""vote.exception — исключения модуля голосов."""

from app.vote.exception.errors import OwnIdeaVoteError, VotingClosedError

__all__ = ["OwnIdeaVoteError", "VotingClosedError"]
