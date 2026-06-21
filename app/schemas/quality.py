from pydantic import BaseModel, Field


class ReadabilityMetrics(BaseModel):
    flesch_reading_ease: float = Field(description="Flesch Reading Ease score (higher is easier)")
    flesch_kincaid_grade: float = Field(description="US grade level from Flesch-Kincaid formula")
    avg_sentence_length: float = Field(description="Average words per sentence")
    word_count: int = Field(ge=0)
    sentence_count: int = Field(ge=0)


class SnippetFeedbackResult(BaseModel):
    strengths: list[str] = Field(description="List of writing strengths found in the snippet")
    improvements: list[str] = Field(description="List of suggested areas of improvement")
    hook_score: int = Field(description="Hook score from 1 to 10", ge=1, le=10)
    rewrite_suggestion: str = Field(description="A specific rewrite suggestion for the opening line or hook")

