import pytest
from uuid import UUID

from app.models.snippet import ProcessingStatus, Snippet
from app.tasks import snippet_pipeline
from app.vector_store import VECTOR_SIZE
from tests.test_books import make_snippet, register_and_login_author


@pytest.mark.asyncio
async def test_phase2_mocked_embedding_pipeline_smoke(monkeypatch, client, db_session):
    scheduled_snippet_ids = []

    class FakeProcessSnippetTask:
        @staticmethod
        def delay(snippet_id: str) -> None:
            scheduled_snippet_ids.append(snippet_id)

    monkeypatch.setattr(snippet_pipeline, "process_snippet", FakeProcessSnippetTask)

    token = await register_and_login_author(client)
    headers = {"Authorization": f"Bearer {token}"}
    book_response = await client.post(
        "/books",
        json={"title": "Smoke Test Story", "description": ""},
        headers=headers,
    )
    book_id = book_response.json()["id"]

    upload_response = await client.post(
        f"/books/{book_id}/snippets",
        json={"content": make_snippet(200), "chapter_number": 1},
        headers=headers,
    )

    assert upload_response.status_code == 201
    upload_body = upload_response.json()
    assert upload_body["processing_status"] == "pending"
    assert scheduled_snippet_ids == [upload_body["id"]]

    monkeypatch.setattr(snippet_pipeline, "embed_text", lambda text: [0.1] * VECTOR_SIZE)
    monkeypatch.setattr(snippet_pipeline, "ensure_snippet_collection", lambda: None)
    monkeypatch.setattr(
        snippet_pipeline,
        "upsert_snippet",
        lambda snippet, embedding: f"embedding-{snippet.id}",
    )

    result = await snippet_pipeline.process_snippet_async(
        scheduled_snippet_ids[0],
        db=db_session,
    )
    snippet = await db_session.get(Snippet, UUID(upload_body["id"]))

    assert result["status"] == "ready"
    assert snippet.processing_status == ProcessingStatus.ready
    assert snippet.embedding_id == f"embedding-{snippet.id}"
