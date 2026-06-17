"""add snippet feedback

Revision ID: 0003_snippet_feedback
Revises: 0002_snippet_metadata
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_snippet_feedback"
down_revision: str | None = "0002_snippet_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snippet_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snippet_id", sa.Uuid(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("improvements", sa.JSON(), nullable=False),
        sa.Column("hook_score", sa.Integer(), nullable=False),
        sa.Column("rewrite_suggestion", sa.Text(), nullable=False),
        sa.Column("agent_model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snippet_id"], ["snippets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snippet_id"),
    )
    op.create_index(
        op.f("ix_snippet_feedback_snippet_id"),
        "snippet_feedback",
        ["snippet_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_snippet_feedback_snippet_id"), table_name="snippet_feedback")
    op.drop_table("snippet_feedback")
