"""Таблицы истинности политик: фаза × роль × свой/чужой × активен, и границы дедлайнов (§10.3)."""

from datetime import UTC, datetime, timedelta
from itertools import product
from uuid import uuid4

import pytest

from app.common.exception import (
    NotAuthenticatedError,
    OrganizerCannotParticipateError,
)
from app.common.model import Actor, ContestId, IdeaId, UserId, UserRole
from app.contest.model import (
    ContestAction,
    ContestPhase,
    ContestSchedule,
    allowed_actions,
    can_submit_ideas,
    can_view_results,
    can_vote_in_contest,
)
from app.idea.exception import IdeaLockedError, IdeaNotFoundError, SubmissionClosedError
from app.idea.model import (
    Idea,
    IdeaContent,
    can_delete_idea,
    can_edit_idea,
    can_view_idea,
    ensure_can_delete_idea,
    ensure_can_edit_idea,
    ensure_can_submit_idea,
)
from app.result.exception import ResultsNotPublishedError
from app.result.model import can_view_authors, ensure_can_view_results
from app.vote.exception import OwnIdeaVoteError, VotingClosedError
from app.vote.model import (
    can_vote,
    can_withdraw_vote,
    ensure_can_vote,
    ensure_can_withdraw_vote,
)

SUB, VOT, FIN = ContestPhase.SUBMISSION, ContestPhase.VOTING, ContestPhase.FINISHED
PHASES = (SUB, VOT, FIN)
EMPLOYEE, ORGANIZER = UserRole.EMPLOYEE, UserRole.ORGANIZER
AUTHOR_ID, OTHER_ID = UserId(1), UserId(2)
T0 = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def actor(role: UserRole = EMPLOYEE, *, user_id: UserId = OTHER_ID, active: bool = True) -> Actor:
    return Actor(user_id=user_id, role=role, is_active=active)


def idea() -> Idea:
    return Idea(
        id=IdeaId(uuid4()),
        contest_id=ContestId(1),
        author_id=AUTHOR_ID,
        content=IdeaContent.create("Название", "Описание"),
        submitted_at=T0,
        updated_at=T0,
    )


# Явные таблицы, а не копия формул из кода: (роль, фаза) -> ожидаемый результат.
SUBMIT = {(EMPLOYEE, SUB): True, (EMPLOYEE, VOT): False, (EMPLOYEE, FIN): False}
VOTE = {(EMPLOYEE, SUB): False, (EMPLOYEE, VOT): True, (EMPLOYEE, FIN): False}
RESULTS = {
    (EMPLOYEE, SUB): False,
    (EMPLOYEE, VOT): False,
    (EMPLOYEE, FIN): True,
    (ORGANIZER, SUB): True,
    (ORGANIZER, VOT): True,
    (ORGANIZER, FIN): True,
}


@pytest.mark.parametrize(("role", "phase"), list(product((EMPLOYEE, ORGANIZER), PHASES)))
def test_contest_predicates_truth_table(role: UserRole, phase: ContestPhase) -> None:
    who = actor(role)
    assert can_submit_ideas(who, phase) is SUBMIT.get((role, phase), False)
    assert can_vote_in_contest(who, phase) is VOTE.get((role, phase), False)
    assert can_view_results(who, phase) is RESULTS[(role, phase)]


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("role", [EMPLOYEE, ORGANIZER])
def test_inactive_actor_is_denied_everything(role: UserRole, phase: ContestPhase) -> None:
    ghost = actor(role, active=False)
    the_idea = idea()
    assert not can_submit_ideas(ghost, phase)
    assert not can_vote_in_contest(ghost, phase)
    assert not can_view_results(ghost, phase)
    assert not can_view_authors(ghost, phase)
    assert not can_view_idea(ghost, the_idea, phase)
    assert not can_withdraw_vote(ghost, phase)
    assert allowed_actions(ghost, phase) == frozenset()
    assert not can_vote(ghost, the_idea, phase)
    own = actor(role, user_id=AUTHOR_ID, active=False)
    assert not can_edit_idea(own, the_idea, phase)
    assert not can_delete_idea(own, the_idea, phase)


@pytest.mark.parametrize(
    ("role", "phase", "expected"),
    [
        (EMPLOYEE, SUB, {ContestAction.SUBMIT_IDEA}),
        (EMPLOYEE, VOT, {ContestAction.VOTE}),
        (EMPLOYEE, FIN, {ContestAction.VIEW_RESULTS}),
        (ORGANIZER, SUB, {ContestAction.VIEW_RESULTS}),
        (ORGANIZER, VOT, {ContestAction.VIEW_RESULTS}),
        (ORGANIZER, FIN, {ContestAction.VIEW_RESULTS}),
    ],
)
def test_allowed_actions(role: UserRole, phase: ContestPhase, expected: set[ContestAction]) -> None:
    assert allowed_actions(actor(role), phase) == frozenset(expected)


@pytest.mark.parametrize("phase", PHASES)
def test_authors_are_revealed_only_after_the_final_for_everyone(phase: ContestPhase) -> None:
    expected = phase is FIN
    assert can_view_authors(actor(EMPLOYEE), phase) is expected
    assert can_view_authors(actor(ORGANIZER), phase) is expected  # организатору до финала — нет


@pytest.mark.parametrize(("is_author", "phase"), list(product((True, False), PHASES)))
def test_can_view_idea_truth_table(is_author: bool, phase: ContestPhase) -> None:
    who = actor(user_id=AUTHOR_ID if is_author else OTHER_ID)
    expected = is_author if phase is SUB else True  # приём: только свои (П3)
    assert can_view_idea(who, idea(), phase) is expected


@pytest.mark.parametrize("phase", PHASES)
def test_organizer_does_not_see_ideas_during_submission(phase: ContestPhase) -> None:
    assert can_view_idea(actor(ORGANIZER), idea(), phase) is (phase is not SUB)


@pytest.mark.parametrize(("is_author", "phase"), list(product((True, False), PHASES)))
def test_edit_and_delete_truth_table(is_author: bool, phase: ContestPhase) -> None:
    who = actor(user_id=AUTHOR_ID if is_author else OTHER_ID)
    assert can_edit_idea(who, idea(), phase) is (is_author and phase is SUB)
    assert can_delete_idea(who, idea(), phase) is (is_author and phase is not FIN)


@pytest.mark.parametrize("phase", PHASES)
def test_organizer_never_edits_or_deletes(phase: ContestPhase) -> None:
    who = actor(ORGANIZER, user_id=AUTHOR_ID)  # даже при совпадении id
    assert not can_edit_idea(who, idea(), phase)
    assert not can_delete_idea(who, idea(), phase)


@pytest.mark.parametrize(("is_author", "phase"), list(product((True, False), PHASES)))
def test_can_vote_truth_table(is_author: bool, phase: ContestPhase) -> None:
    who = actor(user_id=AUTHOR_ID if is_author else OTHER_ID)
    assert can_vote(who, idea(), phase) is ((not is_author) and phase is VOT)
    assert can_withdraw_vote(who, phase) is (phase is VOT)


@pytest.mark.parametrize("phase", PHASES)
def test_organizer_never_votes(phase: ContestPhase) -> None:
    assert not can_vote(actor(ORGANIZER), idea(), phase)
    assert not can_withdraw_vote(actor(ORGANIZER), phase)


# --- ensure_*: порядок ошибок 401 → 404 → 403 → 409 -------------------------------------------


@pytest.mark.parametrize("phase", [VOT, FIN])
def test_ensure_can_submit_idea_after_the_deadline(phase: ContestPhase) -> None:
    with pytest.raises(SubmissionClosedError):
        ensure_can_submit_idea(actor(), phase)


def test_ensure_can_submit_idea_ok_and_role_checks() -> None:
    ensure_can_submit_idea(actor(), SUB)
    with pytest.raises(OrganizerCannotParticipateError):
        ensure_can_submit_idea(actor(ORGANIZER), SUB)
    with pytest.raises(OrganizerCannotParticipateError):  # роль важнее фазы
        ensure_can_submit_idea(actor(ORGANIZER), FIN)
    with pytest.raises(NotAuthenticatedError):
        ensure_can_submit_idea(actor(active=False), SUB)


def test_ensure_can_edit_idea_order() -> None:
    mine = actor(user_id=AUTHOR_ID)
    ensure_can_edit_idea(mine, idea(), SUB)
    with pytest.raises(SubmissionClosedError):
        ensure_can_edit_idea(mine, idea(), VOT)
    with pytest.raises(IdeaNotFoundError):  # чужая идея — 404 раньше любой фазы
        ensure_can_edit_idea(actor(), idea(), FIN)
    with pytest.raises(OrganizerCannotParticipateError):
        ensure_can_edit_idea(actor(ORGANIZER, user_id=AUTHOR_ID), idea(), SUB)
    with pytest.raises(NotAuthenticatedError):
        ensure_can_edit_idea(actor(user_id=AUTHOR_ID, active=False), idea(), SUB)


def test_ensure_can_delete_idea_order() -> None:
    mine = actor(user_id=AUTHOR_ID)
    for phase in (SUB, VOT):
        ensure_can_delete_idea(mine, idea(), phase)
    with pytest.raises(IdeaLockedError):
        ensure_can_delete_idea(mine, idea(), FIN)
    with pytest.raises(IdeaNotFoundError):
        ensure_can_delete_idea(actor(), idea(), VOT)
    with pytest.raises(OrganizerCannotParticipateError):
        ensure_can_delete_idea(actor(ORGANIZER, user_id=AUTHOR_ID), idea(), VOT)
    with pytest.raises(NotAuthenticatedError):
        ensure_can_delete_idea(actor(user_id=AUTHOR_ID, active=False), idea(), VOT)


def test_ensure_can_vote_order() -> None:
    ensure_can_vote(actor(), idea(), VOT)
    with pytest.raises(OwnIdeaVoteError):  # своя идея — 403 раньше фазы
        ensure_can_vote(actor(user_id=AUTHOR_ID), idea(), FIN)
    for phase in (SUB, FIN):
        with pytest.raises(VotingClosedError):
            ensure_can_vote(actor(), idea(), phase)
    with pytest.raises(OrganizerCannotParticipateError):
        ensure_can_vote(actor(ORGANIZER), idea(), VOT)
    with pytest.raises(NotAuthenticatedError):
        ensure_can_vote(actor(active=False), idea(), VOT)


def test_ensure_can_withdraw_vote_order() -> None:
    ensure_can_withdraw_vote(actor(), VOT)
    for phase in (SUB, FIN):
        with pytest.raises(VotingClosedError):
            ensure_can_withdraw_vote(actor(), phase)
    with pytest.raises(OrganizerCannotParticipateError):
        ensure_can_withdraw_vote(actor(ORGANIZER), VOT)
    with pytest.raises(NotAuthenticatedError):
        ensure_can_withdraw_vote(actor(active=False), VOT)


def test_ensure_can_view_results() -> None:
    ensure_can_view_results(actor(ORGANIZER), SUB)
    ensure_can_view_results(actor(), FIN)
    for phase in (SUB, VOT):
        with pytest.raises(ResultsNotPublishedError):
            ensure_can_view_results(actor(), phase)
    with pytest.raises(NotAuthenticatedError):
        ensure_can_view_results(actor(ORGANIZER, active=False), FIN)


# --- границы дедлайнов: d−1µs / d / d+1µs для обоих дедлайнов ---------------------------------

D1 = T0 + timedelta(days=1)
D2 = T0 + timedelta(days=2)
SCHEDULE = ContestSchedule(submission_deadline=D1, voting_deadline=D2)
MICRO = timedelta(microseconds=1)


@pytest.mark.parametrize(
    ("moment", "phase"),
    [
        (D1 - MICRO, SUB),
        (D1, VOT),
        (D1 + MICRO, VOT),
        (D2 - MICRO, VOT),
        (D2, FIN),
        (D2 + MICRO, FIN),
    ],
)
def test_policies_follow_the_deadline_boundaries(moment: datetime, phase: ContestPhase) -> None:
    assert SCHEDULE.phase_at(moment) is phase
    employee = actor()
    assert can_submit_ideas(employee, SCHEDULE.phase_at(moment)) is (phase is SUB)
    assert can_vote_in_contest(employee, SCHEDULE.phase_at(moment)) is (phase is VOT)
    assert can_view_results(employee, SCHEDULE.phase_at(moment)) is (phase is FIN)
    assert can_view_authors(employee, SCHEDULE.phase_at(moment)) is (phase is FIN)
