"""Tests for app/services/feed_service.py (Phase 5.6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.author import Author
from app.models.book import Book
from app.models.reader import PREFERENCE_VECTOR_DIMENSIONS
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.services.feed_service import (
    build_cold_start_feed,
    fetch_cold_start_candidates,
    has_usable_preference_vector,
)


REF = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


async def seed_cold_start_data(db_session):
    author_a = Author(
        username="author_a",
        email="author_a@example.com",
        password_hash="hash",
    )
    author_b = Author(
        username="author_b",
        email="author_b@example.com",
        password_hash="hash",
    )
    book_a = Book(author=author_a, title="Book A")
    book_b = Book(author=author_b, title="Book B")

    recent_high = Snippet(
        author=author_a,
        book=book_a,
        content="A" * 200,
        chapter_number=1,
        processing_status=ProcessingStatus.ready,
    )
    recent_high_meta = SnippetMetadata(
        snippet=recent_high,
        primary_genre="fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="serious",
        hook_type="mystery",
        readability_score=80.0,
        quality_score=90.0,
        hook_score=85,
        classifier_model="model",
        created_at=REF - timedelta(hours=2),
    )

    older_good = Snippet(
        author=author_b,
        book=book_b,
        content="B" * 200,
        chapter_number=1,
        processing_status=ProcessingStatus.ready,
    )
    older_good_meta = SnippetMetadata(
        snippet=older_good,
        primary_genre="sci-fi",
        sub_genres=[],
        pov="third_person",
        pacing="moderate",
        tone="neutral",
        hook_type="action",
        readability_score=75.0,
        quality_score=85.0,
        hook_score=80,
        classifier_model="model",
        created_at=REF - timedelta(days=10),
    )

    stale_low = Snippet(
        author=author_a,
        book=book_a,
        content="C" * 200,
        chapter_number=2,
        processing_status=ProcessingStatus.ready,
    )
    stale_low_meta = SnippetMetadata(
        snippet=stale_low,
        primary_genre="romance",
        sub_genres=[],
        pov="first_person",
        pacing="slow",
        tone="warm",
        hook_type="dialogue",
        readability_score=50.0,
        quality_score=55.0,
        hook_score=45,
        classifier_model="model",
        created_at=REF - timedelta(days=30),
    )

    pending = Snippet(
        author=author_b,
        book=book_b,
        content="D" * 200,
        chapter_number=2,
        processing_status=ProcessingStatus.pending,
    )
    pending_meta = SnippetMetadata(
        snippet=pending,
        primary_genre="horror",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="dark",
        hook_type="mystery",
        readability_score=70.0,
        quality_score=88.0,
        hook_score=82,
        classifier_model="model",
        created_at=REF - timedelta(hours=1),
    )

    db_session.add_all(
        [
            author_a,
            author_b,
            book_a,
            book_b,
            recent_high,
            recent_high_meta,
            older_good,
            older_good_meta,
            stale_low,
            stale_low_meta,
            pending,
            pending_meta,
        ]
    )
    await db_session.commit()
    return recent_high, older_good, stale_low, pending


class TestHasUsablePreferenceVector:
    def test_empty_vector_is_not_usable(self):
        assert has_usable_preference_vector([]) is False

    def test_full_vector_is_usable(self):
        vector = [0.1] * PREFERENCE_VECTOR_DIMENSIONS
        assert has_usable_preference_vector(vector) is True


@pytest.mark.asyncio
async def test_fetch_cold_start_candidates_excludes_non_ready(db_session):
    recent_high, older_good, stale_low, pending = await seed_cold_start_data(
        db_session
    )
    candidates = await fetch_cold_start_candidates(db_session, pool_size=10)
    snippet_ids = {candidate.snippet_id for candidate in candidates}

    assert recent_high.id in snippet_ids
    assert older_good.id in snippet_ids
    assert stale_low.id in snippet_ids
    assert pending.id not in snippet_ids


@pytest.mark.asyncio
async def test_build_cold_start_feed_returns_ranked_recent_high_quality(
    db_session,
):
    recent_high, older_good, stale_low, _pending = await seed_cold_start_data(
        db_session
    )

    feed = await build_cold_start_feed(
        db_session,
        limit=2,
        reference_time=REF,
    )

    assert len(feed) == 2
    assert feed[0].snippet_id == recent_high.id
    assert feed[0].rank_score >= feed[1].rank_score
    assert stale_low.id not in {item.snippet_id for item in feed}


@pytest.mark.asyncio
async def test_build_cold_start_feed_respects_genre_preference(db_session):
    author = Author(
        username="genre_author",
        email="genre_author@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Genre Book")
    created_at = REF - timedelta(hours=2)

    fantasy = Snippet(
        author=author,
        book=book,
        content="F" * 200,
        chapter_number=1,
        processing_status=ProcessingStatus.ready,
    )
    fantasy_meta = SnippetMetadata(
        snippet=fantasy,
        primary_genre="fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="serious",
        hook_type="mystery",
        readability_score=80.0,
        quality_score=88.0,
        hook_score=80,
        classifier_model="model",
        created_at=created_at,
    )

    sci_fi = Snippet(
        author=author,
        book=book,
        content="S" * 200,
        chapter_number=2,
        processing_status=ProcessingStatus.ready,
    )
    sci_fi_meta = SnippetMetadata(
        snippet=sci_fi,
        primary_genre="sci-fi",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="serious",
        hook_type="mystery",
        readability_score=80.0,
        quality_score=88.0,
        hook_score=80,
        classifier_model="model",
        created_at=created_at,
    )

    db_session.add_all([author, book, fantasy, fantasy_meta, sci_fi, sci_fi_meta])
    await db_session.commit()

    feed = await build_cold_start_feed(
        db_session,
        limit=1,
        preferred_genres=["sci-fi"],
        reference_time=REF,
    )

    assert len(feed) == 1
    assert feed[0].snippet_id == sci_fi.id


@pytest.mark.asyncio
async def test_build_cold_start_feed_empty_when_no_candidates(db_session):
    feed = await build_cold_start_feed(db_session, limit=5, reference_time=REF)
    assert feed == []


@pytest.mark.asyncio
async def test_build_cold_start_feed_zero_limit_returns_empty(db_session):
    await seed_cold_start_data(db_session)
    feed = await build_cold_start_feed(db_session, limit=0, reference_time=REF)
    assert feed == []
