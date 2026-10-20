from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.common.exception import DomainValidationError
from app.common.model import ContestId, IdeaId, UserId
from app.contest.exception import InvalidContestError
from app.contest.model import Contest, ContestPhase, ContestRound, ContestSchedule
from tests.unit.conftest import MICRO, T0

SUBMISSION = T0 + timedelta(days=3)
VOTING = T0 + timedelta(days=5)


def schedule() -> ContestSchedule:
    return ContestSchedule(submission_deadline=SUBMISSION, voting_deadline=VOTING)


def contest(**overrides: object) -> Contest:
    fields: dict[str, object] = dict(
        id=ContestId(1),
        topic="Как сократить совещания",
        description="",
        schedule=schedule(),
        created_by=UserId(1),
        created_at=T0,
    )
    fields.update(overrides)
    return Contest(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("now", "phase"),
    [
        (SUBMISSION - MICRO, ContestPhase.SUBMISSION),
        (SUBMISSION, ContestPhase.VOTING),  # дедлайн уже закрывает раунд
        (SUBMISSION + MICRO, ContestPhase.VOTING),
        (VOTING - MICRO, ContestPhase.VOTING),
        (VOTING, ContestPhase.FINISHED),
        (VOTING + MICRO, ContestPhase.FINISHED),
    ],
)
def test_phase_boundaries(now: datetime, phase: ContestPhase) -> None:
    assert schedule().phase_at(now) is phase


def test_phase_is_same_in_any_timezone() -> None:
    moscow = timezone(timedelta(hours=3))
    assert schedule().phase_at(SUBMISSION.astimezone(moscow)) is ContestPhase.VOTING


def test_phase_rejects_naive_now() -> None:
    with pytest.raises(DomainValidationError):
        schedule().phase_at(SUBMISSION.replace(tzinfo=None))


@pytest.mark.parametrize("voting", [SUBMISSION, SUBMISSION - MICRO])
def test_schedule_requires_voting_after_submission(voting: datetime) -> None:
    with pytest.raises(InvalidContestError):
        ContestSchedule(submission_deadline=SUBMISSION, voting_deadline=voting)


def test_schedule_rejects_naive_deadline() -> None:
    with pytest.raises(DomainValidationError):
        ContestSchedule(submission_deadline=SUBMISSION.replace(tzinfo=None), voting_deadline=VOTING)


def test_round_deadline() -> None:
    assert schedule().round_deadline(ContestRound.SUBMISSION) == SUBMISSION
    assert schedule().round_deadline(ContestRound.VOTING) == VOTING


@pytest.mark.parametrize("topic", ["", "   ", "x" * 201, "a‮b", "a\nb"])
def test_contest_rejects_bad_topic(topic: str) -> None:
    with pytest.raises(InvalidContestError):
        contest(topic=topic)


def test_contest_accepts_max_topic_and_multiline_description() -> None:
    assert contest(topic="x" * 200, description="строка 1\nстрока 2\t.").topic == "x" * 200


def test_winner_requires_finalization() -> None:
    with pytest.raises(InvalidContestError):
        contest(winner_idea_id=IdeaId(uuid4()))
    finalized = contest(finalized_at=VOTING, winner_idea_id=IdeaId(uuid4()))
    assert finalized.is_finalized
