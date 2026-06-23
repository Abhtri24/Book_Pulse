import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EngagementEventType(str, enum.Enum):
    view = "view"
    tap_through = "tap_through"
    skip = "skip"
    read_complete = "read_complete"


class EngagementEvent(Base):
    __tablename__ = "engagement_events"
    __table_args__ = (
        CheckConstraint(
            "read_duration_seconds >= 0",
            name="ck_engagement_events_read_duration_non_negative",
        ),
        Index("ix_engagement_events_reader_created_at", "reader_id", "created_at"),
        Index("ix_engagement_events_snippet_created_at", "snippet_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reader_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readers.id", ondelete="CASCADE"),
        index=True,
    )
    snippet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("snippets.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[EngagementEventType] = mapped_column(
        Enum(EngagementEventType),
        index=True,
    )
    read_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    reader = relationship("Reader", back_populates="engagement_events")
    snippet = relationship("Snippet", back_populates="engagement_events")
