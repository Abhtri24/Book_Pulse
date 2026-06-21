"""add quality score to snippet metadata

Revision ID: 0006_quality_score
Revises: 0005_hook_metrics
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_quality_score"
down_revision: str | None = "0005_hook_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "snippet_metadata",
        sa.Column("quality_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("snippet_metadata", "quality_score")
