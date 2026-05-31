import pytest

from app.tasks import snippet_pipeline


async def register_and_login_author(client) -> str:
    await client.post(
        "/auth/register/author",
        json={
            "username": "novelist",
            "email": "novelist@example.com",
            "password": "strong-password",
            "bio": "",
        },
    )
    login_response = await client.post(
        "/auth/login",
        json={"email": "novelist@example.com", "password": "strong-password"},
    )
    return login_response.json()["access_token"]


def make_snippet(word_count: int) -> str:
    return " ".join(f"word{i}" for i in range(word_count))


@pytest.mark.asyncio
async def test_author_can_create_book_and_upload_valid_snippet(monkeypatch, client):
    class FakeProcessSnippetTask:
        @staticmethod
        def delay(snippet_id: str) -> None:
            return None

    monkeypatch.setattr(snippet_pipeline, "process_snippet", FakeProcessSnippetTask)

    token = await register_and_login_author(client)
    headers = {"Authorization": f"Bearer {token}"}

    book_response = await client.post(
        "/books",
        json={"title": "The First Ember", "description": "A discovery fantasy."},
        headers=headers,
    )

    assert book_response.status_code == 201
    book_id = book_response.json()["id"]

    snippet_response = await client.post(
        f"/books/{book_id}/snippets",
        json={"content": make_snippet(200), "chapter_number": 1},
        headers=headers,
    )

    assert snippet_response.status_code == 201
    body = snippet_response.json()
    assert body["book_id"] == book_id
    assert body["processing_status"] == "pending"


@pytest.mark.asyncio
async def test_snippet_upload_schedules_processing(monkeypatch, client):
    scheduled_snippet_ids = []

    class FakeProcessSnippetTask:
        @staticmethod
        def delay(snippet_id: str) -> None:
            scheduled_snippet_ids.append(snippet_id)

    monkeypatch.setattr(snippet_pipeline, "process_snippet", FakeProcessSnippetTask)

    token = await register_and_login_author(client)
    headers = {"Authorization": f"Bearer {token}"}
    book_response = await client.post(
        "/books",
        json={"title": "Queued Story", "description": ""},
        headers=headers,
    )
    book_id = book_response.json()["id"]

    snippet_response = await client.post(
        f"/books/{book_id}/snippets",
        json={"content": make_snippet(200), "chapter_number": 1},
        headers=headers,
    )

    assert snippet_response.status_code == 201
    body = snippet_response.json()
    assert body["processing_status"] == "pending"
    assert scheduled_snippet_ids == [body["id"]]


@pytest.mark.asyncio
async def test_snippet_upload_enforces_word_count(client):
    token = await register_and_login_author(client)
    headers = {"Authorization": f"Bearer {token}"}
    book_response = await client.post(
        "/books",
        json={"title": "Short Hook", "description": ""},
        headers=headers,
    )
    book_id = book_response.json()["id"]

    response = await client.post(
        f"/books/{book_id}/snippets",
        json={"content": make_snippet(199), "chapter_number": 1},
        headers=headers,
    )

    assert response.status_code == 422
