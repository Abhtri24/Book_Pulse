import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database_worker import run_worker_async, worker_session
from app.models.snippet import Snippet
from app.models.snippet_feedback import SnippetFeedback
from app.models.snippet_metadata import SnippetMetadata
from app.services.quality_agent import run_quality_agent
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.quality_task.process_feedback")
def process_feedback(snippet_id: str) -> dict[str, Any]:
    return run_worker_async(lambda: process_feedback_async(snippet_id))


async def process_feedback_async(
    snippet_id: str,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    if db is not None:
        return await _process_feedback_in_session(db, snippet_id)

    async with worker_session() as session:
        return await _process_feedback_in_session(session, snippet_id)


async def _process_feedback_in_session(
    db: AsyncSession,
    snippet_id: str,
) -> dict[str, Any]:
    snippet_uuid = uuid.UUID(snippet_id)
    snippet = await db.get(Snippet, snippet_uuid)
    if snippet is None:
        return {"snippet_id": snippet_id, "feedback_saved": False, "status": "not_found"}
    snippet_id_str = str(snippet.id)

    existing_result = await db.execute(
        select(SnippetFeedback).where(SnippetFeedback.snippet_id == snippet.id)
    )
    if existing_result.scalar_one_or_none() is not None:
        return {"snippet_id": snippet_id_str, "feedback_saved": False, "status": "already_exists"}

    metadata_result = await db.execute(
        select(SnippetMetadata).where(SnippetMetadata.snippet_id == snippet.id)
    )
    metadata = metadata_result.scalar_one_or_none()
    if metadata is None:
        return {"snippet_id": snippet_id_str, "feedback_saved": False, "status": "metadata_not_found"}

    try:
        feedback_result = await run_quality_agent(snippet, metadata.primary_genre, db)
        feedback = SnippetFeedback(
            snippet_id=snippet.id,
            strengths=feedback_result.strengths,
            improvements=feedback_result.improvements,
            hook_score=feedback_result.hook_score,
            rewrite_suggestion=feedback_result.rewrite_suggestion,
        )
        db.add(feedback)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info("Feedback already exists for snippet %s", snippet_id)
        return {"snippet_id": snippet_id_str, "feedback_saved": False, "status": "already_exists"}
    except Exception:
        await db.rollback()
        logger.exception("Failed to generate feedback for snippet %s", snippet_id)
        return {"snippet_id": snippet_id_str, "feedback_saved": False, "status": "failed"}

    return {"snippet_id": snippet_id_str, "feedback_saved": True}
