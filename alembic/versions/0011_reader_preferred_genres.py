"""add reader preferred genres

Revision ID: 0011_reader_preferred_genres
Revises: 0010_book_external_links
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_reader_preferred_genres"
down_revision: str | None = "0010_book_external_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "readers",
        sa.Column(
            "preferred_genres",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column(
        "readers",
        "preferred_genres",
        existing_type=sa.JSON(),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("readers", "preferred_genres")
