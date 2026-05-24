"""foundation

Revision ID: 0001_foundation
Revises:
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("bio", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_authors_email"), "authors", ["email"], unique=True)
    op.create_index(op.f("ix_authors_username"), "authors", ["username"], unique=True)

    op.create_table(
        "readers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("preference_vector", sa.JSON(), nullable=True),
        sa.Column("vector_update_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_readers_email"), "readers", ["email"], unique=True)
    op.create_index(op.f("ix_readers_username"), "readers", ["username"], unique=True)

    book_status = sa.Enum("draft", "published", "completed", "hiatus", name="bookstatus")
    processing_status = sa.Enum("pending", "processing", "ready", "failed", name="processingstatus")
    book_status.create(op.get_bind(), checkfirst=True)
    processing_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "books",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", book_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_books_author_id"), "books", ["author_id"], unique=False)

    op.create_table(
        "snippets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("book_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("processing_status", processing_status, nullable=False),
        sa.Column("embedding_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_snippets_author_id"), "snippets", ["author_id"], unique=False)
    op.create_index(op.f("ix_snippets_book_id"), "snippets", ["book_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_snippets_book_id"), table_name="snippets")
    op.drop_index(op.f("ix_snippets_author_id"), table_name="snippets")
    op.drop_table("snippets")
    op.drop_index(op.f("ix_books_author_id"), table_name="books")
    op.drop_table("books")
    op.drop_index(op.f("ix_readers_username"), table_name="readers")
    op.drop_index(op.f("ix_readers_email"), table_name="readers")
    op.drop_table("readers")
    op.drop_index(op.f("ix_authors_username"), table_name="authors")
    op.drop_index(op.f("ix_authors_email"), table_name="authors")
    op.drop_table("authors")
    sa.Enum(name="processingstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="bookstatus").drop(op.get_bind(), checkfirst=True)
