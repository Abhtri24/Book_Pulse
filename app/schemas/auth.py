from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.reader import MAX_PREFERRED_GENRES, normalize_preferred_genres


class RegisterAuthorRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    bio: str = Field(default="", max_length=500)


class RegisterReaderRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    preferred_genres: list[str] = Field(default_factory=list)

    @field_validator("preferred_genres")
    @classmethod
    def normalize_genres(cls, genres: list[str]) -> list[str]:
        normalized = normalize_preferred_genres(genres)
        if len(normalized) > MAX_PREFERRED_GENRES:
            raise ValueError(f"preferred_genres must contain at most {MAX_PREFERRED_GENRES} genres")
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthorResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    bio: str

    model_config = ConfigDict(from_attributes=True)


class ReaderResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    preferred_genres: list[str]

    model_config = ConfigDict(from_attributes=True)
