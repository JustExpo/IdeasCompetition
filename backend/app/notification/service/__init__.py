"""notification.service — постановка писем в outbox и их доставка."""

from app.notification.service.delivery import DeliveryReport, deliver_due_emails
from app.notification.service.outbox import build_dedup_key, enqueue_email
from app.notification.service.sender import EmailSender, SmtpEmailSender, build_message
from app.notification.service.templates import (
    RenderedEmail,
    format_moment,
    render_not_passed_email,
    render_results_email,
    render_submission_reminder,
    render_voting_reminder,
    render_winner_email,
)

__all__ = [
    "DeliveryReport",
    "EmailSender",
    "RenderedEmail",
    "SmtpEmailSender",
    "build_dedup_key",
    "build_message",
    "deliver_due_emails",
    "enqueue_email",
    "format_moment",
    "render_not_passed_email",
    "render_results_email",
    "render_submission_reminder",
    "render_voting_reminder",
    "render_winner_email",
]
