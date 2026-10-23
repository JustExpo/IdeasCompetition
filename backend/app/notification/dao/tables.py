"""Таблица outbox_emails (CLAUDE.md §7.1)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OutboxEmailRow(Base):
    __tablename__ = "outbox_emails"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    # Уникальный ключ — единственная гарантия «письмо создаётся один раз» (Р9).
    dedup_key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    to_email: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("dedup_key"),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'expired')", name="status"
        ),
        Index(
            "ix_outbox_emails_next_attempt_at_open",
            "next_attempt_at",
            postgresql_where="status IN ('pending', 'sending')",
        ),
    )
