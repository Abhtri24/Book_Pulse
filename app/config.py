from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BookPulse"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/bookpulse"
    secret_key: str = Field(default="change-me-in-production", min_length=16)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    groq_api_key: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
