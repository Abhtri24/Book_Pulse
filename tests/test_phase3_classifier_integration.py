"""Phase 3.6 – Comprehensive classifier tests.

These tests cover the gaps between individual unit tests and the full pipeline
to verify the Phase 3 classifier integration works end-to-end:

- Classifier is called *after* embedding succeeds (pipeline ordering).
- Classifier failure marks snippet as ``failed`` and does **not** create
  a SnippetMetadata row.
- Metadata produced by the classifier is forwarded to the Qdrant upsert.
- Classifier rejects empty snippet text before calling Groq.
- Classifier raises on HTTP error from Groq.
- Classifier handles non-object JSON (e.g. array or string at top-level).
"""

import json
import uuid

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.models.author import Author
from app.models.book import Book
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_metadata import SnippetMetadata
from app.schemas.classifier import ClassifierResult
from app.services.classifier_service import (
    ClassifierResponseError,
    ClassifierServiceError,
    classify_snippet,
)
from app.tasks import snippet_pipeline
from app.vector_store import VECTOR_SIZE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_snippet(db_session) -> Snippet:
    """Insert a minimal author + book + snippet and return the snippet."""
    author = Author(
        username=f"author-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Classifier Story", description="")
    snippet = Snippet(
        author=author,
        book=book,
        content="A vivid opening chapter with enough meaning to embed.",
        chapter_number=1,
    )
    db_session.add_all([author, book, snippet])
    await db_session.commit()
    await db_session.refresh(snippet)
    return snippet


def _valid_classifier_result(**overrides) -> ClassifierResult:
    """Build a valid ClassifierResult with sensible defaults."""
    defaults = dict(
        primary_genre="fantasy",
        sub_genres=["epic"],
        pov="third_person",
        pacing="moderate",
        tone="hopeful",
        hook_type="mystery",
        readability_score=72.0,
        classifier_model="test-classifier",
    )
    defaults.update(overrides)
    return ClassifierResult(**defaults)


# ---------------------------------------------------------------------------
# 1. Pipeline ordering: classifier runs only after embedding succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_calls_classifier_only_after_embedding(monkeypatch, db_session):
    """If embedding is called first, verify classifier is called second."""
    snippet = await _create_snippet(db_session)
    call_order: list[str] = []

    def fake_embed(text):
        call_order.append("embed")
        return [0.1] * VECTOR_SIZE

    async def fake_classify(text, client=None):
        call_order.append("classify")
        return _valid_classifier_result()

    monkeypatch.setattr(snippet_pipeline, "embed_text", fake_embed)
    monkeypatch.setattr("app.tasks.snippet_pipeline.classify_snippet", fake_classify)
    monkeypatch.setattr(snippet_pipeline, "ensure_snippet_collection", lambda: None)
    monkeypatch.setattr(
        snippet_pipeline,
        "upsert_snippet",
        lambda s, e, metadata=None: f"emb-{s.id}",
    )

    await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session)

    assert call_order == ["embed", "classify"], (
        f"Expected embed before classify, got {call_order}"
    )


# ---------------------------------------------------------------------------
# 2. Classifier failure → snippet marked failed, no metadata row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_failure_marks_snippet_failed_no_metadata(
    monkeypatch, db_session
):
    """When the classifier raises, the snippet should be ``failed`` and no
    SnippetMetadata row should be created."""
    snippet = await _create_snippet(db_session)

    monkeypatch.setattr(snippet_pipeline, "embed_text", lambda t: [0.1] * VECTOR_SIZE)

    async def fail_classify(text, client=None):
        raise ClassifierResponseError("classifier returned invalid structured output")

    monkeypatch.setattr("app.tasks.snippet_pipeline.classify_snippet", fail_classify)
    monkeypatch.setattr(snippet_pipeline, "ensure_snippet_collection", lambda: None)

    with pytest.raises(ClassifierResponseError):
        await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session)

    await db_session.refresh(snippet)
    assert snippet.processing_status == ProcessingStatus.failed

    meta_query = await db_session.execute(
        select(SnippetMetadata).where(SnippetMetadata.snippet_id == snippet.id)
    )
    assert meta_query.scalar_one_or_none() is None, (
        "No metadata row should be persisted when the classifier fails"
    )


# ---------------------------------------------------------------------------
# 3. Metadata forwarded to Qdrant upsert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_forwards_metadata_to_qdrant_upsert(monkeypatch, db_session):
    """The metadata object passed to ``upsert_snippet`` must contain the
    classifier's genre/style fields for vector payload enrichment."""
    snippet = await _create_snippet(db_session)
    captured_metadata = {}

    async def fake_classify(text, client=None):
        return _valid_classifier_result(
            primary_genre="sci-fi",
            tone="tense",
            pov="first_person",
        )

    def capture_upsert(s, e, metadata=None):
        captured_metadata["primary_genre"] = metadata.primary_genre
        captured_metadata["tone"] = metadata.tone
        captured_metadata["pov"] = metadata.pov
        return f"emb-{s.id}"

    monkeypatch.setattr(snippet_pipeline, "embed_text", lambda t: [0.1] * VECTOR_SIZE)
    monkeypatch.setattr("app.tasks.snippet_pipeline.classify_snippet", fake_classify)
    monkeypatch.setattr(snippet_pipeline, "ensure_snippet_collection", lambda: None)
    monkeypatch.setattr(snippet_pipeline, "upsert_snippet", capture_upsert)

    await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session)

    assert captured_metadata["primary_genre"] == "sci-fi"
    assert captured_metadata["tone"] == "tense"
    assert captured_metadata["pov"] == "first_person"


# ---------------------------------------------------------------------------
# 4. Classifier rejects empty snippet text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_snippet_rejects_empty_text():
    with pytest.raises(ValueError, match="must not be empty"):
        await classify_snippet("")


@pytest.mark.asyncio
async def test_classify_snippet_rejects_whitespace_only_text():
    with pytest.raises(ValueError, match="must not be empty"):
        await classify_snippet("   \n\t  ")


# ---------------------------------------------------------------------------
# 5. Classifier raises on HTTP error from Groq
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_snippet_raises_on_http_500(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await classify_snippet("A vivid scene.", client=client)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_classify_snippet_raises_on_http_429_rate_limit(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await classify_snippet("A vivid scene.", client=client)

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 6. Classifier handles non-object JSON (e.g. array at top-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_snippet_rejects_array_json(monkeypatch):
    """JSON arrays are syntactically valid JSON but are not the expected
    classifier output structure."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(["fantasy", "sci-fi"])
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ClassifierResponseError, match="invalid structured output"):
            await classify_snippet("A vivid scene.", client=client)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_classify_snippet_rejects_string_json(monkeypatch):
    """A bare JSON string should be rejected as non-object."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps("just a string")
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ClassifierResponseError, match="invalid structured output"):
            await classify_snippet("A vivid scene.", client=client)

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 7. Metadata row has correct one-to-one link after pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_creates_metadata_row_with_correct_snippet_link(
    monkeypatch, db_session
):
    """After a successful pipeline run the SnippetMetadata row must reference
    the same snippet_id and be reachable via ``snippet.metadata_record``."""
    snippet = await _create_snippet(db_session)

    async def fake_classify(text, client=None):
        return _valid_classifier_result(primary_genre="horror", tone="dark")

    monkeypatch.setattr(snippet_pipeline, "embed_text", lambda t: [0.1] * VECTOR_SIZE)
    monkeypatch.setattr("app.tasks.snippet_pipeline.classify_snippet", fake_classify)
    monkeypatch.setattr(snippet_pipeline, "ensure_snippet_collection", lambda: None)
    monkeypatch.setattr(
        snippet_pipeline,
        "upsert_snippet",
        lambda s, e, metadata=None: f"emb-{s.id}",
    )

    await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session)

    meta_query = await db_session.execute(
        select(SnippetMetadata).where(SnippetMetadata.snippet_id == snippet.id)
    )
    saved = meta_query.scalar_one()
    assert saved.primary_genre == "horror"
    assert saved.tone == "dark"
    assert saved.snippet_id == snippet.id


# ---------------------------------------------------------------------------
# 8. ClassifierResult schema edge-case: maximum readability boundary
# ---------------------------------------------------------------------------


def test_classifier_result_accepts_boundary_readability_scores():
    """Readability score at exact boundary values (0 and 100) should pass."""
    r0 = ClassifierResult(
        primary_genre="fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="slow",
        tone="neutral",
        hook_type="dialogue",
        readability_score=0,
        classifier_model="test",
    )
    assert r0.readability_score == 0.0

    r100 = ClassifierResult(
        primary_genre="fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="slow",
        tone="neutral",
        hook_type="dialogue",
        readability_score=100,
        classifier_model="test",
    )
    assert r100.readability_score == 100.0


def test_classifier_result_rejects_negative_readability():
    with pytest.raises(ValidationError):
        ClassifierResult(
            primary_genre="fantasy",
            sub_genres=[],
            pov="third_person",
            pacing="slow",
            tone="neutral",
            hook_type="dialogue",
            readability_score=-1,
            classifier_model="test",
        )
