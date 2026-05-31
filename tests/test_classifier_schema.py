import pytest
from pydantic import ValidationError

from app.schemas.classifier import ClassifierResult


def test_classifier_result_normalizes_text_fields():
    result = ClassifierResult(
        primary_genre=" Fantasy ",
        sub_genres=[" Epic ", "Adventure", "epic"],
        pov="third_person",
        pacing="fast",
        tone=" Hopeful ",
        hook_type="mystery",
        readability_score=82.5,
        classifier_model=" Test-Model ",
    )

    assert result.primary_genre == "fantasy"
    assert result.sub_genres == ["epic", "adventure"]
    assert result.tone == "hopeful"
    assert result.classifier_model == "test-model"


def test_classifier_result_rejects_invalid_enum_values():
    with pytest.raises(ValidationError):
        ClassifierResult(
            primary_genre="fantasy",
            sub_genres=[],
            pov="over_shoulder",
            pacing="fast",
            tone="hopeful",
            hook_type="mystery",
            readability_score=82.5,
            classifier_model="test-model",
        )


def test_classifier_result_rejects_out_of_range_readability():
    with pytest.raises(ValidationError):
        ClassifierResult(
            primary_genre="fantasy",
            sub_genres=[],
            pov="third_person",
            pacing="fast",
            tone="hopeful",
            hook_type="mystery",
            readability_score=120,
            classifier_model="test-model",
        )
