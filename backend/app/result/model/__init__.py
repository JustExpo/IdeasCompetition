"""result.model — доменные модели итогов конкурса."""

from app.result.model.policy import can_view_authors, ensure_can_view_results
from app.result.model.ranking import ContestResults, IdeaScore, RankedIdea, rank_ideas

__all__ = [
    "ContestResults",
    "IdeaScore",
    "RankedIdea",
    "can_view_authors",
    "ensure_can_view_results",
    "rank_ideas",
]
