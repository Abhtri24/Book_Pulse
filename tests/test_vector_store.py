import uuid
from datetime import datetime, timezone

import pytest
from qdrant_client.http import models

from app.config import get_settings
from app.models.snippet import ProcessingStatus, Snippet
from app import vector_store


class FakeQdrantClient:
    def __init__(self, collection_exists: bool = False):
        self._collection_exists = collection_exists
        self.created_collections = []
        self.upserts = []
        self.searches = []

    def collection_exists(self, collection_name: str) -> bool:
        return self._collection_exists

    def create_collection(self, collection_name: str, vectors_config) -> None:
        self.created_collections.append((collection_name, vectors_config))

    def upsert(self, collection_name: str, points: list[models.PointStruct]) -> None:
        self.upserts.append((collection_name, points))

    def search(self, collection_name: str, query_vector: list[float], limit: int):
        self.searches.append((collection_name, query_vector, limit))
        return ["match"]


def make_snippet() -> Snippet:
    return Snippet(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        content="sample",
        chapter_number=3,
        processing_status=ProcessingStatus.ready,
        created_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
    )


def test_ensure_snippet_collection_creates_cosine_collection(monkeypatch):
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "test-snippets")
    get_settings.cache_clear()
    client = FakeQdrantClient(collection_exists=False)

    vector_store.ensure_snippet_collection(client=client)

    collection_name, vector_config = client.created_collections[0]
    assert collection_name == "test-snippets"
    assert vector_config.size == 384
    assert vector_config.distance == models.Distance.COSINE
    get_settings.cache_clear()


def test_ensure_snippet_collection_skips_existing_collection():
    client = FakeQdrantClient(collection_exists=True)

    vector_store.ensure_snippet_collection(client=client)

    assert client.created_collections == []


def test_upsert_snippet_stores_vector_and_payload(monkeypatch):
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "test-snippets")
    get_settings.cache_clear()
    client = FakeQdrantClient()
    snippet = make_snippet()
    embedding = [0.0] * vector_store.VECTOR_SIZE

    embedding_id = vector_store.upsert_snippet(snippet, embedding, client=client)

    collection_name, points = client.upserts[0]
    point = points[0]
    assert collection_name == "test-snippets"
    assert embedding_id == str(snippet.id)
    assert point.id == str(snippet.id)
    assert point.vector == embedding
    assert point.payload == {
        "snippet_id": str(snippet.id),
        "book_id": str(snippet.book_id),
        "author_id": str(snippet.author_id),
        "chapter_number": 3,
        "processing_status": "ready",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    get_settings.cache_clear()


def test_upsert_snippet_rejects_wrong_embedding_size():
    with pytest.raises(ValueError, match="384 dimensions"):
        vector_store.upsert_snippet(make_snippet(), [0.1], client=FakeQdrantClient())


def test_search_similar_delegates_to_qdrant(monkeypatch):
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "test-snippets")
    get_settings.cache_clear()
    client = FakeQdrantClient()
    query_vector = [0.1] * vector_store.VECTOR_SIZE

    result = vector_store.search_similar(query_vector, limit=5, client=client)

    assert result == ["match"]
    assert client.searches == [("test-snippets", query_vector, 5)]
    get_settings.cache_clear()
