"""Таблица contests (IC-010). Только добавление: прежняя версия приложения её не видит.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("submission_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voting_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winner_idea_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "submission_deadline < voting_deadline", name=op.f("ck_contests_deadlines_order")
        ),
        sa.CheckConstraint(
            "char_length(topic) BETWEEN 1 AND 200", name=op.f("ck_contests_topic_length")
        ),
        sa.CheckConstraint(
            "char_length(description) <= 10000", name=op.f("ck_contests_description_length")
        ),
        sa.CheckConstraint(
            "winner_idea_id IS NULL OR finalized_at IS NOT NULL",
            name=op.f("ck_contests_winner_after_finalization"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_contests_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contests")),
    )
    op.create_index(
        "ix_contests_voting_deadline_open",
        "contests",
        ["voting_deadline"],
        unique=False,
        postgresql_where=sa.text("finalized_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contests_voting_deadline_open",
        table_name="contests",
        postgresql_where=sa.text("finalized_at IS NULL"),
    )
    op.drop_table("contests")
