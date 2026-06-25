"""Tests for app/services/ranking.py (Phase 5.5).

Pure-Python tests — no database or network access.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.ranking import (
    AUTHOR_REPEAT_PENALTY,
    DEFAULT_COLD_START_WEIGHTS,
    DEFAULT_PERSONALIZED_WEIGHTS,
    GENRE_REPEAT_PENALTY,
    RankingCandidate,
    RankingWeights,
    compute_diversity_penalty,
    compute_genre_match,
    compute_rank_score,
    compute_recency_score,
    compute_semantic_similarity,
    normalize_hook_score,
    normalize_quality_score,
    normalize_semantic_similarity,
    rank_candidates,
)

REF = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
AUTHOR_A = uuid.uuid4()
AUTHOR_B = uuid.uuid4()


def make_candidate(
    *,
    snippet_id: uuid.UUID | None = None,
    author_id: uuid.UUID = AUTHOR_A,
    primary_genre: str = "fantasy",
    quality_score: float = 80.0,
    hook_score: int = 70,
    created_at: datetime | None = None,
    semantic_similarity: float | None = None,
) -> RankingCandidate:
    return RankingCandidate(
        snippet_id=snippet_id or uuid.uuid4(),
        author_id=author_id,
        primary_genre=primary_genre,
        quality_score=quality_score,
        hook_score=hook_score,
        created_at=created_at or REF - timedelta(days=1),
        semantic_similarity=semantic_similarity,
    )


class TestNormalization:
    def test_normalize_quality_score_maps_to_unit_interval(self):
        assert normalize_quality_score(0.0) == 0.0
        assert normalize_quality_score(50.0) == 0.5
        assert normalize_quality_score(100.0) == 1.0
        assert normalize_quality_score(150.0) == 1.0
        assert normalize_quality_score(None) == 0.0

    def test_normalize_hook_score_maps_to_unit_interval(self):
        assert normalize_hook_score(0) == 0.0
        assert normalize_hook_score(50) == 0.5
        assert normalize_hook_score(100) == 1.0
        assert normalize_hook_score(None) == 0.0

    def test_normalize_semantic_similarity_maps_cosine_range(self):
        assert normalize_semantic_similarity(-1.0) == 0.0
        assert normalize_semantic_similarity(0.0) == 0.5
        assert normalize_semantic_similarity(1.0) == 1.0
        assert normalize_semantic_similarity(None) == 0.0


class TestComputeRecencyScore:
    def test_fresh_snippet_scores_one(self):
        assert compute_recency_score(REF, REF) == pytest.approx(1.0)

    def test_half_life_decay(self):
        half_life = 7.0
        created = REF - timedelta(days=half_life)
        assert compute_recency_score(created, REF, half_life_days=half_life) == pytest.approx(
            0.5
        )

    def test_older_snippets_score_lower(self):
        recent = compute_recency_score(REF - timedelta(days=1), REF)
        older = compute_recency_score(REF - timedelta(days=14), REF)
        assert recent > older

    def test_future_created_at_clamped_to_one(self):
        future = REF + timedelta(days=3)
        assert compute_recency_score(future, REF) == pytest.approx(1.0)

    def test_invalid_half_life_raises(self):
        with pytest.raises(ValueError, match="half_life_days"):
            compute_recency_score(REF, REF, half_life_days=0.0)


class TestComputeDiversityPenalty:
    def test_no_penalty_for_unseen_author_and_genre(self):
        candidate = make_candidate()
        assert compute_diversity_penalty(candidate, set(), set()) == 0.0

    def test_author_repeat_adds_penalty(self):
        candidate = make_candidate(author_id=AUTHOR_A)
        penalty = compute_diversity_penalty(candidate, {AUTHOR_A}, set())
        assert penalty == pytest.approx(AUTHOR_REPEAT_PENALTY)

    def test_genre_repeat_adds_penalty(self):
        candidate = make_candidate(primary_genre="sci-fi")
        penalty = compute_diversity_penalty(candidate, set(), {"sci-fi"})
        assert penalty == pytest.approx(GENRE_REPEAT_PENALTY)

    def test_both_repeats_cap_at_one(self):
        candidate = make_candidate(author_id=AUTHOR_A, primary_genre="romance")
        penalty = compute_diversity_penalty(
            candidate,
            {AUTHOR_A},
            {"romance"},
        )
        assert penalty == pytest.approx(1.0)


class TestComputeGenreMatch:
    def test_no_preferences_returns_zero(self):
        assert compute_genre_match("fantasy", None) == 0.0
        assert compute_genre_match("fantasy", []) == 0.0

    def test_matching_genre_returns_one(self):
        assert compute_genre_match("Fantasy", ["fantasy", "sci-fi"]) == 1.0

    def test_non_matching_genre_returns_zero(self):
        assert compute_genre_match("romance", ["fantasy"]) == 0.0


class TestComputeSemanticSimilarity:
    def test_identical_vectors_score_one(self):
        vector = [1.0, 0.0, 0.0]
        assert compute_semantic_similarity(vector, vector) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_half(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert compute_semantic_similarity(a, b) == pytest.approx(0.5)


class TestRankCandidates:
    def test_empty_input_returns_empty_list(self):
        assert rank_candidates([]) == []

    def test_higher_semantic_similarity_ranks_first(self):
        low = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            semantic_similarity=0.2,
            quality_score=50.0,
        )
        high = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            semantic_similarity=0.9,
            quality_score=50.0,
        )
        ranked = rank_candidates(
            [low, high],
            reference_time=REF,
            weights=DEFAULT_PERSONALIZED_WEIGHTS,
            apply_greedy_diversity=False,
        )
        assert ranked[0].snippet_id == high.snippet_id
        assert ranked[0].rank_score > ranked[1].rank_score

    def test_greedy_diversity_demotes_repeated_author(self):
        same_author_better_quality = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
            author_id=AUTHOR_A,
            quality_score=95.0,
            hook_score=95,
        )
        first = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
            author_id=AUTHOR_A,
            quality_score=89.0,
            hook_score=89,
        )
        different_author = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
            author_id=AUTHOR_B,
            primary_genre="sci-fi",
            quality_score=87.0,
            hook_score=87,
        )

        ranked = rank_candidates(
            [same_author_better_quality, first, different_author],
            reference_time=REF,
            weights=DEFAULT_COLD_START_WEIGHTS,
        )
        # Highest-scoring candidate is picked first regardless of input order.
        assert ranked[0].snippet_id == same_author_better_quality.snippet_id
        # The second slot should prefer a new author over repeating AUTHOR_A.
        assert ranked[1].author_id == AUTHOR_B

    def test_deterministic_tie_breaking_by_snippet_id(self):
        shared_score_weights = RankingWeights(
            semantic_similarity=0.0,
            quality_score=1.0,
            recency=0.0,
            diversity_penalty=0.0,
        )
        a = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000020"),
            quality_score=80.0,
            created_at=REF,
        )
        b = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
            quality_score=80.0,
            created_at=REF,
        )

        first_pass = rank_candidates(
            [b, a],
            reference_time=REF,
            weights=shared_score_weights,
            apply_greedy_diversity=False,
        )
        second_pass = rank_candidates(
            [a, b],
            reference_time=REF,
            weights=shared_score_weights,
            apply_greedy_diversity=False,
        )
        assert [item.snippet_id for item in first_pass] == [
            item.snippet_id for item in second_pass
        ]

    def test_cold_start_prefers_quality_recency_and_hook(self):
        stale_low_hook = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000030"),
            author_id=AUTHOR_A,
            quality_score=60.0,
            hook_score=40,
            created_at=REF - timedelta(days=30),
        )
        fresh_high_quality = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000031"),
            author_id=AUTHOR_B,
            quality_score=95.0,
            hook_score=90,
            created_at=REF - timedelta(hours=6),
        )

        ranked = rank_candidates(
            [stale_low_hook, fresh_high_quality],
            reference_time=REF,
            weights=DEFAULT_COLD_START_WEIGHTS,
            apply_greedy_diversity=False,
        )
        assert ranked[0].snippet_id == fresh_high_quality.snippet_id

    def test_genre_preference_boosts_matching_candidate(self):
        weights = DEFAULT_COLD_START_WEIGHTS
        preferred = ["fantasy"]
        fantasy = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000040"),
            author_id=AUTHOR_A,
            primary_genre="fantasy",
            quality_score=70.0,
            hook_score=70,
        )
        sci_fi = make_candidate(
            snippet_id=uuid.UUID("00000000-0000-0000-0000-000000000041"),
            author_id=AUTHOR_B,
            primary_genre="sci-fi",
            quality_score=70.0,
            hook_score=70,
            created_at=fantasy.created_at,
        )

        fantasy_score = compute_rank_score(
            fantasy,
            weights=weights,
            reference_time=REF,
            seen_author_ids=set(),
            seen_primary_genres=set(),
            preferred_genres=preferred,
        )
        sci_fi_score = compute_rank_score(
            sci_fi,
            weights=weights,
            reference_time=REF,
            seen_author_ids=set(),
            seen_primary_genres=set(),
            preferred_genres=preferred,
        )
        assert fantasy_score > sci_fi_score

    def test_rank_score_is_populated(self):
        candidate = make_candidate(semantic_similarity=0.8)
        ranked = rank_candidates(
            [candidate],
            reference_time=REF,
            apply_greedy_diversity=False,
        )
        assert ranked[0].rank_score == pytest.approx(
            compute_rank_score(
                candidate,
                weights=DEFAULT_PERSONALIZED_WEIGHTS,
                reference_time=REF,
                seen_author_ids=set(),
                seen_primary_genres=set(),
            )
        )

    def test_default_weights_sum_to_one(self):
        total = (
            DEFAULT_PERSONALIZED_WEIGHTS.semantic_similarity
            + DEFAULT_PERSONALIZED_WEIGHTS.quality_score
            + DEFAULT_PERSONALIZED_WEIGHTS.recency
            + DEFAULT_PERSONALIZED_WEIGHTS.diversity_penalty
        )
        assert total == pytest.approx(1.0)

    def test_cold_start_weights_sum_to_one(self):
        total = (
            DEFAULT_COLD_START_WEIGHTS.quality_score
            + DEFAULT_COLD_START_WEIGHTS.recency
            + DEFAULT_COLD_START_WEIGHTS.hook_score
            + DEFAULT_COLD_START_WEIGHTS.genre_match
            + DEFAULT_COLD_START_WEIGHTS.diversity_penalty
        )
        assert total == pytest.approx(1.0)
