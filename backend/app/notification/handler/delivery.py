"""Тик планировщика: отправка писем из outbox."""

from app.core.clock import Clock
from app.core.db import Database
from app.core.logging import get_logger
from app.notification.service import EmailSender, deliver_due_emails

_log = get_logger(__name__)


async def run_email_delivery(database: Database, clock: Clock, sender: EmailSender) -> None:
    report = await deliver_due_emails(database, clock, sender)
    if report.sent or report.retried or report.failed or report.expired:
        _log.info(
            "emails_processed",
            sent=report.sent,
            retried=report.retried,
            failed=report.failed,
            expired=report.expired,
        )
