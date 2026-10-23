"""result.service — сценарии итогов."""

from app.result.service.finalization import finalize_contest, finalize_due_contests
from app.result.service.results import get_results

__all__ = ["finalize_contest", "finalize_due_contests", "get_results"]
