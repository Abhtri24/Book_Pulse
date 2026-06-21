import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SnippetMetadata(Base):
    __tablename__ = "snippet_metadata"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    snippet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("snippets.id"),
        unique=True,
        index=True,
    )
    primary_genre: Mapped[str] = mapped_column(String(80))
    sub_genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    pov: Mapped[str] = mapped_column(String(50))
    pacing: Mapped[str] = mapped_column(String(50))
    tone: Mapped[str] = mapped_column(String(80))
    hook_type: Mapped[str] = mapped_column(String(80))
    readability_score: Mapped[float] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    classifier_model: Mapped[str] = mapped_column(String(100))
    hook_score: Mapped[int] = mapped_column(Integer, default=50)
    opening_style: Mapped[str] = mapped_column(String(50), default="neutral")
    curiosity_gap: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_present: Mapped[bool] = mapped_column(Boolean, default=False)
    dialogue_opening: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    snippet = relationship("Snippet", back_populates="metadata_record")
