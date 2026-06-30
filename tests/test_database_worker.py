import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import Base
from app.database_worker import run_worker_async, shutdown_worker_database, worker_session
from app.models.author import Author
from app.models.book import Book
from app.models.snippet import ProcessingStatus, Snippet
from app.models.snippet_feedback import SnippetFeedback
from app.models.snippet_metadata import SnippetMetadata
from app.schemas.quality import SnippetFeedbackResult
from app.tasks import quality_task, snippet_pipeline
from app.vector_store import VECTOR_SIZE


@pytest.fixture
def worker_database_url(monkeypatch, tmp_path):
    shutdown_worker_database()
    db_path = tmp_path / "worker.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    yield
    shutdown_worker_database()
    get_settings.cache_clear()


def setup_worker_schema() -> None:
    async def setup() -> None:
        from app.database_worker import celery_async_db

        await celery_async_db._ensure_session_factory()
        engine = celery_async_db._engine
        assert engine is not None
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    run_worker_async(setup)


def test_worker_async_runtime_reuses_open_event_loop(worker_database_url):
    async def current_loop_id() -> int:
        return id(asyncio.get_running_loop())

    first_loop_id = run_worker_async(current_loop_id)
    second_loop_id = run_worker_async(current_loop_id)

    assert first_loop_id == second_loop_id


def test_worker_session_supports_multiple_sequential_queries(worker_database_url):
    setup_worker_schema()

    async def create_and_count_authors() -> tuple[int, int]:
        async with worker_session() as session:
            session.add(Author(username="worker-a", email="worker-a@example.com", password_hash="hash"))
            await session.commit()

        async with worker_session() as session:
            first_count = len((await session.execute(select(Author))).scalars().all())
            session.add(Author(username="worker-b", email="worker-b@example.com", password_hash="hash"))
            await session.commit()

        async with worker_session() as session:
            second_count = len((await session.execute(select(Author))).scalars().all())

        return first_count, second_count

    assert run_worker_async(create_and_count_authors) == (1, 2)


def test_sequential_celery_tasks_use_worker_sessions(monkeypatch, worker_database_url):
    setup_worker_schema()

    async def seed_snippet() -> str:
        async with worker_session() as session:
            author = Author(username="seq-author", email="seq@example.com", password_hash="hash")
            book = Book(
                author=author,
                title="Sequential Book",
                external_url="https://example.com/sequential",
            )
            snippet = Snippet(
                author=author,
                book=book,
                content="A vivid opening chapter with enough meaning to embed.",
                chapter_number=1,
            )
            session.add_all([author, book, snippet])
            await session.commit()
            await session.refresh(snippet)
            return str(snippet.id)

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

    snippet_id = run_worker_async(seed_snippet)

    snippet_result = snippet_pipeline.process_snippet.run(
        snippet_id,
        enqueue_feedback=False,
    )
    feedback_result = quality_task.process_feedback.run(snippet_id)

    async def inspect() -> tuple[ProcessingStatus, int]:
        async with worker_session() as session:
            snippet = await session.get(Snippet, uuid.UUID(snippet_id))
            feedback_count = len((await session.execute(select(SnippetFeedback))).scalars().all())
            assert snippet is not None
            return snippet.processing_status, feedback_count

    assert snippet_result["status"] == "ready"
    assert feedback_result["feedback_saved"] is True
    assert run_worker_async(inspect) == (ProcessingStatus.ready, 1)


def test_repeated_feedback_task_execution_is_idempotent(monkeypatch, worker_database_url):
    setup_worker_schema()

    async def seed_ready_snippet() -> str:
        async with worker_session() as session:
            author = Author(username="repeat-author", email="repeat@example.com", password_hash="hash")
            book = Book(
                author=author,
                title="Repeat Book",
                external_url="https://example.com/repeat",
            )
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
            session.add_all([author, book, snippet, metadata])
            await session.commit()
            await session.refresh(snippet)
            return str(snippet.id)

    async def fake_agent(snippet_arg, genre, db):
        return SnippetFeedbackResult(
            strengths=["Clear mood"],
            improvements=[],
            hook_score=7,
            rewrite_suggestion="Keep the image.",
        )

    monkeypatch.setattr(quality_task, "run_quality_agent", fake_agent)
    snippet_id = run_worker_async(seed_ready_snippet)

    first = quality_task.process_feedback.run(snippet_id)
    second = quality_task.process_feedback.run(snippet_id)

    assert first["feedback_saved"] is True
    assert second["status"] == "already_exists"
