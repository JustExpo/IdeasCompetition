"""Outbox: постановка, отправка, повторы, срок годности (Р9, О10; IC-021)."""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId
from app.core.db import Database
from app.notification import dao as notification_dao
from app.notification import service as notification_service
from app.notification.dao import OutboxEmailRow
from app.notification.model import (
    BATCH_SIZE,
    LEASE_DURATION,
    MAX_ATTEMPTS,
    EmailKind,
    EmailStatus,
    retry_delay,
)
from tests.fakes import FakeMailSender, FrozenClock, SendMode
from tests.integration.contests.conftest import NOW, Person
from tests.integration.contests.mailbox import outbox_rows

pytestmark = pytest.mark.commits


async def enqueue(
    database: Database,
    clock: FrozenClock,
    person: Person,
    *,
    contest_id: int = 1,
    kind: EmailKind = EmailKind.RESULTS_ANNOUNCEMENT,
    not_after_in: timedelta | None = None,
    email: str | None = None,
) -> bool:
    async def work(session: AsyncSession) -> bool:
        return await notification_service.enqueue_email(
            session,
            kind=kind,
            contest_id=ContestId(contest_id),
            user_id=person.id,
            to_email=email or f"{person.name.lower()}@example.com",
            subject="Тема",
            body="Текст",
            now=clock.now(),
            not_after=None if not_after_in is None else clock.now() + not_after_in,
        )

    return await database.run_in_transaction(work)


async def only_row(database: Database) -> OutboxEmailRow:
    rows = await outbox_rows(database)
    assert len(rows) == 1
    return rows[0]


async def test_duplicate_dedup_key_creates_one_email(
    database: Database, clock: FrozenClock, anna: Person
) -> None:
    assert await enqueue(database, clock, anna) is True
    assert await enqueue(database, clock, anna) is False

    assert len(await outbox_rows(database)) == 1


async def test_successful_delivery_marks_sent(
    database: Database, clock: FrozenClock, anna: Person
) -> None:
    sender = FakeMailSender()
    await enqueue(database, clock, anna)

    report = await notification_service.deliver_due_emails(database, clock, sender)

    row = await only_row(database)
    assert report.sent == 1
    assert row.status == EmailStatus.SENT.value
    assert row.sent_at == NOW
    assert row.lease_until is None
    assert row.attempts == 1
    assert sender.sent[0].message_id == f"<outbox-{row.id}@ideas-competition.local>"


@pytest.mark.parametrize(
    "mode", [SendMode.REJECT_4XX, SendMode.TIMEOUT, SendMode.DISCONNECT, SendMode.GARBLED]
)
async def test_transient_failure_schedules_retry_with_backoff(
    database: Database, clock: FrozenClock, anna: Person, mode: SendMode
) -> None:
    sender = FakeMailSender(mode)
    await enqueue(database, clock, anna)

    report = await notification_service.deliver_due_emails(database, clock, sender)

    row = await only_row(database)
    assert report.retried == 1
    assert row.status == EmailStatus.PENDING.value
    assert row.attempts == 1
    assert row.next_attempt_at == NOW + retry_delay(1)
    assert row.last_error is not None
    assert "@" not in row.last_error  # адрес не попадает в сохранённую ошибку

    # До срока повтора письмо не трогают, после — отправляют.
    sender.mode = SendMode.OK
    assert (await notification_service.deliver_due_emails(database, clock, sender)).sent == 0
    clock.advance(retry_delay(1))
    assert (await notification_service.deliver_due_emails(database, clock, sender)).sent == 1
    assert (await only_row(database)).status == EmailStatus.SENT.value


async def test_permanent_rejection_fails_without_retry(
    database: Database, clock: FrozenClock, anna: Person
) -> None:
    sender = FakeMailSender(SendMode.REJECT_5XX)
    await enqueue(database, clock, anna)

    report = await notification_service.deliver_due_emails(database, clock, sender)

    assert report.failed == 1
    assert (await only_row(database)).status == EmailStatus.FAILED.value
    clock.advance(timedelta(days=1))
    await notification_service.deliver_due_emails(database, clock, sender)
    assert sender.attempts == 1


async def test_email_fails_after_max_attempts(
    database: Database, clock: FrozenClock, anna: Person
) -> None:
    sender = FakeMailSender(SendMode.REJECT_4XX)
    await enqueue(database, clock, anna)

    for _ in range(MAX_ATTEMPTS):
        await notification_service.deliver_due_emails(database, clock, sender)
        clock.advance(timedelta(hours=2))

    row = await only_row(database)
    assert row.status == EmailStatus.FAILED.value
    assert row.attempts == MAX_ATTEMPTS
    assert sender.attempts == MAX_ATTEMPTS


async def test_expired_email_is_not_sent(
    database: Database, clock: FrozenClock, anna: Person
) -> None:
    sender = FakeMailSender()
    await enqueue(database, clock, anna, not_after_in=timedelta(hours=1))
    clock.advance(timedelta(hours=1))  # ровно not_after: письмо уже бессмысленно

    report = await notification_service.deliver_due_emails(database, clock, sender)

    assert report.expired == 1
    assert sender.attempts == 0
    assert (await only_row(database)).status == EmailStatus.EXPIRED.value


async def test_batch_is_limited_and_failure_of_one_does_not_block_others(
    database: Database, clock: FrozenClock, anna: Person, boris: Person
) -> None:
    sender = FakeMailSender()
    sender.failing_recipients = {"anna@example.com"}
    await enqueue(database, clock, anna)
    await enqueue(database, clock, boris)

    report = await notification_service.deliver_due_emails(database, clock, sender)

    assert (report.sent, report.retried) == (1, 1)
    assert sender.recipients() == ["boris@example.com"]


async def test_batch_size_is_twenty(database: Database, clock: FrozenClock, anna: Person) -> None:
    sender = FakeMailSender()
    for contest_id in range(1, BATCH_SIZE + 6):
        await enqueue(database, clock, anna, contest_id=contest_id)

    first = await notification_service.deliver_due_emails(database, clock, sender)
    second = await notification_service.deliver_due_emails(database, clock, sender)

    assert (first.sent, second.sent) == (BATCH_SIZE, 5)


async def test_sent_but_not_recorded_is_delivered_again_after_lease(
    database: Database,
    clock: FrozenClock,
    anna: Person,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP принял письмо, но итог не записан: доставка at-least-once, дубль — после аренды."""
    sender = FakeMailSender()
    await enqueue(database, clock, anna)
    original = notification_dao.mark_finished

    async def failing_mark(*args: object, **kwargs: object) -> None:
        raise RuntimeError("commit упал")

    monkeypatch.setattr(notification_dao, "mark_finished", failing_mark)
    with pytest.raises(RuntimeError):
        await notification_service.deliver_due_emails(database, clock, sender)
    monkeypatch.setattr(notification_dao, "mark_finished", original)

    assert (await only_row(database)).status == EmailStatus.SENDING.value
    # Пока аренда действует, письмо не берут повторно.
    assert (await notification_service.deliver_due_emails(database, clock, sender)).sent == 0
    clock.advance(LEASE_DURATION + timedelta(seconds=1))
    assert (await notification_service.deliver_due_emails(database, clock, sender)).sent == 1

    assert len(sender.sent) == 2
    assert sender.sent[0].message_id == sender.sent[1].message_id
    assert (await only_row(database)).status == EmailStatus.SENT.value
