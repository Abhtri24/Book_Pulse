from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TopSnippet(BaseModel):
    snippet_id: UUID
    book_id: UUID
    primary_genre: str
    hook_score: int
    readability_score: float
    quality_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
