import uuid

import pytest

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_feedback import SnippetFeedback
from app.services.auth_service import create_access_token


async def create_feedback_fixture(db_session):
    owner = Author(username="owner", email="owner@example.com", password_hash="hash")
    other = Author(username="other", email="other@example.com", password_hash="hash")
    book = Book(author=owner, title="Owned Book")
    snippet = Snippet(author=owner, book=book, content="sample", chapter_number=1)
    feedback = SnippetFeedback(
        snippet=snippet,
        strengths=["Strong voice"],
        improvements=["Trim exposition"],
        hook_score=8,
        rewrite_suggestion="Open on the conflict.",
    )
    db_session.add_all([owner, other, book, snippet, feedback])
    await db_session.commit()
    return owner, other, book, snippet


@pytest.mark.asyncio
async def test_correct_author_gets_feedback(client, db_session):
    owner, _, book, snippet = await create_feedback_fixture(db_session)
    token = create_access_token(str(owner.id), "author")

    response = await client.get(
        f"/books/{book.id}/snippets/{snippet.id}/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["strengths"] == ["Strong voice"]


@pytest.mark.asyncio
async def test_wrong_author_receives_403(client, db_session):
    _, other, book, snippet = await create_feedback_fixture(db_session)
    token = create_access_token(str(other.id), "author")

    response = await client.get(
        f"/books/{book.id}/snippets/{snippet.id}/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_anonymous_receives_401(client, db_session):
    _, _, book, snippet = await create_feedback_fixture(db_session)

    response = await client.get(f"/books/{book.id}/snippets/{snippet.id}/feedback")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_feedback_returns_404(client, db_session):
    author = Author(username="nofeedback", email="nofeedback@example.com", password_hash="hash")
    book = Book(author=author, title="No Feedback")
    snippet = Snippet(author=author, book=book, content="sample", chapter_number=1)
    db_session.add_all([author, book, snippet])
    await db_session.commit()
    token = create_access_token(str(author.id), "author")

    response = await client.get(
        f"/books/{book.id}/snippets/{snippet.id}/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_snippet_must_belong_to_book(client, db_session):
    owner = Author(username="owner2", email="owner2@example.com", password_hash="hash")
    book = Book(author=owner, title="Book One")
    other_book = Book(author=owner, title="Book Two")
    snippet = Snippet(author=owner, book=other_book, content="sample", chapter_number=1)
    db_session.add_all([owner, book, other_book, snippet])
    await db_session.commit()
    token = create_access_token(str(owner.id), "author")

    response = await client.get(
        f"/books/{book.id}/snippets/{snippet.id}/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
