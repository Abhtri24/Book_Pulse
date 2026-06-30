"""Tests for POST /engage (Phase 5.4 — Reader Engagement Endpoint).

Strategy
--------
* The test database is an in-memory SQLite instance provided by conftest.py.
* Qdrant (get_snippet_embedding) is monkey-patched so no real Qdrant is needed.
* All tests use the async HTTP client from conftest.py.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.models.author import Author
from app.models.book import Book
from app.models.engagement_event import EngagementEvent, EngagementEventType
from app.models.reader import PREFERENCE_VECTOR_DIMENSIONS, Reader
from app.models.snippet import ProcessingStatus, Snippet
from app.services.auth_service import create_access_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = PREFERENCE_VECTOR_DIMENSIONS
_FAKE_EMBEDDING = [1.0 / (_DIM ** 0.5)] * _DIM  # unit-ish vector


def _reader_token(reader: Reader) -> str:
    return create_access_token(str(reader.id), "reader")


def _author_token(author: Author) -> str:
    return create_access_token(str(author.id), "author")


async def _make_ready_snippet(db_session, *, username_suffix: str = ""):
    """Create an Author + Book + *ready* Snippet and flush to DB."""
    suffix = username_suffix or str(uuid.uuid4())[:8]
    author = Author(
        username=f"author_{suffix}",
        email=f"author_{suffix}@example.com",
        password_hash="hashed",
    )
    book = Book(
        author=author,
        title=f"Book {suffix}",
        external_url=f"https://example.com/books/{suffix}",
    )
    snippet = Snippet(
        author=author,
        book=book,
        content="The door swung open.",
        chapter_number=1,
        processing_status=ProcessingStatus.ready,
    )
    db_session.add_all([author, book, snippet])
    await db_session.commit()
    return author, book, snippet


async def _make_reader(db_session, *, suffix: str = "") -> Reader:
    suffix = suffix or str(uuid.uuid4())[:8]
    reader = Reader(
        username=f"reader_{suffix}",
        email=f"reader_{suffix}@example.com",
        password_hash="hashed",
    )
    db_session.add(reader)
    await db_session.commit()
    return reader


# ---------------------------------------------------------------------------
# Happy-path: successful interaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_view_engagement(client, db_session):
    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "view",
                "read_duration_seconds": 5,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["event_recorded"] is True
    assert body["vector_update_count"] == 1


@pytest.mark.asyncio
async def test_successful_read_complete_engagement(client, db_session):
    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "read_complete",
                "read_duration_seconds": 120,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert response.status_code == 200
    assert response.json()["vector_update_count"] == 1


# ---------------------------------------------------------------------------
# Engagement row is persisted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engagement_row_persisted(client, db_session):
    from sqlalchemy import select

    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "tap_through",
                "read_duration_seconds": 0,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    result = await db_session.execute(
        select(EngagementEvent).where(
            EngagementEvent.reader_id == reader.id,
            EngagementEvent.snippet_id == snippet.id,
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.event_type == EngagementEventType.tap_through


# ---------------------------------------------------------------------------
# Preference vector is updated on the reader
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preference_vector_updated(client, db_session):
    from sqlalchemy import select

    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)
    assert reader.preference_vector == []

    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "read_complete",
                "read_duration_seconds": 60,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    # Re-fetch the reader from DB to confirm persistence
    result = await db_session.execute(
        select(Reader).where(Reader.id == reader.id)
    )
    updated_reader = result.scalar_one()
    assert len(updated_reader.preference_vector) == _DIM
    assert updated_reader.vector_update_count == 1


# ---------------------------------------------------------------------------
# vector_update_count increments on repeated interactions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_update_count_increments(client, db_session):
    from sqlalchemy import select

    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    for expected_count in range(1, 4):
        with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
            response = await client.post(
                "/engage",
                json={
                    "snippet_id": str(snippet.id),
                    "event_type": "view",
                    "read_duration_seconds": 3,
                },
                headers={"Authorization": f"Bearer {_reader_token(reader)}"},
            )
        assert response.json()["vector_update_count"] == expected_count

    result = await db_session.execute(
        select(Reader).where(Reader.id == reader.id)
    )
    assert result.scalar_one().vector_update_count == 3


# ---------------------------------------------------------------------------
# Error: snippet not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_snippet_returns_404(client, db_session):
    reader = await _make_reader(db_session)

    response = await client.post(
        "/engage",
        json={
            "snippet_id": str(uuid.uuid4()),
            "event_type": "view",
            "read_duration_seconds": 0,
        },
        headers={"Authorization": f"Bearer {_reader_token(reader)}"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Error: snippet not READY
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_snippet_returns_400(client, db_session):
    suffix = str(uuid.uuid4())[:8]
    author = Author(
        username=f"auth_{suffix}",
        email=f"auth_{suffix}@example.com",
        password_hash="hashed",
    )
    book = Book(author=author, title="Pending Book", external_url="https://example.com/pending")
    snippet = Snippet(
        author=author,
        book=book,
        content="...",
        chapter_number=1,
        processing_status=ProcessingStatus.pending,  # NOT ready
    )
    reader = Reader(
        username=f"rdr_{suffix}",
        email=f"rdr_{suffix}@example.com",
        password_hash="hashed",
    )
    db_session.add_all([author, book, snippet, reader])
    await db_session.commit()

    response = await client.post(
        "/engage",
        json={
            "snippet_id": str(snippet.id),
            "event_type": "view",
            "read_duration_seconds": 0,
        },
        headers={"Authorization": f"Bearer {_reader_token(reader)}"},
    )

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"]


@pytest.mark.asyncio
async def test_processing_snippet_returns_400(client, db_session):
    suffix = str(uuid.uuid4())[:8]
    author = Author(
        username=f"auth2_{suffix}",
        email=f"auth2_{suffix}@example.com",
        password_hash="hashed",
    )
    book = Book(
        author=author,
        title="Processing Book",
        external_url="https://example.com/processing",
    )
    snippet = Snippet(
        author=author,
        book=book,
        content="...",
        chapter_number=1,
        processing_status=ProcessingStatus.processing,
    )
    reader = Reader(
        username=f"rdr2_{suffix}",
        email=f"rdr2_{suffix}@example.com",
        password_hash="hashed",
    )
    db_session.add_all([author, book, snippet, reader])
    await db_session.commit()

    with patch("app.api.engagement.get_snippet_embedding", return_value=None):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "view",
                "read_duration_seconds": 0,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Error: snippet has no embedding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snippet_without_embedding_returns_400(client, db_session):
    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    # Qdrant returns None → no embedding stored
    with patch("app.api.engagement.get_snippet_embedding", return_value=None):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "view",
                "read_duration_seconds": 0,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert response.status_code == 400
    assert "embedding" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Error: unauthenticated reader
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_request_returns_401(client, db_session):
    _, _, snippet = await _make_ready_snippet(db_session)

    response = await client.post(
        "/engage",
        json={
            "snippet_id": str(snippet.id),
            "event_type": "view",
            "read_duration_seconds": 0,
        },
        # No Authorization header
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_author_token_rejected_for_engage(client, db_session):
    author, _, snippet = await _make_ready_snippet(db_session)

    # Author JWT should NOT be accepted by get_current_reader
    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "view",
                "read_duration_seconds": 0,
            },
            headers={"Authorization": f"Bearer {_author_token(author)}"},
        )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Rollback on Qdrant failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_when_preference_engine_raises(client, db_session):
    """If update_preference_vector raises (e.g. corrupted vector), the DB
    transaction must be rolled back.

    We verify this indirectly: after the failed request the endpoint returns
    500, and a subsequent *successful* engagement should produce
    vector_update_count == 1 (not 2), proving the failed attempt was not
    committed.
    """
    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    # First call: preference engine raises → expect 500
    with (
        patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING),
        patch(
            "app.api.engagement.update_preference_vector",
            side_effect=ValueError("simulated engine failure"),
        ),
    ):
        failed_response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "read_complete",
                "read_duration_seconds": 90,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert failed_response.status_code == 500

    # Second call: normal execution — update_count should be 1, not 2
    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        ok_response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "view",
                "read_duration_seconds": 5,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert ok_response.status_code == 200
    assert ok_response.json()["vector_update_count"] == 1, (
        "update_count should be 1 — the failed attempt must not have been committed"
    )


# ---------------------------------------------------------------------------
# All four event types are accepted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type",
    ["view", "tap_through", "skip", "read_complete"],
)
async def test_all_event_types_accepted(client, db_session, event_type):
    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": event_type,
                "read_duration_seconds": 10,
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert response.status_code == 200, response.json()


# ---------------------------------------------------------------------------
# read_duration_seconds defaults to 0 when omitted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_duration_defaults_to_zero(client, db_session):
    from sqlalchemy import select

    _, _, snippet = await _make_ready_snippet(db_session)
    reader = await _make_reader(db_session)

    with patch("app.api.engagement.get_snippet_embedding", return_value=_FAKE_EMBEDDING):
        response = await client.post(
            "/engage",
            json={
                "snippet_id": str(snippet.id),
                "event_type": "view",
                # read_duration_seconds omitted intentionally
            },
            headers={"Authorization": f"Bearer {_reader_token(reader)}"},
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(EngagementEvent).where(EngagementEvent.reader_id == reader.id)
    )
    event = result.scalar_one()
    assert event.read_duration_seconds == 0
