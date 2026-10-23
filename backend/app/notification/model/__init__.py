"""notification.model — доменные модели исходящих писем."""

from app.notification.model.email import (
    BATCH_SIZE,
    LEASE_DURATION,
    MAX_ATTEMPTS,
    RETRY_DELAY_MAX,
    EmailKind,
    EmailStatus,
    OutboxEmail,
    OutgoingEmail,
    retry_delay,
)

__all__ = [
    "BATCH_SIZE",
    "LEASE_DURATION",
    "MAX_ATTEMPTS",
    "RETRY_DELAY_MAX",
    "EmailKind",
    "EmailStatus",
    "OutboxEmail",
    "OutgoingEmail",
    "retry_delay",
]
