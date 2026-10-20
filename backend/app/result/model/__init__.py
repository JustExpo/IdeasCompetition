"""result.model — доменные модели итогов конкурса."""

from app.result.model.ranking import ContestResults, IdeaScore, RankedIdea, rank_ideas

__all__ = ["ContestResults", "IdeaScore", "RankedIdea", "rank_ideas"]
