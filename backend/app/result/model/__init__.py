"""result.model — доменные модели итогов конкурса."""

from app.result.model.finalization import (
    FinalRecipients,
    has_tie_for_first,
    select_final_recipients,
)
from app.result.model.policy import can_view_authors, ensure_can_view_results
from app.result.model.ranking import ContestResults, IdeaScore, RankedIdea, rank_ideas
from app.result.model.view import ContestResultsView

__all__ = [
    "ContestResults",
    "ContestResultsView",
    "FinalRecipients",
    "IdeaScore",
    "RankedIdea",
    "can_view_authors",
    "ensure_can_view_results",
    "has_tie_for_first",
    "rank_ideas",
    "select_final_recipients",
]
