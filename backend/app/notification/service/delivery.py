"""Отправщик outbox: аренда пачки, SMTP вне транзакции, итог отдельной транзакцией.

Доставка at-least-once (Р9): если процесс упал после ответа SMTP 250, но до записи `sent`,
письмо вернётся по истёкшей аренде и уйдёт ещё раз с тем же Message-ID.
"""

from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.db import Database
from app.core.logging import get_logger
from app.notification import dao
from app.notification.exception import EmailDeliveryError
from app.notification.model import (
    BATCH_SIZE,
    LEASE_DURATION,
    MAX_ATTEMPTS,
    EmailStatus,
    OutboxEmail,
    OutgoingEmail,
    retry_delay,
)
from app.notification.service.sender import EmailSender

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    sent: int = 0
    retried: int = 0
    failed: int = 0
    expired: int = 0


async def _claim_batch(database: Database, clock: Clock) -> tuple[list[OutboxEmail], int]:
    """Взять пачку: просроченные закрыть, остальные закрепить за этим проходом на 60 с."""

    async def work(session: AsyncSession) -> tuple[list[OutboxEmail], int]:
        now = clock.now()
        claimed: list[OutboxEmail] = []
        expired = 0
        for email in await dao.lock_due_emails(session, now, BATCH_SIZE):
            attempts = email.attempts + 1
            await dao.mark_sending(
                session, email.id, lease_until=now + LEASE_DURATION, attempts=attempts
            )
            if email.is_expired_at(now):
                await dao.mark_finished(
                    session, email.id, status=EmailStatus.EXPIRED, now=now, error=None
                )
                expired += 1
            elif email.attempts >= MAX_ATTEMPTS:
                # Проход падал каждый раз, не дойдя до записи итога: письмо не отправить.
                await dao.mark_finished(
                    session,
                    email.id,
                    status=EmailStatus.FAILED,
                    now=now,
                    error="attempts_exhausted",
                )
            else:
                claimed.append(replace(email, attempts=attempts))
        return claimed, expired

    return await database.run_in_transaction(work)


async def deliver_due_emails(
    database: Database, clock: Clock, sender: EmailSender
) -> DeliveryReport:
    """Один проход отправщика: до 20 писем. Ошибка одного письма не мешает остальным."""
    batch, expired = await _claim_batch(database, clock)
    sent = retried = failed = 0
    for email in batch:
        outgoing = OutgoingEmail(
            outbox_id=email.id,
            to_email=email.to_email,
            subject=email.subject,
            body=email.body or "",
        )
        try:
            await sender.send(outgoing)
        except EmailDeliveryError as error:
            gave_up = error.permanent or email.attempts >= MAX_ATTEMPTS
            await _record_failure(database, clock, email, error.message, gave_up=gave_up)
            if gave_up:
                failed += 1
            else:
                retried += 1
            # Адрес и тема в лог не попадают (CLAUDE.md §13).
            _log.warning(
                "email_delivery_failed",
                outbox_id=email.id,
                attempts=email.attempts,
                permanent=error.permanent,
                reason=error.message,
            )
            continue

        async def mark_sent(session: AsyncSession, email_id: int = email.id) -> None:
            await dao.mark_finished(
                session, email_id, status=EmailStatus.SENT, now=clock.now(), error=None
            )

        await database.run_in_transaction(mark_sent)
        sent += 1
    return DeliveryReport(sent=sent, retried=retried, failed=failed, expired=expired)


async def _record_failure(
    database: Database, clock: Clock, email: OutboxEmail, reason: str, *, gave_up: bool
) -> None:
    async def work(session: AsyncSession) -> None:
        now = clock.now()
        if gave_up:
            await dao.mark_finished(
                session, email.id, status=EmailStatus.FAILED, now=now, error=reason
            )
        else:
            await dao.mark_retry(
                session, email.id, next_attempt_at=now + retry_delay(email.attempts), error=reason
            )

    await database.run_in_transaction(work)
