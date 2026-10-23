"""notification.handler — реакции на тики планировщика."""

from app.notification.handler.delivery import run_email_delivery

__all__ = ["run_email_delivery"]
