"""notification.model — доменные модели исходящих писем."""

from app.notification.model.email import EmailKind, EmailStatus, OutboxEmail

__all__ = ["EmailKind", "EmailStatus", "OutboxEmail"]
