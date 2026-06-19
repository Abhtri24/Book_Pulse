from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import get_settings
from app.models.snippet import Snippet

VECTOR_SIZE = 384


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url,timeout=60,)


def ensure_snippet_collection(
    client: QdrantClient | None = None,
    vector_size: int = VECTOR_SIZE,
) -> None:
    settings = get_settings()
    qdrant = client or get_qdrant_client()

    if qdrant.collection_exists(settings.qdrant_collection_name):
        return

    qdrant.create_collection(
        collection_name=settings.qdrant_collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )


def upsert_snippet(
    snippet: Snippet,
    embedding: list[float],
    metadata: Any = None,
    client: QdrantClient | None = None,
) -> str:
    if len(embedding) != VECTOR_SIZE:
        raise ValueError(f"snippet embedding must have {VECTOR_SIZE} dimensions")

    settings = get_settings()
    qdrant = client or get_qdrant_client()
    embedding_id = str(snippet.id)
    qdrant.upsert(
        collection_name=settings.qdrant_collection_name,
        points=[
            models.PointStruct(
                id=embedding_id,
                vector=embedding,
                payload=_snippet_payload(snippet, metadata),
            )
        ],
    )
    return embedding_id


def search_similar(
    query_vector: list[float],
    limit: int = 10,
    client: QdrantClient | None = None,
) -> list[Any]:
    settings = get_settings()
    qdrant = client or get_qdrant_client()
    return qdrant.search(
        collection_name=settings.qdrant_collection_name,
        query_vector=query_vector,
        limit=limit,
    )


def _snippet_payload(snippet: Snippet, metadata: Any = None) -> dict[str, Any]:
    payload = {
        "snippet_id": str(snippet.id),
        "book_id": str(snippet.book_id),
        "author_id": str(snippet.author_id),
        "chapter_number": snippet.chapter_number,
        "processing_status": snippet.processing_status.value,
        "created_at": snippet.created_at.isoformat(),
    }
    m = metadata
    if m is None and "metadata_record" in snippet.__dict__:
        m = snippet.metadata_record

    if m is not None:
        payload.update({
            "primary_genre": m.primary_genre,
            "sub_genres": m.sub_genres,
            "pov": m.pov,
            "pacing": m.pacing,
            "tone": m.tone,
            "hook_type": m.hook_type,
            "readability_score": m.readability_score,
            "classifier_model": m.classifier_model,
            "hook_score": m.hook_score,
            "opening_style": m.opening_style,
            "curiosity_gap": m.curiosity_gap,
            "conflict_present": m.conflict_present,
            "dialogue_opening": m.dialogue_opening,
        })
    return payload
