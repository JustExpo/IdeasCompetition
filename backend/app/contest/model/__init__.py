"""contest.model — доменные модели конкурса."""

from app.contest.model.contest import (
    DESCRIPTION_MAX_LENGTH,
    TIE_BREAK_RULE_TEXT,
    TOPIC_MAX_LENGTH,
    Contest,
    ContestPhase,
    ContestRound,
    ContestSchedule,
    NewContest,
)
from app.contest.model.details import ContestDetails
from app.contest.model.policy import (
    ContestAction,
    allowed_actions,
    can_submit_ideas,
    can_view_authors,
    can_view_results,
    can_vote_in_contest,
)

__all__ = [
    "DESCRIPTION_MAX_LENGTH",
    "TIE_BREAK_RULE_TEXT",
    "TOPIC_MAX_LENGTH",
    "Contest",
    "ContestAction",
    "ContestDetails",
    "ContestPhase",
    "ContestRound",
    "ContestSchedule",
    "NewContest",
    "allowed_actions",
    "can_submit_ideas",
    "can_view_authors",
    "can_view_results",
    "can_vote_in_contest",
]
