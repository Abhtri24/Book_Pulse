"""add external links to books

Revision ID: 0010_book_external_links
Revises: 0009_chapters
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_book_external_links"
down_revision: str | None = "0009_chapters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_platform = sa.Enum(
        "royalroad",
        "tapas",
        "wattpad",
        "webnovel",
        "own_site",
        "other",
        name="sourceplatform",
    )
    source_platform.create(op.get_bind(), checkfirst=True)

    op.add_column("books", sa.Column("external_url", sa.String(length=500), nullable=True))
    op.execute("UPDATE books SET external_url = 'https://example.com' WHERE external_url IS NULL")
    op.alter_column(
        "books",
        "external_url",
        existing_type=sa.String(length=500),
        nullable=False,
    )
    op.add_column(
        "books",
        sa.Column(
            "source_platform",
            source_platform,
            nullable=False,
            server_default="other",
        ),
    )
    op.alter_column(
        "books",
        "source_platform",
        existing_type=source_platform,
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("books", "source_platform")
    op.drop_column("books", "external_url")
    sa.Enum(name="sourceplatform").drop(op.get_bind(), checkfirst=True)
