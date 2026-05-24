from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterAuthorRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    bio: str = Field(default="", max_length=500)


class RegisterReaderRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


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

    model_config = ConfigDict(from_attributes=True)
