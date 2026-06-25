from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedItem(BaseModel):
    snippet_id: UUID
    book_id: UUID | None = None
    author_id: UUID
    primary_genre: str
    quality_score: float
    hook_score: int
    rank_score: float = Field(description="Final weighted ranking score")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
