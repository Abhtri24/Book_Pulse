"""add engagement events and reader preference defaults

Revision ID: 0008_engagement_events
Revises: 0007_snippet_feedback
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_engagement_events"
down_revision: str | None = "0007_snippet_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    engagement_event_type = sa.Enum(
        "view",
        "tap_through",
        "skip",
        "read_complete",
        name="engagementeventtype",
    )

    op.execute(
        "UPDATE readers SET preference_vector = '[]' "
        "WHERE preference_vector IS NULL "
        "OR json_array_length(preference_vector) NOT IN (0, 384)"
    )
    op.alter_column(
        "readers",
        "preference_vector",
        existing_type=sa.JSON(),
        nullable=False,
        server_default="[]",
    )
    op.alter_column(
        "readers",
        "vector_update_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
    )
    op.create_check_constraint(
        "ck_readers_preference_vector_dimensions",
        "readers",
        "json_array_length(preference_vector) IN (0, 384)",
    )

    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column("snippet_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", engagement_event_type, nullable=False),
        sa.Column("read_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "read_duration_seconds >= 0",
            name="ck_engagement_events_read_duration_non_negative",
        ),
        sa.ForeignKeyConstraint(["reader_id"], ["readers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snippet_id"], ["snippets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_engagement_events_created_at"),
        "engagement_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engagement_events_event_type"),
        "engagement_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engagement_events_reader_id"),
        "engagement_events",
        ["reader_id"],
        unique=False,
    )
    op.create_index(
        "ix_engagement_events_reader_created_at",
        "engagement_events",
        ["reader_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engagement_events_snippet_id"),
        "engagement_events",
        ["snippet_id"],
        unique=False,
    )
    op.create_index(
        "ix_engagement_events_snippet_created_at",
        "engagement_events",
        ["snippet_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_engagement_events_snippet_created_at", table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_snippet_id"), table_name="engagement_events")
    op.drop_index("ix_engagement_events_reader_created_at", table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_reader_id"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_event_type"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_created_at"), table_name="engagement_events")
    op.drop_table("engagement_events")
    sa.Enum(name="engagementeventtype").drop(op.get_bind(), checkfirst=True)
    op.drop_constraint(
        "ck_readers_preference_vector_dimensions",
        "readers",
        type_="check",
    )

    op.alter_column(
        "readers",
        "vector_update_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "readers",
        "preference_vector",
        existing_type=sa.JSON(),
        nullable=True,
        server_default=None,
    )
