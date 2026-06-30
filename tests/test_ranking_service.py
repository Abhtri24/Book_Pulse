import pytest

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.services.ranking_service import (
    get_top_by_hook,
    get_top_by_quality,
    get_top_by_readability,
)


async def seed_ranking_data(db_session):
    author = Author(
        username="author1",
        email="author1@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Book 1", external_url="https://example.com/book-1")

    # Snippet A: Quality Score = 80*0.6 + 60*0.4 = 72.0
    # Hook Score = 80, Readability = 60
    snippet_a = Snippet(author=author, book=book, content="A" * 200, chapter_number=1)
    meta_a = SnippetMetadata(
        snippet=snippet_a,
        primary_genre="fantasy",
        sub_genres=["epic"],
        pov="third_person",
        pacing="fast",
        tone="serious",
        hook_type="mystery",
        readability_score=60.0,
        quality_score=72.0,
        hook_score=80,
        classifier_model="model",
    )

    # Snippet B: Quality Score = 50*0.6 + 90*0.4 = 66.0
    # Hook Score = 50, Readability = 90
    snippet_b = Snippet(author=author, book=book, content="B" * 200, chapter_number=2)
    meta_b = SnippetMetadata(
        snippet=snippet_b,
        primary_genre="sci-fi",
        sub_genres=["space"],
        pov="third_person",
        pacing="moderate",
        tone="neutral",
        hook_type="action",
        readability_score=90.0,
        quality_score=66.0,
        hook_score=50,
        classifier_model="model",
    )

    # Snippet C: Quality Score = 90*0.6 + 50*0.4 = 74.0
    # Hook Score = 90, Readability = 50
    snippet_c = Snippet(author=author, book=book, content="C" * 200, chapter_number=3)
    meta_c = SnippetMetadata(
        snippet=snippet_c,
        primary_genre="romance",
        sub_genres=[],
        pov="first_person",
        pacing="slow",
        tone="warm",
        hook_type="dialogue",
        readability_score=50.0,
        quality_score=74.0,
        hook_score=90,
        classifier_model="model",
    )

    db_session.add_all([
        author,
        book,
        snippet_a,
        meta_a,
        snippet_b,
        meta_b,
        snippet_c,
        meta_c,
    ])
    await db_session.commit()
    return snippet_a, snippet_b, snippet_c


@pytest.mark.asyncio
async def test_ranking_by_quality(db_session):
    s_a, s_b, s_c = await seed_ranking_data(db_session)
    results = await get_top_by_quality(db_session, limit=2)
    assert len(results) == 2
    assert results[0]["snippet_id"] == s_c.id
    assert results[0]["quality_score"] == 74.0
    assert results[1]["snippet_id"] == s_a.id
    assert results[1]["quality_score"] == 72.0


@pytest.mark.asyncio
async def test_ranking_by_hook(db_session):
    s_a, s_b, s_c = await seed_ranking_data(db_session)
    results = await get_top_by_hook(db_session, limit=10)
    assert len(results) == 3
    assert results[0]["snippet_id"] == s_c.id
    assert results[0]["hook_score"] == 90
    assert results[1]["snippet_id"] == s_a.id
    assert results[1]["hook_score"] == 80
    assert results[2]["snippet_id"] == s_b.id
    assert results[2]["hook_score"] == 50


@pytest.mark.asyncio
async def test_ranking_by_readability(db_session):
    s_a, s_b, s_c = await seed_ranking_data(db_session)
    results = await get_top_by_readability(db_session, limit=10)
    assert len(results) == 3
    assert results[0]["snippet_id"] == s_b.id
    assert results[0]["readability_score"] == 90.0
    assert results[1]["snippet_id"] == s_a.id
    assert results[1]["readability_score"] == 60.0
    assert results[2]["snippet_id"] == s_c.id
    assert results[2]["readability_score"] == 50.0


@pytest.mark.asyncio
async def test_ranking_empty_results(db_session):
    results = await get_top_by_quality(db_session, limit=10)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_api_top_snippets_default_quality(client, db_session):
    s_a, s_b, s_c = await seed_ranking_data(db_session)
    response = await client.get("/snippets/top")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["snippet_id"] == str(s_c.id)
    assert data[0]["quality_score"] == 74.0
    assert data[1]["snippet_id"] == str(s_a.id)
    assert data[1]["quality_score"] == 72.0
    assert data[2]["snippet_id"] == str(s_b.id)
    assert data[2]["quality_score"] == 66.0


@pytest.mark.asyncio
async def test_api_top_snippets_by_hook(client, db_session):
    s_a, s_b, s_c = await seed_ranking_data(db_session)
    response = await client.get("/snippets/top?metric=hook")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["snippet_id"] == str(s_c.id)
    assert data[0]["hook_score"] == 90
    assert data[1]["snippet_id"] == str(s_a.id)
    assert data[1]["hook_score"] == 80
    assert data[2]["snippet_id"] == str(s_b.id)
    assert data[2]["hook_score"] == 50


@pytest.mark.asyncio
async def test_api_top_snippets_by_readability(client, db_session):
    s_a, s_b, s_c = await seed_ranking_data(db_session)
    response = await client.get("/snippets/top?metric=readability")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["snippet_id"] == str(s_b.id)
    assert data[0]["readability_score"] == 90.0
    assert data[1]["snippet_id"] == str(s_a.id)
    assert data[1]["readability_score"] == 60.0
    assert data[2]["snippet_id"] == str(s_c.id)
    assert data[2]["readability_score"] == 50.0


@pytest.mark.asyncio
async def test_api_top_snippets_invalid_metric(client):
    response = await client.get("/snippets/top?metric=invalid")
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported metric"
