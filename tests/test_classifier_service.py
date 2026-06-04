import json

import httpx
import pytest

from app.config import get_settings
from app.services.classifier_service import (
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
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ClassifierServiceError, match="GROQ_API_KEY"):
        await classify_snippet("A mysterious door opens.")

    get_settings.cache_clear()
