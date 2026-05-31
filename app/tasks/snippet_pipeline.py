import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.snippet import ProcessingStatus, Snippet
from app.services.embedding_service import embed_text
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
        ensure_snippet_collection()
        embedding_id = upsert_snippet(snippet, embedding)
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
