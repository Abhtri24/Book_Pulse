from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.book import BookStatus


class BookCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: BookStatus = BookStatus.draft


class BookResponse(BaseModel):
    id: UUID
    author_id: UUID
    title: str
    description: str
    status: BookStatus

    model_config = ConfigDict(from_attributes=True)
