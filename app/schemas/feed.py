from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedSnippet(BaseModel):
    id: UUID
    book_id: UUID
    author_id: UUID
    content: str
    chapter_number: int

    model_config = ConfigDict(from_attributes=True)


class FeedMetadata(BaseModel):
    primary_genre: str
    sub_genres: list[str]
    pov: str
    pacing: str
    tone: str
    hook_type: str
    readability_score: float
    quality_score: float | None
    hook_score: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedItem(BaseModel):
    snippet_id: UUID
    book_id: UUID | None = None
    author_id: UUID
    snippet: FeedSnippet
    metadata: FeedMetadata
    primary_genre: str
    quality_score: float | None
    hook_score: int
    rank_score: float = Field(description="Final weighted ranking score")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedPagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    has_next: bool
    has_previous: bool


class FeedResponse(BaseModel):
    items: list[FeedItem]
    pagination: FeedPagination
    mode: str
