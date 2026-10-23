"""Кому какое итоговое письмо и кому напоминание (Ф4, П9; IC-022, IC-023)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.common.model import IdeaId, UserId
from app.reminder.model import select_reminder_recipients
from app.result.model import (
    IdeaScore,
    has_tie_for_first,
    rank_ideas,
    select_final_recipients,
)

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def score(author: int, votes: int, minutes: int = 0) -> IdeaScore:
    return IdeaScore(
        idea_id=IdeaId(uuid4()),
        title="Идея",
        author_id=UserId(author),
        submitted_at=T0 + timedelta(minutes=minutes),
        votes=votes,
    )


def test_no_ideas_means_no_winner_and_no_emails() -> None:
    recipients = select_final_recipients((), {UserId(1)})

    assert (recipients.winner, recipients.not_passed, recipients.voters_only) == (None, (), ())


def test_each_person_gets_one_role() -> None:
    ranking = rank_ideas([score(1, votes=3), score(2, votes=1), score(2, votes=0, minutes=1)])

    recipients = select_final_recipients(ranking, {UserId(1), UserId(2), UserId(3)})

    assert recipients.winner == UserId(1)  # победитель, даже будучи ещё и голосующим
    assert recipients.not_passed == (UserId(2),)  # автор двух идей — одно письмо
    assert recipients.voters_only == (UserId(3),)


def test_author_of_winning_idea_among_several_is_winner_only() -> None:
    ranking = rank_ideas([score(1, votes=0), score(1, votes=5, minutes=1), score(2, votes=1)])

    recipients = select_final_recipients(ranking, set())

    assert recipients.winner == UserId(1)
    assert recipients.not_passed == (UserId(2),)


def test_tie_for_first_is_detected_only_for_equal_top_votes() -> None:
    assert has_tie_for_first(rank_ideas([score(1, 2), score(2, 2, 1)])) is True
    assert has_tie_for_first(rank_ideas([score(1, 3), score(2, 2, 1)])) is False
    assert has_tie_for_first(rank_ideas([score(1, 0)])) is False
    assert has_tie_for_first(()) is False


def test_reminder_recipients_exclude_participants() -> None:
    employees = [UserId(3), UserId(1), UserId(2)]

    assert select_reminder_recipients(employees, {UserId(2)}) == (UserId(1), UserId(3))
    assert select_reminder_recipients(employees, set()) == (UserId(1), UserId(2), UserId(3))
    assert select_reminder_recipients(employees, {UserId(1), UserId(2), UserId(3)}) == ()
    assert select_reminder_recipients([], {UserId(1)}) == ()
