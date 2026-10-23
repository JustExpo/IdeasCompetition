from datetime import timedelta
from itertools import pairwise
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

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


@given(
    rows=st.lists(st.tuples(st.integers(0, 5), st.integers(0, 5)), min_size=1, max_size=12).flatmap(
        lambda pairs: st.permutations(list(enumerate(pairs, start=1)))
    )
)
def test_ranking_does_not_depend_on_input_order(rows: list[tuple[int, tuple[int, int]]]) -> None:
    scores = [score(n, votes, minutes) for n, (votes, minutes) in rows]
    ranking = rank_ideas(scores)
    assert ranking == rank_ideas(sorted(scores, key=lambda s: str(s.idea_id)))
    assert [r.place for r in ranking] == list(range(1, len(scores) + 1))
    # П10: у соседей по месту голоса не растут, а при равенстве раньше поданная выше.
    for upper, lower in pairwise(ranking):
        assert (-upper.score.votes, upper.score.submitted_at) <= (
            -lower.score.votes,
            lower.score.submitted_at,
        )
