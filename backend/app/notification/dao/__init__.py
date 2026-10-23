"""notification.dao — таблица писем и запросы к ней."""

from app.notification.dao.repository import (
    insert_email_if_absent,
    lock_due_emails,
    mark_finished,
    mark_retry,
    mark_sending,
    select_email_by_dedup_key,
)
from app.notification.dao.tables import OutboxEmailRow

__all__ = [
    "OutboxEmailRow",
    "insert_email_if_absent",
    "lock_due_emails",
    "mark_finished",
    "mark_retry",
    "mark_sending",
    "select_email_by_dedup_key",
]
