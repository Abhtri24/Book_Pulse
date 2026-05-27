import math

import pytest

from app.config import get_settings
from app.services import embedding_service


class FakeEmbeddingModel:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def encode(self, text: str) -> list[float]:
        return [3, 4]


def test_embed_text_returns_normalized_vector(monkeypatch):
    monkeypatch.setattr(
        embedding_service,
        "_load_sentence_transformer_class",
        lambda: FakeEmbeddingModel,
    )
    embedding_service.get_embedding_model.cache_clear()

    embedding = embedding_service.embed_text("A vivid opening chapter.")

    assert embedding == [0.6, 0.8]
    assert math.isclose(math.sqrt(sum(value * value for value in embedding)), 1.0)
    embedding_service.get_embedding_model.cache_clear()


def test_embedding_model_uses_configured_model_name(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom-model")
    get_settings.cache_clear()
    embedding_service.get_embedding_model.cache_clear()
    monkeypatch.setattr(
        embedding_service,
        "_load_sentence_transformer_class",
        lambda: FakeEmbeddingModel,
    )

    model = embedding_service.get_embedding_model()

    assert model.model_name == "custom-model"
    get_settings.cache_clear()
    embedding_service.get_embedding_model.cache_clear()


def test_embed_text_rejects_empty_text():
    with pytest.raises(ValueError, match="text must not be empty"):
        embedding_service.embed_text("   ")
