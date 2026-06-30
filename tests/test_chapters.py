from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.author import Author
from app.models.book import Book
from app.models.chapter import Chapter


async def register_and_login_author(client, suffix: str = "one") -> str:
    await client.post(
        "/auth/register/author",
        json={
            "username": f"author-{suffix}",
            "email": f"author-{suffix}@example.com",
            "password": "strong-password",
            "bio": "",
        },
    )
    response = await client.post(
        "/auth/login",
        json={"email": f"author-{suffix}@example.com", "password": "strong-password"},
    )
    return response.json()["access_token"]


async def create_book(client, token: str, title: str = "A Book") -> str:
    response = await client.post(
        "/books",
        json={
            "title": title,
            "description": "",
            "external_url": "https://example.com/chapter-test-book",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_chapter_relationships_and_word_count(db_session):
    author = Author(
        username="model-author",
        email="model@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Model Book", external_url="https://example.com/model")
    chapter = Chapter(
        book=book,
        chapter_number=1,
        title="Opening",
        content="One  two\nthree.",
    )
    db_session.add(chapter)
    await db_session.commit()

    result = await db_session.execute(
        select(Book).options(selectinload(Book.chapters)).where(Book.id == book.id)
    )
    stored_book = result.scalar_one()
    assert stored_book.chapters == [chapter]
    assert chapter.book is book
    assert chapter.word_count == 3


@pytest.mark.asyncio
async def test_chapter_unique_constraint(db_session):
    author = Author(
        username="unique-author",
        email="unique@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Unique Book", external_url="https://example.com/unique")
    db_session.add_all(
        [
            Chapter(book=book, chapter_number=1, title="First", content="First chapter"),
            Chapter(book=book, chapter_number=1, title="Again", content="Duplicate chapter"),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_successful_chapter_upload(client, db_session):
    token = await register_and_login_author(client)
    book_id = await create_book(client, token)
    response = await client.post(
        f"/books/{book_id}/chapters",
        json={"chapter_number": 1, "title": "Arrival", "content": "The ship came home."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["book_id"] == book_id
    assert body["chapter_number"] == 1
    assert body["word_count"] == 4
    assert body["created_at"]
    assert body["updated_at"]
    stored = await db_session.get(Chapter, UUID(body["id"]))
    assert stored.content == "The ship came home."


@pytest.mark.asyncio
async def test_chapter_upload_requires_authentication(client):
    response = await client.post(
        f"/books/{uuid4()}/chapters",
        json={"chapter_number": 1, "title": "No", "content": "Not authorized"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chapter_upload_rejects_wrong_author(client):
    owner_token = await register_and_login_author(client, "owner")
    other_token = await register_and_login_author(client, "other")
    book_id = await create_book(client, owner_token)
    response = await client.post(
        f"/books/{book_id}/chapters",
        json={"chapter_number": 1, "title": "Intrusion", "content": "Wrong author"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_chapter_upload_rejects_duplicate_number(client):
    token = await register_and_login_author(client)
    book_id = await create_book(client, token)
    payload = {"chapter_number": 1, "title": "One", "content": "Chapter one"}
    assert (await client.post(
        f"/books/{book_id}/chapters", json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )).status_code == 201
    response = await client.post(
        f"/books/{book_id}/chapters", json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "missing_field"),
    [
        ({"chapter_number": 0, "title": "Bad", "content": "Text"}, None),
        ({"chapter_number": -1, "title": "Bad", "content": "Text"}, None),
        ({"chapter_number": 1, "title": "Bad", "content": "   \n"}, None),
        ({"title": "Missing number", "content": "Text"}, "chapter_number"),
        ({"chapter_number": 1, "content": "Text"}, "title"),
        ({"chapter_number": 1, "title": "Missing content"}, "content"),
    ],
)
async def test_chapter_upload_validation(client, payload, missing_field):
    token = await register_and_login_author(client)
    book_id = await create_book(client, token)
    response = await client.post(
        f"/books/{book_id}/chapters",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    if missing_field:
        assert any(error["loc"][-1] == missing_field for error in response.json()["detail"])


@pytest.mark.asyncio
async def test_different_books_can_each_have_chapter_one(client):
    token = await register_and_login_author(client)
    first_book = await create_book(client, token, "First")
    second_book = await create_book(client, token, "Second")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"chapter_number": 1, "title": "Opening", "content": "Once upon a time"}

    first = await client.post(f"/books/{first_book}/chapters", json=payload, headers=headers)
    second = await client.post(f"/books/{second_book}/chapters", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201


@pytest.mark.asyncio
async def test_author_workflow_uploads_two_retrievable_chapters(client, db_session):
    token = await register_and_login_author(client, "workflow")
    book_id = await create_book(client, token, "Workflow Book")
    headers = {"Authorization": f"Bearer {token}"}

    for number in (1, 2):
        response = await client.post(
            f"/books/{book_id}/chapters",
            json={
                "chapter_number": number,
                "title": f"Chapter {number}",
                "content": f"Full text for chapter {number}",
            },
            headers=headers,
        )
        assert response.status_code == 201

    result = await db_session.execute(
        select(Chapter)
        .where(Chapter.book_id == UUID(book_id))
        .order_by(Chapter.chapter_number)
    )
    chapters = list(result.scalars())
    assert [chapter.chapter_number for chapter in chapters] == [1, 2]
    assert [chapter.title for chapter in chapters] == ["Chapter 1", "Chapter 2"]
