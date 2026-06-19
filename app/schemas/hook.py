from pydantic import BaseModel, Field


class HookMetrics(BaseModel):
    hook_score: int = Field(ge=0, le=100)
    hook_type: str
    opening_style: str
    curiosity_gap: bool
    conflict_present: bool
    dialogue_opening: bool
    reasoning: list[str] = Field(default_factory=list)
