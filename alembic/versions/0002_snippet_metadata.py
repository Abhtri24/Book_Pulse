"""add snippet metadata

Revision ID: 0002_snippet_metadata
Revises: 0001_foundation
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_snippet_metadata"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snippet_metadata",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snippet_id", sa.Uuid(), nullable=False),
        sa.Column("primary_genre", sa.String(length=80), nullable=False),
        sa.Column("sub_genres", sa.JSON(), nullable=False),
        sa.Column("pov", sa.String(length=50), nullable=False),
        sa.Column("pacing", sa.String(length=50), nullable=False),
        sa.Column("tone", sa.String(length=80), nullable=False),
        sa.Column("hook_type", sa.String(length=80), nullable=False),
        sa.Column("readability_score", sa.Float(), nullable=False),
        sa.Column("classifier_model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snippet_id"], ["snippets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snippet_id"),
    )
    op.create_index(
        op.f("ix_snippet_metadata_snippet_id"),
        "snippet_metadata",
        ["snippet_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_snippet_metadata_snippet_id"), table_name="snippet_metadata")
    op.drop_table("snippet_metadata")
