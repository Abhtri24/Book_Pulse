"""Quality agent tools and agent loop (Phase 4)."""

import textstat

from app.schemas.quality import ReadabilityMetrics


def analyze_readability(text: str) -> ReadabilityMetrics:
    if not text.strip():
        raise ValueError("text must not be empty")

    return ReadabilityMetrics(
        flesch_reading_ease=round(textstat.flesch_reading_ease(text), 2),
        flesch_kincaid_grade=round(textstat.flesch_kincaid_grade(text), 2),
        avg_sentence_length=round(textstat.words_per_sentence(text), 2),
        word_count=textstat.lexicon_count(text),
        sentence_count=textstat.sentence_count(text),
    )
