"""Quality agent tools and agent loop (Phase 4)."""

import json
import logging
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import textstat
from pydantic import ValidationError

from app.config import get_settings
from app.models.snippet import Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.schemas.quality import ReadabilityMetrics, SnippetFeedbackResult
from app.services.hook_service import check_hook_strength

logger = logging.getLogger(__name__)

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

class QualityAgentServiceError(RuntimeError):
    pass


class QualityAgentResponseError(QualityAgentServiceError):
    pass


AGENT_SYSTEM_PROMPT = """
You are an expert editor and writing coach agent. Your goal is to analyze the provided book snippet and generate structured feedback for the author.
You have access to tools that let you query the top performing snippets in the same genre, analyze the snippet's readability, and check its opening hook strength.

Use these tools to gather details and perform a thorough analysis. You should call:
1. `analyze_readability` to evaluate the reading ease and complexity.
2. `check_hook_strength` to evaluate the opening words of the snippet.
3. `query_top_snippets` with the appropriate genre to see what top-performing snippets in the same genre look like, using them as a reference.

After you have executed the tools and received the results, synthesize the findings to produce the final feedback.
Your final response MUST be a JSON object containing:
- "strengths": A list of strings describing specific writing strengths.
- "improvements": A list of suggested areas of improvement.
- "hook_score": An integer from 1 to 10 indicating the strength of the hook.
- "rewrite_suggestion": A string containing a specific rewrite suggestion for the opening line or hook.

Do not include any text outside of the JSON object.
""".strip()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_top_snippets",
            "description": "Fetch top-performing snippets in the same genre by quality score. Use these as quality references.",
            "parameters": {
                "type": "object",
                "properties": {
                    "genre": {"type": "string"},
                    "limit": {"type": "integer", "default": 3}
                },
                "required": ["genre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_readability",
            "description": "Compute readability metrics for the snippet text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_hook_strength",
            "description": "Analyze the opening 50 words for hook effectiveness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    }
]


def analyze_readability(text: str) -> ReadabilityMetrics:
    if not text.strip():
        raise ValueError("text must not be empty")

    return ReadabilityMetrics(
        flesch_reading_ease=round(textstat.flesch_reading_ease(text), 2),
        flesch_kincaid_grade=round(textstat.flesch_kincaid_grade(text), 2),
        avg_sentence_length=round(textstat.words_per_sentence(text), 2),
        word_count=textstat.lexicon_count(text),
        sentence_count=textstat.sentence_count(text),
    )


async def query_top_snippets(
    db: AsyncSession,
    genre: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Fetch top-performing snippets in the same genre by quality score from Postgres."""
    if not genre.strip():
        return []

    stmt = (
        select(
            Snippet.content,
            SnippetMetadata.primary_genre,
            SnippetMetadata.quality_score,
            SnippetMetadata.hook_score,
            SnippetMetadata.readability_score,
        )
        .join(Snippet, Snippet.id == SnippetMetadata.snippet_id)
        .where(func.lower(SnippetMetadata.primary_genre) == func.lower(genre.strip()))
        .order_by(SnippetMetadata.quality_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.mappings().all()
    return [
        {
            "content": row["content"],
            "primary_genre": row["primary_genre"],
            "quality_score": float(row["quality_score"]) if row["quality_score"] is not None else 0.0,
            "hook_score": int(row["hook_score"]) if row["hook_score"] is not None else 0,
            "readability_score": float(row["readability_score"]) if row["readability_score"] is not None else 0.0,
        }
        for row in rows
    ]


async def run_quality_agent(
    snippet: Snippet,
    genre: str,
    db: AsyncSession,
    client: httpx.AsyncClient | None = None,
) -> SnippetFeedbackResult:
    if not snippet.content.strip():
        raise ValueError("snippet content must not be empty")

    settings = get_settings()
    if not settings.groq_api_key:
        raise QualityAgentServiceError("GROQ_API_KEY is required for quality agent")

    should_close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)

    try:
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this snippet:\n\n{snippet.content}"}
        ]

        for _ in range(10):
            response = await http_client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": settings.groq_quality_model,
                    "messages": messages,
                    "temperature": 0,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                },
            )
            if response.status_code != 200:
                print("GROQ ERROR:")
                print(response.text)
            response.raise_for_status()
            resp_data = response.json()
            choice = resp_data["choices"][0]
            message = choice["message"]

            assistant_msg = {
                "role": "assistant",
                "content": message.get("content"),
            }
            if message.get("tool_calls"):
                assistant_msg["tool_calls"] = message["tool_calls"]
            messages.append(assistant_msg)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                break

            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_args_str = tool_call["function"]["arguments"]

                if isinstance(tool_args_str, str):
                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        tool_args = {}
                else:
                    tool_args = tool_args_str or {}

                try:
                    if tool_name == "query_top_snippets":
                        query_genre = tool_args.get("genre") or genre
                        limit = tool_args.get("limit", 3)
                        result_data = await query_top_snippets(db, query_genre, limit)
                    elif tool_name == "analyze_readability":
                        text = tool_args.get("text") or snippet.content
                        result_data = analyze_readability(text).model_dump()
                    elif tool_name == "check_hook_strength":
                        text = tool_args.get("text") or snippet.content
                        result_data = check_hook_strength(text).model_dump()
                    else:
                        result_data = {"error": f"Unknown tool: {tool_name}"}
                except Exception as exc:
                    logger.error(f"Error executing tool {tool_name}: {exc}")
                    result_data = {"error": str(exc)}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_name,
                    "content": json.dumps(result_data),
                })
        else:
            raise QualityAgentServiceError("Agent exceeded maximum tool call iterations")

        content = message.get("content") or ""
        try:
            return _parse_feedback_response(content)
        except (QualityAgentResponseError, ValidationError) as exc:
            logger.warning(f"First parse attempt failed: {exc}. Retrying...")
            messages.append({
                "role": "user",
                "content": "Your response was invalid. Please return only a valid JSON object matching the schema."
            })
            response = await http_client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": settings.groq_quality_model,
                    "messages": messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            resp_data = response.json()
            retry_content = resp_data["choices"][0]["message"].get("content") or ""
            return _parse_feedback_response(retry_content)

    finally:
        if should_close_client:
            await http_client.aclose()


def _parse_feedback_response(content: str) -> SnippetFeedbackResult:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise QualityAgentResponseError("Agent returned malformed JSON") from exc

    if not isinstance(payload, dict):
        raise QualityAgentResponseError("Agent returned non-object JSON")

    return SnippetFeedbackResult.model_validate(payload)
