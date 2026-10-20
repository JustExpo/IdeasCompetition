from datetime import timedelta
from uuid import UUID

from app.common.model import ContestId, IdeaId, UserId
from app.result.model import ContestResults, IdeaScore, rank_ideas
from tests.unit.conftest import T0


def score(n: int, votes: int, submitted_offset_min: int) -> IdeaScore:
    return IdeaScore(
        idea_id=IdeaId(UUID(int=n)),
        title=f"Идея {n}",
        author_id=UserId(n),
        submitted_at=T0 + timedelta(minutes=submitted_offset_min),
        votes=votes,
    )


def test_more_votes_wins() -> None:
    ranking = rank_ideas([score(1, 2, 0), score(2, 5, 10)])
    assert [r.score.idea_id for r in ranking] == [UUID(int=2), UUID(int=1)]
    assert [r.place for r in ranking] == [1, 2]


def test_tie_goes_to_earlier_submission() -> None:
    ranking = rank_ideas([score(1, 3, 10), score(2, 3, 0)])
    assert ranking[0].score.idea_id == UUID(int=2)


def test_all_zero_votes_earliest_wins() -> None:
    ranking = rank_ideas([score(1, 0, 5), score(2, 0, 1), score(3, 0, 9)])
    assert ranking[0].score.idea_id == UUID(int=2)


def test_ranking_is_deterministic_on_full_tie() -> None:
    a, b = score(1, 1, 0), score(2, 1, 0)
    assert rank_ideas([a, b]) == rank_ideas([b, a])


def test_empty_contest_has_no_winner() -> None:
    assert ContestResults(ContestId(1), rank_ideas([]), is_final=True).winner is None
