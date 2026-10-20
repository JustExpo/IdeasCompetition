"""Ошибки голосования."""

from app.common.exception import AppError


class VotingClosedError(AppError):
    code = "voting_closed"
    status = 409


class OwnIdeaVoteError(AppError):
    code = "own_idea_vote"
    status = 403
