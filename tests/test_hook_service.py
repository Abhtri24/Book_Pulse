import pytest

from app.services.hook_service import check_hook_strength

MYSTERY_OPENING = (
    "Something strange happened in the village when a mysterious figure suddenly disappeared. "
    "The impossible event left an unknown trace that nobody could explain. "
    "What happened to the missing witness in that dark corridor?"
)

DIALOGUE_OPENING = (
    '"Stop running," she whispered. The alley was narrow and the danger was closing in fast. '
    "He turned back once, breathless, and saw the shadow stretch across the wet stone walls. "
    "They had to escape before the guards found them in the maze of old city streets."
)

QUESTION_OPENING = (
    "What happened to the missing child? Nobody in the village knew the answer yet. "
    "Parents searched every street while fear spread through the crowded market square. "
    "The question hung over the town like smoke from a distant fire."
)

CONFLICT_OPENING = (
    "The war began with a brutal attack on the border fort. Soldiers fought through smoke "
    "and blood while civilians ran from the danger. Escape routes collapsed as kill squads "
    "pushed deeper into the valley."
)

LOW_QUALITY_OPENING = (
    "The day was nice. It was warm. People walked along the street and talked about ordinary "
    "things. Nothing unusual happened during the afternoon. The evening arrived quietly."
)


def test_mystery_opening_scores_above_seventy():
    metrics = check_hook_strength(MYSTERY_OPENING)

    assert metrics.hook_score > 70
    assert metrics.curiosity_gap is True
    assert metrics.hook_type in {"mystery", "question"}


def test_dialogue_opening_detected():
    metrics = check_hook_strength(DIALOGUE_OPENING)

    assert metrics.hook_type == "dialogue"
    assert metrics.dialogue_opening is True
    assert metrics.opening_style == "quoted_dialogue"


def test_question_opening_detected():
    metrics = check_hook_strength(QUESTION_OPENING)

    assert metrics.hook_type == "question"
    assert metrics.curiosity_gap is True
    assert metrics.hook_score >= 70


def test_conflict_opening_detected():
    metrics = check_hook_strength(CONFLICT_OPENING)

    assert metrics.hook_type == "conflict"
    assert metrics.conflict_present is True
    assert metrics.hook_score >= 65


def test_empty_text_rejected():
    with pytest.raises(ValueError, match="text must not be empty"):
        check_hook_strength("   ")


def test_low_quality_opening_stays_near_baseline():
    metrics = check_hook_strength(LOW_QUALITY_OPENING)

    assert metrics.hook_score == 50
    assert metrics.curiosity_gap is False
    assert metrics.conflict_present is False
    assert metrics.dialogue_opening is False
    assert any("baseline" in reason.lower() for reason in metrics.reasoning)
