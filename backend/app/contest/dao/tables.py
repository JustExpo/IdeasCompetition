"""Таблица конкурсов (CLAUDE.md §7.1)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ContestRow(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    topic: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    submission_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    voting_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Внешнего ключа на ideas нет: таблицы ссылались бы друг на друга; значение ставит
    # финализация (IC-020) и проверяет её же транзакция.
    winner_idea_id: Mapped[UUID | None] = mapped_column(Uuid)

    __table_args__ = (
        CheckConstraint("submission_deadline < voting_deadline", name="deadlines_order"),
        CheckConstraint("char_length(topic) BETWEEN 1 AND 200", name="topic_length"),
        CheckConstraint("char_length(description) <= 10000", name="description_length"),
        CheckConstraint(
            "winner_idea_id IS NULL OR finalized_at IS NOT NULL", name="winner_after_finalization"
        ),
        # Планировщик (IC-020) ищет только конкурсы, у которых итог ещё не зафиксирован.
        Index(
            "ix_contests_voting_deadline_open",
            "voting_deadline",
            postgresql_where="finalized_at IS NULL",
        ),
    )
