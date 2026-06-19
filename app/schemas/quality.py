from pydantic import BaseModel, Field


class ReadabilityMetrics(BaseModel):
    flesch_reading_ease: float = Field(description="Flesch Reading Ease score (higher is easier)")
    flesch_kincaid_grade: float = Field(description="US grade level from Flesch-Kincaid formula")
    avg_sentence_length: float = Field(description="Average words per sentence")
    word_count: int = Field(ge=0)
    sentence_count: int = Field(ge=0)
