from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.snippet import ProcessingStatus


class SnippetCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    chapter_number: int = Field(ge=1)

    @field_validator("content")
    @classmethod
    def validate_word_count(cls, value: str) -> str:
        word_count = len(value.split())
        if word_count < 200 or word_count > 600:
            raise ValueError("snippet content must be between 200 and 600 words")
        return value


class SnippetResponse(BaseModel):
    id: UUID
    book_id: UUID
    author_id: UUID
    content: str
    chapter_number: int
    processing_status: ProcessingStatus
    embedding_id: str | None

    model_config = ConfigDict(from_attributes=True)
