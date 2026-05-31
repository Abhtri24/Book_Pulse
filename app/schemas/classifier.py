from typing import Literal

from pydantic import BaseModel, Field, field_validator

PointOfView = Literal["first_person", "second_person", "third_person", "multiple"]
Pacing = Literal["slow", "moderate", "fast"]
HookType = Literal[
    "action",
    "dialogue",
    "mystery",
    "character",
    "worldbuilding",
    "emotional",
]


class ClassifierResult(BaseModel):
    primary_genre: str = Field(min_length=2, max_length=80)
    sub_genres: list[str] = Field(default_factory=list, max_length=5)
    pov: PointOfView
    pacing: Pacing
    tone: str = Field(min_length=2, max_length=80)
    hook_type: HookType
    readability_score: float = Field(ge=0, le=100)
    classifier_model: str = Field(min_length=1, max_length=100)

    @field_validator("primary_genre", "tone", "classifier_model")
    @classmethod
    def normalize_text_field(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("sub_genres")
    @classmethod
    def normalize_sub_genres(cls, value: list[str]) -> list[str]:
        normalized = [genre.strip().lower() for genre in value if genre.strip()]
        return list(dict.fromkeys(normalized))
