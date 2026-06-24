"""Pydantic schemas for the POST /engage endpoint (Phase 5.4)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.engagement_event import EngagementEventType


class EngageRequest(BaseModel):
    """Payload sent by a reader when interacting with a snippet."""

    snippet_id: UUID
    event_type: EngagementEventType
    read_duration_seconds: int = Field(default=0, ge=0)


class EngageResponse(BaseModel):
    """Response returned after successfully recording an engagement event."""

    success: bool
    vector_update_count: int
    event_recorded: bool

    model_config = ConfigDict(from_attributes=True)
