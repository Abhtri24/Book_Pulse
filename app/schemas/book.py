from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator

from app.models.book import BookStatus, SourcePlatform

http_url_adapter = TypeAdapter(HttpUrl)


class BookCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: BookStatus = BookStatus.draft
    external_url: str = Field(max_length=500)
    source_platform: SourcePlatform = SourcePlatform.other

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: str) -> str:
        http_url_adapter.validate_python(value)
        return value


class BookResponse(BaseModel):
    id: UUID
    author_id: UUID
    title: str
    description: str
    status: BookStatus
    external_url: str
    source_platform: SourcePlatform

    model_config = ConfigDict(from_attributes=True)
