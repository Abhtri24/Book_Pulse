import uuid

import pytest

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import ProcessingStatus, Snippet
from app.tasks import snippet_pipeline
from app.vector_store import VECTOR_SIZE


async def create_snippet(db_session) -> Snippet:
    author = Author(
        username=f"author-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hash",
    )
    book = Book(
        author=author,
        title="Vector Story",
        description="",
    )
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


@pytest.mark.asyncio
async def test_process_snippet_sets_ready_and_embedding_id(monkeypatch, db_session):
    snippet = await create_snippet(db_session)
    embedding = [0.1] * VECTOR_SIZE
    calls = {"ensure_collection": 0, "upsert": 0}

    monkeypatch.setattr(snippet_pipeline, "embed_text", lambda text: embedding)
    monkeypatch.setattr(
        snippet_pipeline,
        "ensure_snippet_collection",
        lambda: calls.__setitem__("ensure_collection", calls["ensure_collection"] + 1),
    )

    def fake_upsert(processed_snippet, processed_embedding):
        calls["upsert"] += 1
        assert processed_snippet.id == snippet.id
        assert processed_snippet.processing_status == ProcessingStatus.processing
        assert processed_embedding == embedding
        return f"embedding-{processed_snippet.id}"

    monkeypatch.setattr(snippet_pipeline, "upsert_snippet", fake_upsert)

    result = await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session)

    await db_session.refresh(snippet)
    assert result == {
        "snippet_id": str(snippet.id),
        "embedding_id": f"embedding-{snippet.id}",
        "status": "ready",
    }
    assert snippet.processing_status == ProcessingStatus.ready
    assert snippet.embedding_id == f"embedding-{snippet.id}"
    assert calls == {"ensure_collection": 1, "upsert": 1}


@pytest.mark.asyncio
async def test_process_snippet_marks_failed_on_pipeline_error(monkeypatch, db_session):
    snippet = await create_snippet(db_session)

    def fail_embed(text):
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(snippet_pipeline, "embed_text", fail_embed)

    with pytest.raises(RuntimeError, match="embedding failed"):
        await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session)

    await db_session.refresh(snippet)
    assert snippet.processing_status == ProcessingStatus.failed
    assert snippet.embedding_id is None


@pytest.mark.asyncio
async def test_process_snippet_returns_not_found(db_session):
    missing_id = str(uuid.uuid4())

    result = await snippet_pipeline.process_snippet_async(missing_id, db=db_session)

    assert result == {"snippet_id": missing_id, "status": "not_found"}
