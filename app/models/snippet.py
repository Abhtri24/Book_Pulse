import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Snippet(Base):
    __tablename__ = "snippets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authors.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    chapter_number: Mapped[int] = mapped_column(Integer)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.pending,
    )
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    author = relationship("Author", back_populates="snippets")
    book = relationship("Book", back_populates="snippets")
    metadata_record = relationship(
        "SnippetMetadata",
        back_populates="snippet",
        cascade="all, delete-orphan",
        uselist=False,
    )
    feedback_record = relationship(
        "SnippetFeedback",
        back_populates="snippet",
        cascade="all, delete-orphan",
        uselist=False,
    )
