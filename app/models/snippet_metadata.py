import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
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
    classifier_model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    snippet = relationship("Snippet", back_populates="metadata_record")
