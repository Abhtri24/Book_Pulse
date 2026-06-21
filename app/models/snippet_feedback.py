import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SnippetFeedback(Base):
    __tablename__ = "snippet_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    snippet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("snippets.id"),
        unique=True,
        index=True,
    )
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    improvements: Mapped[list[str]] = mapped_column(JSON, default=list)
    hook_score: Mapped[int] = mapped_column(Integer)
    rewrite_suggestion: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    snippet = relationship("Snippet", back_populates="feedback_record")
