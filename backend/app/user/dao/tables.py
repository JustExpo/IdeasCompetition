"""Таблица пользователей (CLAUDE.md §7.1)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Identity, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("role IN ('employee', 'organizer')", name="role"),
        CheckConstraint("char_length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        # Уникальность адреса без учёта регистра держит БД, а не код (Р5).
        Index("uq_users_email_lower", func.lower(email), unique=True),
    )
