import uuid

import pytest
from sqlalchemy import select

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_feedback import SnippetFeedback
from app.models.snippet_metadata import SnippetMetadata
from app.schemas.quality import SnippetFeedbackResult
from app.tasks import quality_task, snippet_pipeline
from app.vector_store import VECTOR_SIZE


async def create_ready_snippet(db_session) -> Snippet:
    author = Author(username=f"qa-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    book = Book(author=author, title="Feedback Book")
    snippet = Snippet(
        author=author,
        book=book,
        content="A strong opening with enough texture for feedback.",
        chapter_number=1,
        processing_status=ProcessingStatus.ready,
    )
    metadata = SnippetMetadata(
        snippet=snippet,
        primary_genre="Fantasy",
        sub_genres=[],
        pov="third_person",
        pacing="fast",
        tone="tense",
        hook_type="mystery",
        readability_score=75.0,
        quality_score=80.0,
        classifier_model="test",
        hook_score=85,
    )
    db_session.add_all([author, book, snippet, metadata])
    await db_session.commit()
    await db_session.refresh(snippet)
    return snippet


@pytest.mark.asyncio
async def test_feedback_saved_successfully(monkeypatch, db_session):
    snippet = await create_ready_snippet(db_session)

    async def fake_agent(snippet_arg, genre, db):
        return SnippetFeedbackResult(
            strengths=["Clear mood"],
            improvements=["Sharpen the first line"],
            hook_score=8,
            rewrite_suggestion="Open with the choice.",
        )

    monkeypatch.setattr(quality_task, "run_quality_agent", fake_agent)

    result = await quality_task.process_feedback_async(str(snippet.id), db=db_session)

    assert result == {"snippet_id": str(snippet.id), "feedback_saved": True}
    saved = (await db_session.execute(select(SnippetFeedback))).scalar_one()
    assert saved.snippet_id == snippet.id
    assert saved.strengths == ["Clear mood"]


@pytest.mark.asyncio
async def test_quality_agent_exception_handled(monkeypatch, db_session):
    snippet = await create_ready_snippet(db_session)
    snippet_id = str(snippet.id)

    async def fail_agent(snippet_arg, genre, db):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr(quality_task, "run_quality_agent", fail_agent)

    result = await quality_task.process_feedback_async(snippet_id, db=db_session)

    assert result == {"snippet_id": snippet_id, "feedback_saved": False, "status": "failed"}
    saved = (await db_session.execute(select(SnippetFeedback))).scalar_one_or_none()
    assert saved is None


@pytest.mark.asyncio
async def test_snippet_remains_ready_on_feedback_failure(monkeypatch, db_session):
    snippet = await create_ready_snippet(db_session)

    async def fail_agent(snippet_arg, genre, db):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr(quality_task, "run_quality_agent", fail_agent)

    await quality_task.process_feedback_async(str(snippet.id), db=db_session)
    await db_session.refresh(snippet)

    assert snippet.processing_status == ProcessingStatus.ready


@pytest.mark.asyncio
async def test_duplicate_feedback_prevented(monkeypatch, db_session):
    snippet = await create_ready_snippet(db_session)

    async def fake_agent(snippet_arg, genre, db):
        return SnippetFeedbackResult(
            strengths=["Clear mood"],
            improvements=[],
            hook_score=7,
            rewrite_suggestion="Keep the image.",
        )

    monkeypatch.setattr(quality_task, "run_quality_agent", fake_agent)

    first = await quality_task.process_feedback_async(str(snippet.id), db=db_session)
    second = await quality_task.process_feedback_async(str(snippet.id), db=db_session)

    rows = (await db_session.execute(select(SnippetFeedback))).scalars().all()
    assert first["feedback_saved"] is True
    assert second == {"snippet_id": str(snippet.id), "feedback_saved": False, "status": "already_exists"}
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_full_flow_pipeline_ready_then_feedback_saved(monkeypatch, db_session):
    author = Author(username="flow-author", email="flow@example.com", password_hash="hash")
    book = Book(author=author, title="Flow Book")
    snippet = Snippet(
        author=author,
        book=book,
        content="A vivid opening chapter with enough meaning to embed.",
        chapter_number=1,
    )
    db_session.add_all([author, book, snippet])
    await db_session.commit()
    await db_session.refresh(snippet)

    from app.schemas.classifier import ClassifierResult

    async def fake_classifier(text, client=None):
        return ClassifierResult(
            primary_genre="Fantasy",
            sub_genres=[],
            pov="third_person",
            pacing="fast",
            tone="tense",
            hook_type="mystery",
            readability_score=70.0,
            classifier_model="test",
        )

    async def fake_agent(snippet_arg, genre, db):
        return SnippetFeedbackResult(
            strengths=["Atmosphere"],
            improvements=["More specificity"],
            hook_score=8,
            rewrite_suggestion="Start closer to the decision.",
        )

    monkeypatch.setattr(snippet_pipeline, "embed_text", lambda text: [0.1] * VECTOR_SIZE)
    monkeypatch.setattr(snippet_pipeline, "classify_snippet", fake_classifier)
    monkeypatch.setattr(snippet_pipeline, "ensure_snippet_collection", lambda: None)
    monkeypatch.setattr(snippet_pipeline, "upsert_snippet", lambda s, e, metadata=None: f"embedding-{s.id}")
    monkeypatch.setattr(quality_task, "run_quality_agent", fake_agent)

    await snippet_pipeline.process_snippet_async(str(snippet.id), db=db_session, enqueue_feedback=False)
    await db_session.refresh(snippet)
    feedback_result = await quality_task.process_feedback_async(str(snippet.id), db=db_session)

    assert snippet.processing_status == ProcessingStatus.ready
    assert feedback_result["feedback_saved"] is True
    saved = (await db_session.execute(select(SnippetFeedback))).scalar_one()
    assert saved.snippet_id == snippet.id
