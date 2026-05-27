import math
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class EmbeddingModel(Protocol):
    def encode(self, text: str) -> object:
        pass


def _load_sentence_transformer_class():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model(model_name: str | None = None) -> EmbeddingModel:
    settings = get_settings()
    resolved_model_name = model_name or settings.embedding_model_name
    sentence_transformer = _load_sentence_transformer_class()
    return sentence_transformer(resolved_model_name)


def embed_text(text: str) -> list[float]:
    if not text.strip():
        raise ValueError("text must not be empty")

    model = get_embedding_model()
    raw_embedding = model.encode(text)
    embedding = _coerce_embedding(raw_embedding)
    return _normalize(embedding)


def _coerce_embedding(raw_embedding: object) -> list[float]:
    if hasattr(raw_embedding, "tolist"):
        raw_embedding = raw_embedding.tolist()

    if (
        isinstance(raw_embedding, list)
        and raw_embedding
        and isinstance(raw_embedding[0], list)
    ):
        raw_embedding = raw_embedding[0]

    if not isinstance(raw_embedding, list):
        raise TypeError("embedding model returned an unsupported embedding type")

    return [float(value) for value in raw_embedding]


def _normalize(embedding: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in embedding))
    if magnitude == 0:
        raise ValueError("embedding vector must not be all zeros")
    return [value / magnitude for value in embedding]
