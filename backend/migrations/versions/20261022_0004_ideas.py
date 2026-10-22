"""Таблица ideas (IC-011). Только добавление: прежняя версия приложения её не видит.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ideas",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=True),
        sa.Column("request_hash", sa.LargeBinary(), nullable=True),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name=op.f("ck_ideas_title_length")
        ),
        sa.CheckConstraint(
            "char_length(description) BETWEEN 1 AND 10000", name=op.f("ck_ideas_description_length")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_ideas_version_positive")),
        sa.ForeignKeyConstraint(
            ["contest_id"],
            ["contests.id"],
            name=op.f("fk_ideas_contest_id_contests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_ideas_author_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ideas")),
        sa.UniqueConstraint("author_id", "client_request_id", name="uq_ideas_author_request"),
    )
    op.create_index(
        "ix_ideas_contest_id_submitted_at_id",
        "ideas",
        ["contest_id", "submitted_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ideas_contest_id_submitted_at_id", table_name="ideas")
    op.drop_table("ideas")
