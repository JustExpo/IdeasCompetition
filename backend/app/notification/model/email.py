"""Письмо в outbox: создаётся в транзакции события, отправляется отдельно (Р9)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.common.model import UserId, require_aware


class EmailKind(StrEnum):
    SUBMISSION_REMINDER = "submission_reminder"
    VOTING_REMINDER = "voting_reminder"
    WINNER_ANNOUNCEMENT = "winner_announcement"
    RESULTS_ANNOUNCEMENT = "results_announcement"


class EmailStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        return self in {EmailStatus.SENT, EmailStatus.FAILED, EmailStatus.EXPIRED}


@dataclass(frozen=True, slots=True)
class OutboxEmail:
    """Запись outbox. `dedup_key` вида `<kind>:<contest>:<user>` не даёт создать письмо дважды.

    `body` обнуляется через 30 дней после завершения (хранение ПДн, CLAUDE.md §9).
    `not_after` — после этого момента письмо уже бессмысленно (напоминание после дедлайна).
    Адрес, тема, текст и ошибка SMTP (может содержать адрес) скрыты из repr.
    """

    id: int
    dedup_key: str
    kind: EmailKind
    user_id: UserId | None
    to_email: str = field(repr=False)
    subject: str = field(repr=False)
    body: str | None = field(repr=False)
    status: EmailStatus
    attempts: int
    next_attempt_at: datetime
    created_at: datetime
    not_after: datetime | None = None
    sent_at: datetime | None = None
    last_error: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for name in ("next_attempt_at", "created_at", "not_after", "sent_at"):
            value = getattr(self, name)
            if value is not None:
                require_aware(value, name)

    def is_expired_at(self, now: datetime) -> bool:
        return self.not_after is not None and now >= self.not_after
