"""add hook metrics to snippet metadata

Revision ID: 0005_hook_metrics
Revises: 0003_snippet_feedback
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_hook_metrics"
down_revision: str | None = "0003_snippet_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "snippet_metadata",
        sa.Column("hook_score", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "snippet_metadata",
        sa.Column("opening_style", sa.String(length=50), nullable=False, server_default="neutral"),
    )
    op.add_column(
        "snippet_metadata",
        sa.Column("curiosity_gap", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "snippet_metadata",
        sa.Column("conflict_present", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "snippet_metadata",
        sa.Column("dialogue_opening", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("snippet_metadata", "dialogue_opening")
    op.drop_column("snippet_metadata", "conflict_present")
    op.drop_column("snippet_metadata", "curiosity_gap")
    op.drop_column("snippet_metadata", "opening_style")
    op.drop_column("snippet_metadata", "hook_score")
