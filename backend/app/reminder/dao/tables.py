"""Таблица reminders (CLAUDE.md §7.1)."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ReminderRow(Base):
    __tablename__ = "reminders"

    # Составной ключ — единственная гарантия «одно напоминание на (конкурс, раунд, сотрудник)»
    # при параллельных тиках (П9); код опирается на него, а не на проверку «до».
    contest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    round: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("round IN ('submission', 'voting')", name="round"),)
