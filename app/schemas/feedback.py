from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SnippetFeedbackResponse(BaseModel):
    snippet_id: UUID
    strengths: list[str]
    improvements: list[str]
    hook_score: int
    rewrite_suggestion: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
