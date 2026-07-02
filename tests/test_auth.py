import pytest
from sqlalchemy import select

from app.models.reader import Reader


@pytest.mark.asyncio
async def test_register_author_and_login(client):
    register_response = await client.post(
        "/auth/register/author",
        json={
            "username": "storysmith",
            "email": "author@example.com",
            "password": "strong-password",
            "bio": "Fantasy author.",
        },
    )

    assert register_response.status_code == 201
    assert register_response.json()["email"] == "author@example.com"

    login_response = await client.post(
        "/auth/login",
        json={"email": "author@example.com", "password": "strong-password"},
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_protected_route_requires_author_token(client):
    response = await client.post(
        "/books",
        json={
            "title": "No Token",
            "description": "Should fail.",
            "external_url": "https://example.com/book",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_reader_persists_normalized_preferred_genres(client, db_session):
    response = await client.post(
        "/auth/register/reader",
        json={
            "username": "genre_reader",
            "email": "genre-reader@example.com",
            "password": "strong-password",
            "preferred_genres": ["  Fantasy ", "fantasy", " SCI-FI ", ""],
        },
    )

    assert response.status_code == 201
    assert response.json()["preferred_genres"] == ["fantasy", "sci-fi"]
    reader = (
        await db_session.execute(
            select(Reader).where(Reader.email == "genre-reader@example.com")
        )
    ).scalar_one()
    assert reader.preferred_genres == ["fantasy", "sci-fi"]
