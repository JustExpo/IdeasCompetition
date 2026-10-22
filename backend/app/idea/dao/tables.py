"""Таблица идей (CLAUDE.md §7.1)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class IdeaRow(Base):
    __tablename__ = "ideas"

    # UUIDv4, а не порядковый номер: по последовательным номерам в фазе голосования
    # можно вычислить порядок подачи и по нему — автора (Р7).
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    contest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contests.id", ondelete="RESTRICT")
    )
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    client_request_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_hash: Mapped[bytes | None] = mapped_column(LargeBinary)

    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("char_length(description) BETWEEN 1 AND 10000", name="description_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        # NULL в client_request_id допустимы (дубли NULL не конфликтуют): ключ нужен SPA,
        # но схема не ломается об клиента без ключа (§7.1).
        UniqueConstraint("author_id", "client_request_id", name="uq_ideas_author_request"),
        Index("ix_ideas_contest_id_submitted_at_id", "contest_id", "submitted_at", "id"),
    )
