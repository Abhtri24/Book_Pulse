import json

import httpx
import pytest

from app.config import get_settings
from app.services.classifier_service import (
    ClassifierResponseError,
    ClassifierServiceError,
    build_classifier_messages,
    classify_snippet,
)


def test_build_classifier_messages_includes_schema_instructions():
    messages = build_classifier_messages("An opening scene.")

    assert messages[0]["role"] == "system"
    assert "Return only JSON" in messages[0]["content"]
    assert "hook_type" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "An opening scene." in messages[1]["content"]


@pytest.mark.asyncio
async def test_classify_snippet_calls_groq_and_returns_validated_result(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_CLASSIFIER_MODEL", "test-model")
    get_settings.cache_clear()
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["authorization"] = request.headers["Authorization"]
        captured_request["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "primary_genre": " Fantasy ",
                                    "sub_genres": ["Epic"],
                                    "pov": "third_person",
                                    "pacing": "fast",
                                    "tone": "Hopeful",
                                    "hook_type": "mystery",
                                    "readability_score": 81.0,
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await classify_snippet("A mysterious door opens.", client=client)

    assert captured_request["authorization"] == "Bearer test-key"
    assert captured_request["body"]["model"] == "test-model"
    assert captured_request["body"]["temperature"] == 0
    assert captured_request["body"]["response_format"] == {"type": "json_object"}
    assert result.primary_genre == "fantasy"
    assert result.classifier_model == "test-model"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_classify_snippet_requires_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(ClassifierServiceError, match="GROQ_API_KEY"):
        await classify_snippet("A mysterious door opens.")

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_classify_snippet_retries_after_malformed_json(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_CLASSIFIER_MODEL", "test-model")
    get_settings.cache_clear()
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            content = "{not-json"
        else:
            content = json.dumps(
                {
                    "primary_genre": "fantasy",
                    "sub_genres": ["portal"],
                    "pov": "third_person",
                    "pacing": "moderate",
                    "tone": "curious",
                    "hook_type": "mystery",
                    "readability_score": 77,
                }
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await classify_snippet("A door appears in the wall.", client=client)

    assert attempts == 2
    assert result.primary_genre == "fantasy"
    assert result.classifier_model == "test-model"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_classify_snippet_retries_after_invalid_schema(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_CLASSIFIER_MODEL", "test-model")
    get_settings.cache_clear()
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            content = json.dumps(
                {
                    "primary_genre": "fantasy",
                    "sub_genres": [],
                    "pov": "over_shoulder",
                    "pacing": "moderate",
                    "tone": "curious",
                    "hook_type": "mystery",
                    "readability_score": 77,
                }
            )
        else:
            content = json.dumps(
                {
                    "primary_genre": "fantasy",
                    "sub_genres": [],
                    "pov": "third_person",
                    "pacing": "moderate",
                    "tone": "curious",
                    "hook_type": "mystery",
                    "readability_score": 77,
                }
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await classify_snippet("A door appears in the wall.", client=client)

    assert attempts == 2
    assert result.pov == "third_person"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_classify_snippet_fails_after_two_invalid_outputs(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{not-json"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ClassifierResponseError, match="invalid structured output"):
            await classify_snippet("A door appears in the wall.", client=client)

    assert attempts == 2
    get_settings.cache_clear()
