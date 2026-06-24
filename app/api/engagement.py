"""POST /engage — record a reader interaction and update preference vector.

Phase 5.4 implementation.  All steps run inside a single database transaction
so that partial failures leave no orphaned rows.  Qdrant retrieval is the only
call that can fail *after* the DB write; on that path we roll back the DB
transaction and surface a 400 to the caller.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_reader, get_session
from app.models.engagement_event import EngagementEvent
from app.models.reader import Reader
from app.models.snippet import ProcessingStatus, Snippet
from app.schemas.engagement import EngageRequest, EngageResponse
from app.services.preference_engine import update_preference_vector
from app.vector_store import get_snippet_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/engage", tags=["engagement"])


@router.post(
    "",
    response_model=EngageResponse,
    status_code=status.HTTP_200_OK,
    summary="Record a reader interaction with a snippet",
)
async def engage(
    payload: EngageRequest,
    reader: Reader = Depends(get_current_reader),
    db: AsyncSession = Depends(get_session),
) -> EngageResponse:
    """Record an engagement event and synchronously update the reader's
    preference vector.

    Errors
    ------
    404 — snippet not found
    400 — snippet not in READY state
    400 — snippet has no embedding stored in Qdrant
    401 — unauthenticated or wrong token type (author token rejected)
    """
    # ------------------------------------------------------------------
    # 1. Validate the snippet
    # ------------------------------------------------------------------
    snippet: Snippet | None = await db.get(Snippet, payload.snippet_id)
    if snippet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="snippet not found",
        )

    if snippet.processing_status != ProcessingStatus.ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"snippet is not ready (status: {snippet.processing_status.value})",
        )

    # ------------------------------------------------------------------
    # 2. Retrieve the embedding *before* opening the transaction so that
    #    a Qdrant failure never leaves orphaned DB rows.
    # ------------------------------------------------------------------
    snippet_embedding: list[float] | None = get_snippet_embedding(str(snippet.id))
    if snippet_embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="snippet has no embedding — cannot update preference vector",
        )

    # ------------------------------------------------------------------
    # 3. Persist the EngagementEvent and update the preference vector
    #    inside a single atomic transaction.
    #
    # Capture plain-Python identifiers *before* entering the try block so
    # that the except handler never needs to touch ORM-managed attributes
    # (which would be expired after a rollback and trigger a sync DB load
    # — illegal in an async context).
    # ------------------------------------------------------------------
    reader_id = reader.id
    snippet_id = snippet.id
    current_vector = list(reader.preference_vector)
    current_update_count = reader.vector_update_count

    try:
        # 3a. Compute the updated preference vector (pure, no I/O)
        new_vector = update_preference_vector(
            current_vector=current_vector,
            snippet_vector=snippet_embedding,
            event_type=payload.event_type,
            update_count=current_update_count,
        )

        # 3b. Store the event row
        event = EngagementEvent(
            reader_id=reader_id,
            snippet_id=snippet_id,
            event_type=payload.event_type,
            read_duration_seconds=payload.read_duration_seconds,
        )
        db.add(event)

        # 3c. Persist the updated reader fields
        reader.preference_vector = new_vector
        reader.vector_update_count = current_update_count + 1
        db.add(reader)

        await db.commit()

    except Exception as exc:
        await db.rollback()
        logger.exception(
            "Failed to persist engagement event for reader=%s snippet=%s: %s",
            reader_id,
            snippet_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to record engagement — please retry",
        ) from exc

    return EngageResponse(
        success=True,
        vector_update_count=reader.vector_update_count,
        event_recorded=True,
    )
