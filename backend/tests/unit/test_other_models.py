from datetime import timedelta
from uuid import uuid4

import pytest

from app.auth.model import Actor, Session
from app.common.exception import DomainValidationError
from app.common.model import ContestId, IdeaId, UserId
from app.notification.model import EmailKind, EmailStatus, OutboxEmail
from app.realtime.model import ContestEvent, EventType
from app.reminder.model import reminder_window_contains
from app.user.model import User, UserRole
from tests.unit.conftest import MICRO, T0


def user(role: UserRole, is_active: bool = True) -> User:
    return User(UserId(1), "a@example.com", "Анна", role, is_active, T0)


def test_only_active_employee_participates() -> None:
    assert user(UserRole.EMPLOYEE).can_participate
    assert not user(UserRole.EMPLOYEE, is_active=False).can_participate
    assert not user(UserRole.ORGANIZER).can_participate


def test_user_repr_hides_personal_data() -> None:
    text = repr(user(UserRole.EMPLOYEE))
    assert "a@example.com" not in text
    assert "Анна" not in text


def test_session_validity_boundaries() -> None:
    session = Session(1, UserId(1), T0, T0 + timedelta(days=7))
    assert session.is_valid_at(T0 + timedelta(days=7) - MICRO)
    assert not session.is_valid_at(T0 + timedelta(days=7))
    revoked = Session(1, UserId(1), T0, T0 + timedelta(days=7), revoked_at=T0)
    assert not revoked.is_valid_at(T0)


def test_actor_role() -> None:
    assert Actor(UserId(1), UserRole.ORGANIZER).is_organizer
    assert not Actor(UserId(1), UserRole.EMPLOYEE).is_organizer


@pytest.mark.parametrize(
    ("now", "inside"),
    [
        (T0 - timedelta(hours=24) - MICRO, False),
        (T0 - timedelta(hours=24), True),
        (T0 - MICRO, True),
        (T0, False),
    ],
)
def test_reminder_window(now: object, inside: bool) -> None:
    assert reminder_window_contains(T0, now) is inside  # type: ignore[arg-type]


def test_outbox_email() -> None:
    email = OutboxEmail(
        id=1,
        dedup_key="voting_reminder:1:1",
        kind=EmailKind.VOTING_REMINDER,
        user_id=UserId(1),
        to_email="a@example.com",
        subject="Напоминание",
        body="Текст",
        status=EmailStatus.PENDING,
        attempts=0,
        next_attempt_at=T0,
        created_at=T0,
        not_after=T0 + timedelta(hours=1),
    )
    assert not email.is_expired_at(T0 + timedelta(hours=1) - MICRO)
    assert email.is_expired_at(T0 + timedelta(hours=1))
    assert "a@example.com" not in repr(email)
    assert {s for s in EmailStatus if s.is_terminal} == {
        EmailStatus.SENT,
        EmailStatus.FAILED,
        EmailStatus.EXPIRED,
    }


def test_event_invariants() -> None:
    ContestEvent(EventType.IDEAS_CHANGED, contest_id=ContestId(1))
    ContestEvent(EventType.SESSION_REVOKED)
    ContestEvent(EventType.IDEA_DELETED, contest_id=ContestId(1), idea_id=IdeaId(uuid4()))
    with pytest.raises(DomainValidationError):
        ContestEvent(EventType.IDEAS_CHANGED)
    with pytest.raises(DomainValidationError):
        ContestEvent(EventType.IDEA_DELETED, contest_id=ContestId(1))
