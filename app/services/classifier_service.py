import json

import httpx

from app.config import get_settings
from app.schemas.classifier import ClassifierResult

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

CLASSIFIER_SYSTEM_PROMPT = """
You classify fiction snippets for a book discovery recommendation system.
Return only JSON with these exact fields:
primary_genre, sub_genres, pov, pacing, tone, hook_type, readability_score, classifier_model.

Allowed values:
pov: first_person, second_person, third_person, multiple
pacing: slow, moderate, fast
hook_type: action, dialogue, mystery, character, worldbuilding, emotional

readability_score must be a number from 0 to 100.
""".strip()


class ClassifierServiceError(RuntimeError):
    pass


def build_classifier_messages(snippet_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Classify this snippet:\n\n{snippet_text}",
        },
    ]


async def classify_snippet(
    snippet_text: str,
    client: httpx.AsyncClient | None = None,
) -> ClassifierResult:
    if not snippet_text.strip():
        raise ValueError("snippet_text must not be empty")

    settings = get_settings()
    if not settings.groq_api_key:
        raise ClassifierServiceError("GROQ_API_KEY is required for classification")

    should_close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)
    try:
        response = await http_client.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_classifier_model,
                "messages": build_classifier_messages(snippet_text),
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
    finally:
        if should_close_client:
            await http_client.aclose()

    content = response.json()["choices"][0]["message"]["content"]
    payload = json.loads(content)
    payload.setdefault("classifier_model", settings.groq_classifier_model)
    return ClassifierResult.model_validate(payload)
