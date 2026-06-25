"""Reader feed generation.

Cold-start recommendations are served when a reader has no usable
preference vector.  Ranking math lives in ``app.services.ranking`` so
this module only handles candidate retrieval and orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reader import PREFERENCE_VECTOR_DIMENSIONS
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.services.ranking import (
    DEFAULT_COLD_START_WEIGHTS,
    RankingCandidate,
    rank_candidates,
)

COLD_START_POOL_MULTIPLIER: int = 5


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
    preferred_genres: list[str] | None = None,
    reference_time: datetime | None = None,
) -> list[RankingCandidate]:
    """Return high-quality recent snippets for readers without preferences."""
    if limit <= 0:
        return []

    pool_size = max(limit * COLD_START_POOL_MULTIPLIER, limit)
    candidates = await fetch_cold_start_candidates(db, pool_size=pool_size)
    if not candidates:
        return []

    ranked = rank_candidates(
        candidates,
        reference_time=reference_time,
        weights=DEFAULT_COLD_START_WEIGHTS,
        preferred_genres=preferred_genres,
    )
    return ranked[:limit]
