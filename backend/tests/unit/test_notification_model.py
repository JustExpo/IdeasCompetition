"""Письма: пауза повтора, Message-ID, заголовки без инъекций, тексты (Р9; IC-021, IC-022)."""

from datetime import UTC, datetime, timedelta

import aiosmtplib
import pytest

from app.notification.exception import EmailDeliveryError
from app.notification.model import RETRY_DELAY_MAX, OutgoingEmail, retry_delay
from app.notification.service import (
    SmtpEmailSender,
    build_message,
    format_moment,
    render_not_passed_email,
    render_results_email,
    render_submission_reminder,
    render_voting_reminder,
    render_winner_email,
)

URL = "http://127.0.0.1:8000/contests/7"


def email(
    *, to: str = "anna@example.com", subject: str = "Тема", body: str = "Текст"
) -> OutgoingEmail:
    return OutgoingEmail(outbox_id=42, to_email=to, subject=subject, body=body)


@pytest.mark.parametrize(
    ("attempts", "minutes"), [(0, 1), (1, 2), (2, 4), (3, 8), (5, 32), (6, 60), (7, 60), (50, 60)]
)
def test_retry_delay_doubles_and_is_capped_at_one_hour(attempts: int, minutes: int) -> None:
    assert retry_delay(attempts) == timedelta(minutes=minutes)
    assert retry_delay(attempts) <= RETRY_DELAY_MAX


def test_message_id_is_deterministic_per_outbox_row() -> None:
    assert email().message_id == "<outbox-42@ideas-competition.local>"
    assert email().message_id == email(body="другой").message_id


def test_build_message_sets_headers() -> None:
    message = build_message(email(), "noreply@example.com")

    assert message["From"] == "noreply@example.com"
    assert message["To"] == "anna@example.com"
    assert message["Message-ID"] == "<outbox-42@ideas-competition.local>"
    assert message["Subject"] == "Тема"
    assert message.get_content().strip() == "Текст"


@pytest.mark.parametrize(
    "bad",
    [
        {"subject": "Тема\r\nBcc: victim@example.com"},
        {"subject": "Тема\nX-Evil: 1"},
        {"to": "anna@example.com\r\nBcc: victim@example.com"},
    ],
)
def test_header_injection_is_rejected_as_permanent(bad: dict[str, str]) -> None:
    with pytest.raises(EmailDeliveryError) as raised:
        build_message(email(**bad), "noreply@example.com")

    assert raised.value.permanent is True


@pytest.mark.parametrize(
    ("raised", "permanent"),
    [
        (aiosmtplib.SMTPResponseException(451, "try later"), False),
        (aiosmtplib.SMTPResponseException(550, "no such user"), True),
        (aiosmtplib.SMTPRecipientsRefused([]), True),
        (aiosmtplib.SMTPServerDisconnected("reset"), False),
        (aiosmtplib.SMTPConnectError("refused"), False),
        (TimeoutError(), False),
        (ConnectionResetError(), False),
    ],
)
async def test_smtp_errors_are_mapped_to_permanent_or_transient(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, permanent: bool
) -> None:
    async def fail(*_args: object, **_kwargs: object) -> None:
        raise raised

    monkeypatch.setattr(aiosmtplib, "send", fail)
    sender = SmtpEmailSender("mailpit", 1025, "noreply@example.com")

    with pytest.raises(EmailDeliveryError) as error:
        await sender.send(email())

    assert error.value.permanent is permanent
    assert "anna@example.com" not in error.value.message  # адрес не уходит в журнал


def test_format_moment_uses_display_timezone() -> None:
    moment = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    assert format_moment(moment, "Europe/Moscow") == "24.10.2026 15:00 (MSK)"


def test_final_emails_say_what_the_owner_asked() -> None:
    winner = render_winner_email(topic="Офис", idea_title="Кофе", votes=3, url=URL)
    lost = render_not_passed_email(topic="Офис", winner_title="Кофе", tie_rule=None, url=URL)
    voter = render_results_email(topic="Офис", winner_title="Кофе", url=URL)

    assert winner.subject.startswith("Вы победили")
    assert "Голосов за неё: 3" in winner.body
    assert lost.subject.startswith("Ваша идея не прошла")
    assert "Кофе" in lost.body
    assert voter.subject.startswith("Итоги конкурса")
    assert all(URL in mail.body for mail in (winner, lost, voter))


def test_tie_rule_is_shown_only_when_given() -> None:
    rule = "При равенстве голосов побеждает идея, поданная раньше."

    with_rule = render_not_passed_email(topic="Т", winner_title="И", tie_rule=rule, url=URL)
    without = render_not_passed_email(topic="Т", winner_title="И", tie_rule=None, url=URL)

    assert rule in with_rule.body
    assert "равенстве" not in without.body


def test_reminders_show_deadline_in_display_timezone() -> None:
    deadline = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    submit = render_submission_reminder(
        topic="Офис", deadline=deadline, display_tz="Europe/Moscow", url=URL
    )
    vote = render_voting_reminder(
        topic="Офис", deadline=deadline, display_tz="Europe/Moscow", url=URL
    )

    assert "24.10.2026 15:00 (MSK)" in submit.body
    assert "приём идей" in submit.subject
    assert "24.10.2026 15:00 (MSK)" in vote.body
    assert "голосование" in vote.subject
