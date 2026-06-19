import pytest

from app.services.quality_agent import analyze_readability


SAMPLE_TEXT = (
    "The rain fell hard on the city streets. "
    "She ran without looking back. "
    "Every shadow seemed to follow her."
)


def test_analyze_readability_returns_structured_metrics():
    metrics = analyze_readability(SAMPLE_TEXT)

    assert metrics.flesch_reading_ease == 84.64
    assert metrics.flesch_kincaid_grade == 3.03
    assert metrics.avg_sentence_length == 6.33
    assert metrics.word_count == 19
    assert metrics.sentence_count == 3


def test_analyze_readability_serializes_to_dict():
    metrics = analyze_readability(SAMPLE_TEXT)
    payload = metrics.model_dump()

    assert set(payload) == {
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "avg_sentence_length",
        "word_count",
        "sentence_count",
    }
    assert all(isinstance(payload[key], (int, float)) for key in payload)


def test_analyze_readability_rejects_empty_text():
    with pytest.raises(ValueError, match="text must not be empty"):
        analyze_readability("   ")
