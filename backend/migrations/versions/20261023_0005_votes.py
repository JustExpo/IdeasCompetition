"""Таблица votes (IC-013). Только добавление: прежняя версия приложения её не видит.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("idea_id", sa.Uuid(), nullable=False),
        sa.Column("voter_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["idea_id"], ["ideas.id"], name=op.f("fk_votes_idea_id_ideas"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["voter_id"], ["users.id"], name=op.f("fk_votes_voter_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("idea_id", "voter_id", name=op.f("pk_votes")),
    )
    op.create_index("ix_votes_voter_id", "votes", ["voter_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_votes_voter_id", table_name="votes")
    op.drop_table("votes")
