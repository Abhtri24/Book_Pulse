from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snippet import Snippet
from app.models.snippet_metadata import SnippetMetadata


async def get_top_by_quality(db: AsyncSession, limit: int = 20):
    stmt = (
        select(
            SnippetMetadata.snippet_id,
            Snippet.book_id,
            SnippetMetadata.primary_genre,
            SnippetMetadata.hook_score,
            SnippetMetadata.readability_score,
            SnippetMetadata.quality_score,
            SnippetMetadata.created_at,
        )
        .join(Snippet, Snippet.id == SnippetMetadata.snippet_id)
        .order_by(SnippetMetadata.quality_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.mappings().all()


async def get_top_by_hook(db: AsyncSession, limit: int = 20):
    stmt = (
        select(
            SnippetMetadata.snippet_id,
            Snippet.book_id,
            SnippetMetadata.primary_genre,
            SnippetMetadata.hook_score,
            SnippetMetadata.readability_score,
            SnippetMetadata.quality_score,
            SnippetMetadata.created_at,
        )
        .join(Snippet, Snippet.id == SnippetMetadata.snippet_id)
        .order_by(SnippetMetadata.hook_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.mappings().all()


async def get_top_by_readability(db: AsyncSession, limit: int = 20):
    stmt = (
        select(
            SnippetMetadata.snippet_id,
            Snippet.book_id,
            SnippetMetadata.primary_genre,
            SnippetMetadata.hook_score,
            SnippetMetadata.readability_score,
            SnippetMetadata.quality_score,
            SnippetMetadata.created_at,
        )
        .join(Snippet, Snippet.id == SnippetMetadata.snippet_id)
        .order_by(SnippetMetadata.readability_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.mappings().all()
