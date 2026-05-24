import pytest


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
        json={"title": "No Token", "description": "Should fail."},
    )

    assert response.status_code == 401
