"""Reader feed generation.

Cold-start recommendations are served when a reader has no usable
preference vector.  Ranking math lives in ``app.services.ranking`` so
this module only handles candidate retrieval and orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reader import PREFERENCE_VECTOR_DIMENSIONS
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.schemas.feed import (
    FeedItem,
    FeedMetadata,
    FeedPagination,
    FeedResponse,
    FeedSnippet,
)
from app.services.ranking import (
    DEFAULT_COLD_START_WEIGHTS,
    DEFAULT_PERSONALIZED_WEIGHTS,
    RankingCandidate,
    rank_candidates,
)
from app.vector_store import search_similar

COLD_START_POOL_MULTIPLIER: int = 5
PERSONALIZED_POOL_MULTIPLIER: int = 5
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
COLD_START_INTERACTION_THRESHOLD: int = 5


@dataclass(frozen=True)
class CandidateMetadata:
    snippet: Snippet
    metadata: SnippetMetadata


def has_usable_preference_vector(preference_vector: list[float]) -> bool:
    """Return ``True`` when the reader has a populated preference vector."""
    return len(preference_vector) == PREFERENCE_VECTOR_DIMENSIONS


async def fetch_cold_start_candidates(
    db: AsyncSession,
    *,
    pool_size: int,
) -> list[RankingCandidate]:
    """Load ready snippets with quality metadata for cold-start ranking."""
    stmt = (
        select(
            Snippet.id,
            Snippet.author_id,
            SnippetMetadata.primary_genre,
            SnippetMetadata.sub_genres,
            SnippetMetadata.quality_score,
            SnippetMetadata.hook_score,
            SnippetMetadata.created_at,
        )
        .join(SnippetMetadata, SnippetMetadata.snippet_id == Snippet.id)
        .where(Snippet.processing_status == ProcessingStatus.ready)
        .where(SnippetMetadata.quality_score.is_not(None))
        .order_by(SnippetMetadata.created_at.desc())
        .limit(pool_size)
    )
    rows = (await db.execute(stmt)).mappings().all()

    return [
        RankingCandidate(
            snippet_id=row["id"],
            author_id=row["author_id"],
            primary_genre=row["primary_genre"],
            sub_genres=tuple(row["sub_genres"] or []),
            quality_score=float(row["quality_score"]),
            hook_score=int(row["hook_score"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def build_cold_start_feed(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    preferred_genres: list[str] | None = None,
    reference_time: datetime | None = None,
) -> list[RankingCandidate]:
    """Return high-quality recent snippets for readers without preferences."""
    if limit <= 0:
        return []

    page_end = max(offset, 0) + limit
    pool_size = max(page_end * COLD_START_POOL_MULTIPLIER, page_end)
    candidates = await fetch_cold_start_candidates(db, pool_size=pool_size)
    if not candidates:
        return []

    ranked = rank_candidates(
        candidates,
        reference_time=reference_time,
        weights=DEFAULT_COLD_START_WEIGHTS,
        preferred_genres=preferred_genres,
    )
    return ranked[offset:page_end]


async def build_feed_response(
    db: AsyncSession,
    *,
    preference_vector: list[float],
    vector_update_count: int,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    preferred_genres: list[str] | None = None,
    reference_time: datetime | None = None,
) -> FeedResponse:
    """Build a feed, keeping new readers cold until five vector updates."""
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    if (
        vector_update_count < COLD_START_INTERACTION_THRESHOLD
        or not has_usable_preference_vector(preference_vector)
    ):
        return await build_cold_start_feed_response(
            db,
            page=safe_page,
            page_size=safe_page_size,
            preferred_genres=preferred_genres,
            reference_time=reference_time,
        )

    return await build_personalized_feed_response(
        db,
        preference_vector=preference_vector,
        page=safe_page,
        page_size=safe_page_size,
        reference_time=reference_time,
    )


async def build_cold_start_feed_response(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    preferred_genres: list[str] | None = None,
    reference_time: datetime | None = None,
) -> FeedResponse:
    """Return a paginated cold-start feed response."""
    offset = _offset_for_page(page, page_size)
    page_end = offset + page_size
    pool_size = max(page_end * COLD_START_POOL_MULTIPLIER, page_end)
    candidates = await fetch_cold_start_candidates(db, pool_size=pool_size)
    ranked = rank_candidates(
        candidates,
        reference_time=reference_time,
        weights=DEFAULT_COLD_START_WEIGHTS,
        preferred_genres=preferred_genres,
    )
    return await _response_from_ranked(
        db,
        ranked,
        page=page,
        page_size=page_size,
        mode="cold_start",
    )


async def build_personalized_feed_response(
    db: AsyncSession,
    *,
    preference_vector: list[float],
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    reference_time: datetime | None = None,
) -> FeedResponse:
    """Query Qdrant, hydrate metadata in one SQL query, rank, and paginate."""
    if not has_usable_preference_vector(preference_vector):
        return await build_cold_start_feed_response(
            db,
            page=page,
            page_size=page_size,
            reference_time=reference_time,
        )

    page_end = _offset_for_page(page, page_size) + page_size
    qdrant_limit = max(page_end * PERSONALIZED_POOL_MULTIPLIER, page_end)
    qdrant_hits = search_similar(preference_vector, limit=qdrant_limit)
    similarities = _similarities_by_snippet_id(qdrant_hits)
    if not similarities:
        return _empty_response(page=page, page_size=page_size, mode="personalized")

    hydrated = await load_candidate_metadata(db, list(similarities.keys()))
    candidates = [
        RankingCandidate(
            snippet_id=snippet_id,
            author_id=record.snippet.author_id,
            primary_genre=record.metadata.primary_genre,
            sub_genres=tuple(record.metadata.sub_genres or []),
            quality_score=float(record.metadata.quality_score or 0.0),
            hook_score=record.metadata.hook_score,
            created_at=record.metadata.created_at,
            semantic_similarity=similarities[snippet_id],
        )
        for snippet_id, record in hydrated.items()
    ]
    ranked = rank_candidates(
        candidates,
        reference_time=reference_time,
        weights=DEFAULT_PERSONALIZED_WEIGHTS,
    )
    return await _response_from_ranked(
        db,
        ranked,
        page=page,
        page_size=page_size,
        mode="personalized",
        hydrated=hydrated,
    )


async def load_candidate_metadata(
    db: AsyncSession,
    snippet_ids: list[UUID],
) -> dict[UUID, CandidateMetadata]:
    """Load all candidate snippets and metadata in a single SQL query."""
    if not snippet_ids:
        return {}

    stmt = (
        select(Snippet, SnippetMetadata)
        .join(SnippetMetadata, SnippetMetadata.snippet_id == Snippet.id)
        .where(Snippet.id.in_(snippet_ids))
        .where(Snippet.processing_status == ProcessingStatus.ready)
        .where(SnippetMetadata.quality_score.is_not(None))
    )
    rows = (await db.execute(stmt)).all()
    return {
        snippet.id: CandidateMetadata(snippet=snippet, metadata=metadata)
        for snippet, metadata in rows
    }


async def _response_from_ranked(
    db: AsyncSession,
    ranked: list[RankingCandidate],
    *,
    page: int,
    page_size: int,
    mode: str,
    hydrated: dict[UUID, CandidateMetadata] | None = None,
) -> FeedResponse:
    offset = _offset_for_page(page, page_size)
    page_items = ranked[offset : offset + page_size]
    records = hydrated or await load_candidate_metadata(
        db,
        [candidate.snippet_id for candidate in page_items],
    )
    return FeedResponse(
        items=[
            _to_feed_item(candidate, records[candidate.snippet_id])
            for candidate in page_items
            if candidate.snippet_id in records
        ],
        pagination=FeedPagination(
            page=page,
            page_size=page_size,
            total_items=len(ranked),
            has_next=offset + page_size < len(ranked),
            has_previous=page > 1,
        ),
        mode=mode,
    )


def _to_feed_item(
    candidate: RankingCandidate,
    record: CandidateMetadata,
) -> FeedItem:
    snippet = record.snippet
    metadata = record.metadata
    return FeedItem(
        snippet_id=snippet.id,
        book_id=snippet.book_id,
        author_id=snippet.author_id,
        snippet=FeedSnippet(
            id=snippet.id,
            book_id=snippet.book_id,
            author_id=snippet.author_id,
            content=snippet.content,
            chapter_number=snippet.chapter_number,
        ),
        metadata=FeedMetadata(
            primary_genre=metadata.primary_genre,
            sub_genres=metadata.sub_genres,
            pov=metadata.pov,
            pacing=metadata.pacing,
            tone=metadata.tone,
            hook_type=metadata.hook_type,
            readability_score=metadata.readability_score,
            quality_score=metadata.quality_score,
            hook_score=metadata.hook_score,
            created_at=metadata.created_at,
        ),
        primary_genre=metadata.primary_genre,
        quality_score=metadata.quality_score,
        hook_score=metadata.hook_score,
        rank_score=candidate.rank_score,
        created_at=metadata.created_at,
    )


def _similarities_by_snippet_id(qdrant_hits: list[Any]) -> dict[UUID, float]:
    similarities: dict[UUID, float] = {}
    for hit in qdrant_hits:
        snippet_id = _extract_snippet_id(hit)
        if snippet_id is None:
            continue
        similarities[snippet_id] = float(getattr(hit, "score", 0.0))
    return similarities


def _extract_snippet_id(hit: Any) -> UUID | None:
    payload = getattr(hit, "payload", None) or {}
    raw_id = payload.get("snippet_id") if isinstance(payload, dict) else None
    raw_id = raw_id or getattr(hit, "id", None)
    try:
        return UUID(str(raw_id))
    except (TypeError, ValueError):
        return None


def _offset_for_page(page: int, page_size: int) -> int:
    return (max(page, 1) - 1) * page_size


def _empty_response(*, page: int, page_size: int, mode: str) -> FeedResponse:
    return FeedResponse(
        items=[],
        pagination=FeedPagination(
            page=page,
            page_size=page_size,
            total_items=0,
            has_next=False,
            has_previous=page > 1,
        ),
        mode=mode,
    )
