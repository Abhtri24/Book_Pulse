import json
import httpx
import pytest

from app.config import get_settings
from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.services.quality_agent import (
    analyze_readability,
    query_top_snippets,
    run_quality_agent,
    QualityAgentServiceError,
    QualityAgentResponseError,
)

SAMPLE_TEXT = (
    "The rain fell hard on the city streets. "
    "She ran without looking back. "
    "Every shadow seemed to follow her."
)


def test_analyze_readability_returns_structured_metrics():
    metrics = analyze_readability(SAMPLE_TEXT)

    assert metrics.flesch_reading_ease == 84.64
    assert metrics.flesch_kincaid_grade == 3.03
    assert metrics.avg_sentence_length == 6.33
    assert metrics.word_count == 19
    assert metrics.sentence_count == 3


def test_analyze_readability_serializes_to_dict():
    metrics = analyze_readability(SAMPLE_TEXT)
    payload = metrics.model_dump()

    assert set(payload) == {
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "avg_sentence_length",
        "word_count",
        "sentence_count",
    }
    assert all(isinstance(payload[key], (int, float)) for key in payload)


def test_analyze_readability_rejects_empty_text():
    with pytest.raises(ValueError, match="text must not be empty"):
        analyze_readability("   ")


@pytest.mark.asyncio
async def test_query_top_snippets_filters_and_orders(db_session):
    author = Author(username="a", email="a@example.com", password_hash="hash")
    book = Book(author=author, title="Book", external_url="https://example.com/book")

    # Snippet in target genre
    s1 = Snippet(author=author, book=book, content="Content 1 " * 50, chapter_number=1)
    m1 = SnippetMetadata(
        snippet=s1,
        primary_genre="Fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="neutral",
        hook_type="action",
        readability_score=80.0,
        hook_score=90,
        quality_score=86.0,
        classifier_model="test-classifier",
    )

    # Another snippet in target genre but lower score
    s2 = Snippet(author=author, book=book, content="Content 2 " * 50, chapter_number=2)
    m2 = SnippetMetadata(
        snippet=s2,
        primary_genre="fantasy",  # test case insensitivity
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="neutral",
        hook_type="action",
        readability_score=70.0,
        hook_score=80,
        quality_score=76.0,
        classifier_model="test-classifier",
    )

    # Snippet in different genre
    s3 = Snippet(author=author, book=book, content="Content 3 " * 50, chapter_number=3)
    m3 = SnippetMetadata(
        snippet=s3,
        primary_genre="Sci-Fi",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="neutral",
        hook_type="action",
        readability_score=90.0,
        hook_score=90,
        quality_score=90.0,
        classifier_model="test-classifier",
    )

    db_session.add_all([author, book, s1, m1, s2, m2, s3, m3])
    await db_session.commit()

    # Query fantasy snippets
    results = await query_top_snippets(db_session, "fantasy", limit=5)
    assert len(results) == 2
    assert results[0]["content"] == s1.content
    assert results[0]["quality_score"] == 86.0
    assert results[1]["content"] == s2.content
    assert results[1]["quality_score"] == 76.0


@pytest.mark.asyncio
async def test_run_quality_agent_success(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_QUALITY_MODEL", "test-model")
    get_settings.cache_clear()

    author = Author(username="a", email="a@example.com", password_hash="hash")
    book = Book(author=author, title="Book", external_url="https://example.com/book")
    snippet = Snippet(author=author, book=book, content="Once upon a time in a faraway kingdom.", chapter_number=1)

    db_session.add(author)
    db_session.add(book)
    db_session.add(snippet)
    await db_session.commit()
    await db_session.refresh(snippet)

    # Seed a reference snippet
    ref_snippet = Snippet(author=author, book=book, content="High quality reference snippet content.", chapter_number=2)
    ref_meta = SnippetMetadata(
        snippet=ref_snippet,
        primary_genre="Fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="neutral",
        hook_type="action",
        readability_score=80.0,
        hook_score=90,
        quality_score=86.0,
        classifier_model="test-classifier",
    )
    db_session.add(ref_snippet)
    db_session.add(ref_meta)
    await db_session.commit()

    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        body = json.loads(request.content)

        messages = body["messages"]
        last_message = messages[-1]

        if last_message["role"] == "tool":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps({
                                    "strengths": ["Strong setting"],
                                    "improvements": ["Tighten dialogue"],
                                    "hook_score": 8,
                                    "rewrite_suggestion": "Open with action."
                                })
                            }
                        }
                    ]
                }
            )
        else:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "query_top_snippets",
                                            "arguments": json.dumps({"genre": "Fantasy", "limit": 1})
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feedback = await run_quality_agent(snippet, "Fantasy", db_session, client=client)

    assert feedback.strengths == ["Strong setting"]
    assert feedback.improvements == ["Tighten dialogue"]
    assert feedback.hook_score == 8
    assert feedback.rewrite_suggestion == "Open with action."

    assert len(captured_requests) == 2
    first_payload = json.loads(captured_requests[0].content)
    system_prompt = " ".join(first_payload["messages"][0]["content"].split())
    assert "0-100 scale" in system_prompt
    assert "final `hook_score` must be" in system_prompt
    assert "independent integer from 1 to 10" in system_prompt
    assert "Do NOT copy" in system_prompt
    assert "`hook_score: 65`" in system_prompt
    assert "might be 7" in system_prompt
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_quality_agent_retries_on_malformed_json(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    author = Author(username="a2", email="a2@example.com", password_hash="hash")
    book = Book(author=author, title="Book", external_url="https://example.com/book")
    snippet = Snippet(author=author, book=book, content="Sample content for retry test.", chapter_number=1)

    db_session.add(author)
    db_session.add(book)
    db_session.add(snippet)
    await db_session.commit()

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            content = "{bad_json"
        else:
            content = json.dumps({
                "strengths": ["Fine word choice"],
                "improvements": ["None"],
                "hook_score": 7,
                "rewrite_suggestion": "None."
            })

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content
                        }
                    }
                ]
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feedback = await run_quality_agent(snippet, "Fantasy", db_session, client=client)

    assert attempts == 2
    assert feedback.hook_score == 7
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_quality_agent_fails_after_retry(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    author = Author(username="a3", email="a3@example.com", password_hash="hash")
    book = Book(author=author, title="Book", external_url="https://example.com/book")
    snippet = Snippet(author=author, book=book, content="Sample content for failure test.", chapter_number=1)

    db_session.add(author)
    db_session.add(book)
    db_session.add(snippet)
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "{invalid"
                        }
                    }
                ]
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(QualityAgentResponseError, match="Agent returned malformed JSON"):
            await run_quality_agent(snippet, "Fantasy", db_session, client=client)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_quality_agent_missing_api_key(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()

    author = Author(username="a4", email="a4@example.com", password_hash="hash")
    book = Book(author=author, title="Book", external_url="https://example.com/book")
    snippet = Snippet(author=author, book=book, content="Sample content.", chapter_number=1)

    db_session.add(author)
    db_session.add(book)
    db_session.add(snippet)
    await db_session.commit()

    with pytest.raises(QualityAgentServiceError, match="GROQ_API_KEY is required"):
        await run_quality_agent(snippet, "Fantasy", db_session)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_quality_agent_executes_readability_and_hook_tools(monkeypatch, db_session):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    author = Author(username="a5", email="a5@example.com", password_hash="hash")
    book = Book(author=author, title="Book", external_url="https://example.com/book")
    snippet = Snippet(author=author, book=book, content=SAMPLE_TEXT, chapter_number=1)

    db_session.add(author)
    db_session.add(book)
    db_session.add(snippet)
    await db_session.commit()
    await db_session.refresh(snippet)

    tool_execution_order = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        messages = body["messages"]
        last_message = messages[-1]

        if last_message["role"] == "tool":
            tool_name = last_message["name"]
            tool_execution_order.append(tool_name)

            if len(tool_execution_order) >= 2:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": json.dumps({
                                        "strengths": ["Analyzed readability and hook"],
                                        "improvements": ["None"],
                                        "hook_score": 9,
                                        "rewrite_suggestion": "Keep it up."
                                    })
                                }
                            }
                        ]
                    }
                )
            next_tool = "check_hook_strength" if tool_name == "analyze_readability" else "analyze_readability"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": f"call_{next_tool}",
                                        "type": "function",
                                        "function": {
                                            "name": next_tool,
                                            "arguments": json.dumps({"text": SAMPLE_TEXT})
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
        else:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_readability",
                                        "type": "function",
                                        "function": {
                                            "name": "analyze_readability",
                                            "arguments": json.dumps({"text": SAMPLE_TEXT})
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feedback = await run_quality_agent(snippet, "Fantasy", db_session, client=client)

    assert feedback.hook_score == 9
    assert "analyze_readability" in tool_execution_order
    assert "check_hook_strength" in tool_execution_order
    get_settings.cache_clear()
