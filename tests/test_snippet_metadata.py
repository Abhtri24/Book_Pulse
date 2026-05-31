import pytest
from sqlalchemy import select

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_metadata import SnippetMetadata


@pytest.mark.asyncio
async def test_snippet_metadata_persists_as_one_to_one(db_session):
    author = Author(
        username="metadata-author",
        email="metadata-author@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Metadata Story", description="")
    snippet = Snippet(
        author=author,
        book=book,
        content="sample",
        chapter_number=1,
    )
    metadata = SnippetMetadata(
        snippet=snippet,
        primary_genre="fantasy",
        sub_genres=["epic", "adventure"],
        pov="third_person",
        pacing="fast",
        tone="hopeful",
        hook_type="mystery",
        readability_score=72.5,
        classifier_model="test-classifier",
    )
    db_session.add_all([author, book, snippet, metadata])
    await db_session.commit()

    result = await db_session.execute(select(SnippetMetadata))
    saved_metadata = result.scalar_one()

    assert saved_metadata.snippet_id == snippet.id
    assert saved_metadata.sub_genres == ["epic", "adventure"]
    assert saved_metadata.snippet.metadata_record.primary_genre == "fantasy"
