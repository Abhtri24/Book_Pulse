from app.config import Settings


def test_pipeline_settings_have_defaults():
    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_collection_name == "snippets"


def test_pipeline_settings_can_be_overridden(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom-embedding-model")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "bookpulse-snippets")

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://redis:6379/1"
    assert settings.embedding_model_name == "custom-embedding-model"
    assert settings.qdrant_url == "http://qdrant:6333"
    assert settings.qdrant_collection_name == "bookpulse-snippets"
