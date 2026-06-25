"""Tests for app/services/feed_service.py (Phase 5.6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event

from app.models.author import Author
from app.models.book import Book
from app.models.reader import PREFERENCE_VECTOR_DIMENSIONS, Reader
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.services.auth_service import create_access_token
from app.services.feed_service import (
    build_feed_response,
    build_personalized_feed_response,
    build_cold_start_feed,
    fetch_cold_start_candidates,
    has_usable_preference_vector,
)


REF = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
PREF = [1.0 / (PREFERENCE_VECTOR_DIMENSIONS ** 0.5)] * PREFERENCE_VECTOR_DIMENSIONS


def reader_token(reader: Reader) -> str:
    return create_access_token(str(reader.id), "reader")


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


async def seed_reader(db_session, *, preference_vector=None) -> Reader:
    reader = Reader(
        username=f"reader_{len(preference_vector or [])}_{datetime.now().timestamp()}",
        email=f"reader_{datetime.now().timestamp()}@example.com",
        password_hash="hash",
        preference_vector=preference_vector or [],
    )
    db_session.add(reader)
    await db_session.commit()
    return reader


async def seed_personalized_data(db_session):
    author_a = Author(
        username="personal_author_a",
        email="personal_author_a@example.com",
        password_hash="hash",
    )
    author_b = Author(
        username="personal_author_b",
        email="personal_author_b@example.com",
        password_hash="hash",
    )
    book_a = Book(author=author_a, title="Personal A")
    book_b = Book(author=author_b, title="Personal B")

    snippets = []
    for idx, (author, book, genre, quality, hook) in enumerate(
        [
            (author_a, book_a, "fantasy", 70.0, 70),
            (author_b, book_b, "sci-fi", 95.0, 90),
            (author_a, book_a, "mystery", 85.0, 80),
        ],
        start=1,
    ):
        snippet = Snippet(
            author=author,
            book=book,
            content=f"Personalized snippet {idx}",
            chapter_number=idx,
            processing_status=ProcessingStatus.ready,
        )
        metadata = SnippetMetadata(
            snippet=snippet,
            primary_genre=genre,
            sub_genres=[],
            pov="third_person",
            pacing="fast",
            tone="serious",
            hook_type="mystery",
            readability_score=80.0,
            quality_score=quality,
            hook_score=hook,
            classifier_model="model",
            created_at=REF - timedelta(hours=idx),
        )
        snippets.append(snippet)
        db_session.add(metadata)

    db_session.add_all([author_a, author_b, book_a, book_b, *snippets])
    await db_session.commit()
    return snippets


def qdrant_hit(snippet_id, score: float):
    return SimpleNamespace(id=str(snippet_id), score=score, payload={"snippet_id": str(snippet_id)})


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


@pytest.mark.asyncio
async def test_build_feed_response_routes_empty_preference_to_cold_start(db_session):
    await seed_cold_start_data(db_session)

    response = await build_feed_response(
        db_session,
        preference_vector=[],
        page=1,
        page_size=2,
        reference_time=REF,
    )

    assert response.mode == "cold_start"
    assert len(response.items) == 2
    assert response.pagination.page_size == 2


@pytest.mark.asyncio
async def test_personalized_feed_uses_mocked_qdrant_and_ranks_results(db_session):
    snippets = await seed_personalized_data(db_session)
    hits = [
        qdrant_hit(snippets[0].id, 0.2),
        qdrant_hit(snippets[1].id, 0.95),
        qdrant_hit(snippets[2].id, 0.5),
    ]

    with patch("app.services.feed_service.search_similar", return_value=hits):
        response = await build_personalized_feed_response(
            db_session,
            preference_vector=PREF,
            page=1,
            page_size=2,
            reference_time=REF,
        )

    assert response.mode == "personalized"
    assert [item.snippet_id for item in response.items][0] == snippets[1].id
    assert response.items[0].metadata.primary_genre == "sci-fi"
    assert response.items[0].snippet.content == "Personalized snippet 2"
    assert response.pagination.total_items == 3
    assert response.pagination.has_next is True


@pytest.mark.asyncio
async def test_personalized_feed_paginates_ranked_results(db_session):
    snippets = await seed_personalized_data(db_session)
    hits = [
        qdrant_hit(snippets[0].id, 0.95),
        qdrant_hit(snippets[1].id, 0.9),
        qdrant_hit(snippets[2].id, 0.85),
    ]

    with patch("app.services.feed_service.search_similar", return_value=hits):
        first = await build_personalized_feed_response(
            db_session,
            preference_vector=PREF,
            page=1,
            page_size=1,
            reference_time=REF,
        )
        second = await build_personalized_feed_response(
            db_session,
            preference_vector=PREF,
            page=2,
            page_size=1,
            reference_time=REF,
        )

    assert first.items[0].snippet_id != second.items[0].snippet_id
    assert second.pagination.has_previous is True


@pytest.mark.asyncio
async def test_personalized_feed_loads_metadata_in_one_query(db_session):
    snippets = await seed_personalized_data(db_session)
    hits = [qdrant_hit(snippet.id, 0.9) for snippet in snippets]
    statement_count = 0

    def count_statement(*args):
        nonlocal statement_count
        statement_count += 1

    event.listen(db_session.bind.sync_engine, "before_cursor_execute", count_statement)
    try:
        with patch("app.services.feed_service.search_similar", return_value=hits):
            await build_personalized_feed_response(
                db_session,
                preference_vector=PREF,
                page=1,
                page_size=3,
                reference_time=REF,
            )
    finally:
        event.remove(db_session.bind.sync_engine, "before_cursor_execute", count_statement)

    assert statement_count == 1


@pytest.mark.asyncio
async def test_feed_endpoint_requires_reader_auth(client, db_session):
    response = await client.get("/feed")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feed_endpoint_returns_cold_start_for_reader_without_vector(client, db_session):
    await seed_cold_start_data(db_session)
    reader = await seed_reader(db_session)

    response = await client.get(
        "/feed?page_size=1",
        headers={"Authorization": f"Bearer {reader_token(reader)}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "cold_start"
    assert body["pagination"]["page_size"] == 1
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_feed_endpoint_returns_personalized_for_reader_with_vector(client, db_session):
    snippets = await seed_personalized_data(db_session)
    reader = await seed_reader(db_session, preference_vector=PREF)
    hits = [qdrant_hit(snippet.id, 0.9) for snippet in snippets]

    with patch("app.services.feed_service.search_similar", return_value=hits):
        response = await client.get(
            "/feed?page_size=2",
            headers={"Authorization": f"Bearer {reader_token(reader)}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "personalized"
    assert len(body["items"]) == 2
    assert "rank_score" in body["items"][0]


@pytest.mark.asyncio
async def test_end_to_end_mocked_engagement_to_personalized_feed(client, db_session):
    snippets = await seed_personalized_data(db_session)
    reader = await seed_reader(db_session)
    unit_embedding = PREF

    with patch("app.api.engagement.get_snippet_embedding", return_value=unit_embedding):
        engagement = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippets[0].id),
                "event_type": "read_complete",
                "read_duration_seconds": 90,
            },
            headers={"Authorization": f"Bearer {reader_token(reader)}"},
        )

    assert engagement.status_code == 200

    hits = [
        qdrant_hit(snippets[2].id, 0.95),
        qdrant_hit(snippets[0].id, 0.8),
    ]
    with patch("app.services.feed_service.search_similar", return_value=hits):
        feed = await client.get(
            "/feed?page_size=2",
            headers={"Authorization": f"Bearer {reader_token(reader)}"},
        )

    assert feed.status_code == 200
    body = feed.json()
    assert body["mode"] == "personalized"
    assert body["items"][0]["snippet_id"] == str(snippets[2].id)
