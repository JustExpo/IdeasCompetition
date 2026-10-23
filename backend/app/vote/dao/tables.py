"""Таблица голосов (CLAUDE.md §7.1)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class VoteRow(Base):
    __tablename__ = "votes"

    # Составной первичный ключ — единственная гарантия «один голос на идею» при любом числе
    # вкладок и параллельных запросов (П5); код опирается на него, а не на проверку «до».
    idea_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), primary_key=True
    )
    voter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_votes_voter_id", "voter_id"),)
