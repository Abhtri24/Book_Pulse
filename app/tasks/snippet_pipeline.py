import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.services.embedding_service import embed_text
from app.services.classifier_service import classify_snippet
from app.services.hook_service import check_hook_strength
from app.services.quality_agent import analyze_readability
from app.tasks.celery_app import celery_app
from app.vector_store import ensure_snippet_collection, upsert_snippet


@celery_app.task(name="app.tasks.snippet_pipeline.process_snippet")
def process_snippet(snippet_id: str) -> dict[str, Any]:
    return asyncio.run(process_snippet_async(snippet_id))


async def process_snippet_async(
    snippet_id: str,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    if db is not None:
        return await _process_snippet_in_session(db, snippet_id)

    async with AsyncSessionLocal() as session:
        return await _process_snippet_in_session(session, snippet_id)


async def _process_snippet_in_session(
    db: AsyncSession,
    snippet_id: str,
) -> dict[str, Any]:
    snippet_uuid = uuid.UUID(snippet_id)
    snippet = await db.get(Snippet, snippet_uuid)
    if snippet is None:
        return {"snippet_id": snippet_id, "status": "not_found"}

    snippet.processing_status = ProcessingStatus.processing
    await db.commit()
    await db.refresh(snippet)

    try:
        embedding = embed_text(snippet.content)
        
        classifier_result = await classify_snippet(snippet.content)
        readability_metrics = analyze_readability(snippet.content)
        hook_metrics = check_hook_strength(snippet.content)
        
        quality_score = float(
            (hook_metrics.hook_score * 0.6)
            + (readability_metrics.flesch_reading_ease * 0.4)
        )
        
        snippet_metadata = SnippetMetadata(
            snippet_id=snippet.id,
            primary_genre=classifier_result.primary_genre,
            sub_genres=classifier_result.sub_genres,
            pov=classifier_result.pov,
            pacing=classifier_result.pacing,
            tone=classifier_result.tone,
            hook_type=hook_metrics.hook_type,
            readability_score=readability_metrics.flesch_reading_ease,
            quality_score=quality_score,
            classifier_model=classifier_result.classifier_model,
            hook_score=hook_metrics.hook_score,
            opening_style=hook_metrics.opening_style,
            curiosity_gap=hook_metrics.curiosity_gap,
            conflict_present=hook_metrics.conflict_present,
            dialogue_opening=hook_metrics.dialogue_opening,
        )
        db.add(snippet_metadata)

        ensure_snippet_collection()
        embedding_id = upsert_snippet(snippet, embedding, metadata=snippet_metadata)
    except Exception:
        snippet.processing_status = ProcessingStatus.failed
        await db.commit()
        raise

    snippet.embedding_id = embedding_id
    snippet.processing_status = ProcessingStatus.ready
    await db.commit()
    await db.refresh(snippet)
    return {
        "snippet_id": str(snippet.id),
        "embedding_id": embedding_id,
        "status": snippet.processing_status.value,
    }
