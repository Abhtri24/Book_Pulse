"""align snippet feedback table

Revision ID: 0007_snippet_feedback
Revises: 0006_quality_score
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_snippet_feedback"
down_revision: str | None = "0006_quality_score"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("snippet_feedback") as batch_op:
        batch_op.drop_column("agent_model")


def downgrade() -> None:
    with op.batch_alter_table("snippet_feedback") as batch_op:
        batch_op.add_column(sa.Column("agent_model", sa.String(length=100), nullable=False, server_default="unknown"))
