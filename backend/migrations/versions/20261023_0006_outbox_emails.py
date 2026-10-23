"""Таблица outbox_emails (IC-021). Только добавление: прежняя версия приложения её не видит.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_emails",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("to_email", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("not_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'expired')",
            name=op.f("ck_outbox_emails_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_outbox_emails_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_emails")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_outbox_emails_dedup_key")),
    )
    op.create_index(
        "ix_outbox_emails_next_attempt_at_open",
        "outbox_emails",
        ["next_attempt_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'sending')"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_emails_next_attempt_at_open", table_name="outbox_emails")
    op.drop_table("outbox_emails")
