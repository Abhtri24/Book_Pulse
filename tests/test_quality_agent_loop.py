import json

import httpx
import pytest

from app.config import get_settings
from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.services.quality_agent import run_quality_agent


@pytest.mark.asyncio
async def test_mocked_groq_response_json_validation(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    author = Author(username="loop", email="loop@example.com", password_hash="hash")
    book = Book(author=author, title="Loop Book", external_url="https://example.com/loop")
    snippet = Snippet(author=author, book=book, content="The door opened before she knocked.", chapter_number=1)
    db_session.add_all([author, book, snippet])
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps({
                "strengths": ["Immediate tension"],
                "improvements": ["Ground the setting"],
                "hook_score": 8,
                "rewrite_suggestion": "Add a sensory detail."
            })}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feedback = await run_quality_agent(snippet, "Mystery", db_session, client=client)

    assert feedback.hook_score == 8
    assert feedback.strengths == ["Immediate tension"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_mocked_tool_calls(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    author = Author(username="tools", email="tools@example.com", password_hash="hash")
    book = Book(author=author, title="Tool Book", external_url="https://example.com/tool")
    snippet = Snippet(author=author, book=book, content="The rain fell hard. She ran.", chapter_number=1)
    db_session.add_all([author, book, snippet])
    await db_session.commit()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        last = body["messages"][-1]
        if last["role"] == "tool":
            calls.append(last["name"])
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": json.dumps({
                    "strengths": ["Kinetic opening"],
                    "improvements": ["Clarify stakes"],
                    "hook_score": 7,
                    "rewrite_suggestion": "Name what she fears."
                })}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_hook",
                "type": "function",
                "function": {"name": "check_hook_strength", "arguments": json.dumps({"text": snippet.content})},
            }]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feedback = await run_quality_agent(snippet, "Thriller", db_session, client=client)

    assert feedback.hook_score == 7
    assert calls == ["check_hook_strength"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_malformed_response_retry_path(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    author = Author(username="retry", email="retry@example.com", password_hash="hash")
    book = Book(author=author, title="Retry Book", external_url="https://example.com/retry")
    snippet = Snippet(author=author, book=book, content="A clock stopped at midnight.", chapter_number=1)
    db_session.add_all([author, book, snippet])
    await db_session.commit()
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        content = "{broken" if attempts == 1 else json.dumps({
            "strengths": ["Clean image"],
            "improvements": ["Increase urgency"],
            "hook_score": 6,
            "rewrite_suggestion": "Tie the stopped clock to danger.",
        })
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feedback = await run_quality_agent(snippet, "Fantasy", db_session, client=client)

    assert attempts == 2
    assert feedback.rewrite_suggestion.startswith("Tie the stopped clock")
    get_settings.cache_clear()
