import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base

PREFERENCE_VECTOR_DIMENSIONS = 384


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
        super().__init__(**kwargs)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    preference_vector: Mapped[list[float]] = mapped_column(JSON, default=list)
    vector_update_count: Mapped[int] = mapped_column(Integer, default=0)
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
