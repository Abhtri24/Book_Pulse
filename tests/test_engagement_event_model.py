import pytest
from sqlalchemy import select

from app.models.author import Author
from app.models.book import Book
from app.models.engagement_event import EngagementEvent, EngagementEventType
from app.models.reader import PREFERENCE_VECTOR_DIMENSIONS, Reader
from app.models.snippet import Snippet


@pytest.mark.asyncio
async def test_engagement_event_links_reader_and_snippet(db_session):
    author = Author(
        username="phasefiveauthor",
        email="phasefive-author@example.com",
        password_hash="hashed",
    )
    reader = Reader(
        username="phasefivereader",
        email="phasefive-reader@example.com",
        password_hash="hashed",
    )
    book = Book(author=author, title="Signals", description="A test book.")
    snippet = Snippet(
        author=author,
        book=book,
        content="The first line caught and held.",
        chapter_number=1,
    )
    event = EngagementEvent(
        reader=reader,
        snippet=snippet,
        event_type=EngagementEventType.read_complete,
        read_duration_seconds=42,
    )

    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(select(EngagementEvent))
    saved_event = result.scalar_one()

    assert saved_event.reader_id == reader.id
    assert saved_event.snippet_id == snippet.id
    assert saved_event.event_type == EngagementEventType.read_complete
    assert saved_event.read_duration_seconds == 42


def test_reader_preference_vector_defaults_to_empty_vector():
    reader = Reader(username="reader", email="reader@example.com", password_hash="hashed")

    assert reader.preference_vector == []
    assert reader.vector_update_count == 0


def test_reader_preference_vector_allows_embedding_dimension():
    vector = [0.1] * PREFERENCE_VECTOR_DIMENSIONS
    reader = Reader(
        username="reader",
        email="reader@example.com",
        password_hash="hashed",
        preference_vector=vector,
    )

    assert reader.preference_vector == vector


def test_reader_preference_vector_rejects_wrong_dimension():
    with pytest.raises(ValueError, match="384 dimensions"):
        Reader(
            username="reader",
            email="reader@example.com",
            password_hash="hashed",
            preference_vector=[0.1, 0.2],
        )
