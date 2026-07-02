import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base

PREFERENCE_VECTOR_DIMENSIONS = 384
MAX_PREFERRED_GENRES = 10
MAX_GENRE_LENGTH = 80


def normalize_preferred_genres(genres: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for genre in genres or []:
        value = genre.strip().lower()
        if not value or value in normalized:
            continue
        if len(value) > MAX_GENRE_LENGTH:
            raise ValueError(f"preferred genres must be at most {MAX_GENRE_LENGTH} characters")
        normalized.append(value)
    if len(normalized) > MAX_PREFERRED_GENRES:
        raise ValueError(f"preferred_genres must contain at most {MAX_PREFERRED_GENRES} genres")
    return normalized


class Reader(Base):
    __tablename__ = "readers"
    __table_args__ = (
        CheckConstraint(
            f"json_array_length(preference_vector) IN (0, {PREFERENCE_VECTOR_DIMENSIONS})",
            name="ck_readers_preference_vector_dimensions",
        ),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("preference_vector", [])
        kwargs.setdefault("vector_update_count", 0)
        kwargs.setdefault("preferred_genres", [])
        super().__init__(**kwargs)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    preference_vector: Mapped[list[float]] = mapped_column(JSON, default=list)
    vector_update_count: Mapped[int] = mapped_column(Integer, default=0)
    preferred_genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    engagement_events = relationship(
        "EngagementEvent",
        back_populates="reader",
        cascade="all, delete-orphan",
    )

    @validates("preference_vector")
    def validate_preference_vector(self, key: str, vector: list[float] | None) -> list[float]:
        if vector is None:
            return []
        if len(vector) not in (0, PREFERENCE_VECTOR_DIMENSIONS):
            raise ValueError(
                f"{key} must be empty or contain {PREFERENCE_VECTOR_DIMENSIONS} dimensions"
            )
        return [float(value) for value in vector]

    @validates("preferred_genres")
    def validate_preferred_genres(self, key: str, genres: list[str] | None) -> list[str]:
        return normalize_preferred_genres(genres)
