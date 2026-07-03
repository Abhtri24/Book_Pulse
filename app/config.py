from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    app_name: str = "BookPulse"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/bookpulse"
    secret_key: str = Field(default=DEFAULT_SECRET_KEY, min_length=16)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    groq_api_key: str | None = None
    groq_classifier_model: str = Field(default="llama-3.1-8b-instant", min_length=1)
    groq_quality_model: str = Field(default="llama-3.3-70b-versatile", min_length=1)
    redis_url: str = Field(default="redis://localhost:6379/0", min_length=1)
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        min_length=1,
    )
    qdrant_url: str = Field(default="http://localhost:6333", min_length=1)
    qdrant_collection_name: str = Field(default="snippets", min_length=1)

    @model_validator(mode="after")
    def reject_default_production_secret(self) -> "Settings":
        if (
            self.environment.strip().lower() == "production"
            and self.secret_key == DEFAULT_SECRET_KEY
        ):
            raise ValueError(
                "SECRET_KEY must be explicitly configured to a non-default value "
                "when ENVIRONMENT=production"
            )
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
