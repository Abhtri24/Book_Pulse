import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BookStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    completed = "completed"
    hiatus = "hiatus"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authors.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[BookStatus] = mapped_column(Enum(BookStatus), default=BookStatus.draft)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    author = relationship("Author", back_populates="books")
    snippets = relationship("Snippet", back_populates="book", cascade="all, delete-orphan")
