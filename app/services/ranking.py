"""Deterministic ranking engine for feed personalisation.

Pure business logic — no database or Qdrant access.  Callers assemble
``RankingCandidate`` instances from their data source and pass them here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from uuid import UUID

from app.services.preference_engine import cosine_similarity

# ---------------------------------------------------------------------------
# Configurable weight constants — personalised feed
# ---------------------------------------------------------------------------

WEIGHT_SEMANTIC_SIMILARITY: float = 0.60
WEIGHT_QUALITY_SCORE: float = 0.20
WEIGHT_RECENCY: float = 0.15
WEIGHT_DIVERSITY_PENALTY: float = 0.05

# ---------------------------------------------------------------------------
# Configurable weight constants — cold-start feed
# ---------------------------------------------------------------------------

COLD_START_WEIGHT_QUALITY: float = 0.35
COLD_START_WEIGHT_RECENCY: float = 0.30
COLD_START_WEIGHT_HOOK: float = 0.25
COLD_START_WEIGHT_GENRE: float = 0.05

# ---------------------------------------------------------------------------
# Recency and diversity tuning
# ---------------------------------------------------------------------------

RECENCY_HALF_LIFE_DAYS: float = 7.0

AUTHOR_REPEAT_PENALTY: float = 0.5
GENRE_REPEAT_PENALTY: float = 0.5

QUALITY_SCORE_MAX: float = 100.0
HOOK_SCORE_MAX: float = 100.0

SECONDS_PER_DAY: float = 86_400.0


@dataclass(frozen=True)
class RankingWeights:
    """Linear combination weights for ``rank_candidates``."""

    semantic_similarity: float = WEIGHT_SEMANTIC_SIMILARITY
    quality_score: float = WEIGHT_QUALITY_SCORE
    recency: float = WEIGHT_RECENCY
    diversity_penalty: float = WEIGHT_DIVERSITY_PENALTY
    hook_score: float = 0.0
    genre_match: float = 0.0


DEFAULT_PERSONALIZED_WEIGHTS = RankingWeights()

DEFAULT_COLD_START_WEIGHTS = RankingWeights(
    semantic_similarity=0.0,
    quality_score=COLD_START_WEIGHT_QUALITY,
    recency=COLD_START_WEIGHT_RECENCY,
    diversity_penalty=WEIGHT_DIVERSITY_PENALTY,
    hook_score=COLD_START_WEIGHT_HOOK,
    genre_match=COLD_START_WEIGHT_GENRE,
)


@dataclass
class RankingCandidate:
    """A snippet eligible for feed ranking."""

    snippet_id: UUID
    author_id: UUID
    primary_genre: str
    quality_score: float
    hook_score: int
    created_at: datetime
    sub_genres: tuple[str, ...] = field(default_factory=tuple)
    semantic_similarity: float | None = None
    rank_score: float = field(default=0.0, compare=False)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def normalize_quality_score(quality_score: float | None) -> float:
    """Map a raw quality score into the closed interval [0, 1]."""
    if quality_score is None:
        return 0.0
    if not math.isfinite(quality_score):
        return 0.0
    return max(0.0, min(quality_score / QUALITY_SCORE_MAX, 1.0))


def normalize_hook_score(hook_score: int | None) -> float:
    """Map a raw hook score into the closed interval [0, 1]."""
    if hook_score is None:
        return 0.0
    return max(0.0, min(float(hook_score) / HOOK_SCORE_MAX, 1.0))


def normalize_semantic_similarity(similarity: float | None) -> float:
    """Map cosine similarity from [-1, 1] into [0, 1]."""
    if similarity is None:
        return 0.0
    if not math.isfinite(similarity):
        return 0.0
    return max(0.0, min((similarity + 1.0) / 2.0, 1.0))


def compute_semantic_similarity(
    preference_vector: list[float],
    snippet_vector: list[float],
) -> float:
    """Return a [0, 1] semantic similarity score between two embeddings."""
    raw = cosine_similarity(preference_vector, snippet_vector)
    return normalize_semantic_similarity(raw)


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------


def compute_recency_score(
    created_at: datetime,
    reference_time: datetime,
    *,
    half_life_days: float = RECENCY_HALF_LIFE_DAYS,
) -> float:
    """Return an exponential recency score in (0, 1].

    Uses half-life decay: a snippet created *half_life_days* ago scores 0.5.
    """
    if half_life_days <= 0.0:
        raise ValueError("half_life_days must be positive")

    ref = _ensure_utc(reference_time)
    created = _ensure_utc(created_at)
    age_seconds = max((ref - created).total_seconds(), 0.0)
    age_days = age_seconds / SECONDS_PER_DAY
    decay_constant = math.log(2.0) / half_life_days
    return math.exp(-decay_constant * age_days)


def compute_diversity_penalty(
    candidate: RankingCandidate,
    seen_author_ids: set[UUID],
    seen_primary_genres: set[str],
    *,
    author_penalty: float = AUTHOR_REPEAT_PENALTY,
    genre_penalty: float = GENRE_REPEAT_PENALTY,
) -> float:
    """Return a penalty in [0, 1] for repeated authors or primary genres."""
    penalty = 0.0
    if candidate.author_id in seen_author_ids:
        penalty += author_penalty
    if candidate.primary_genre in seen_primary_genres:
        penalty += genre_penalty
    return min(penalty, 1.0)


def compute_genre_match(
    primary_genre: str,
    preferred_genres: list[str] | None,
    sub_genres: tuple[str, ...] | list[str] | None = None,
) -> float:
    """Return 1.0 when a primary or subgenre matches a preferred genre."""
    if not preferred_genres:
        return 0.0

    preferred = {
        genre.strip().lower()
        for genre in preferred_genres
        if genre and genre.strip()
    }
    if not preferred:
        return 0.0

    candidate_genres = {primary_genre.strip().lower()}
    candidate_genres.update(
        genre.strip().lower()
        for genre in sub_genres or ()
        if genre and genre.strip()
    )
    return 1.0 if candidate_genres & preferred else 0.0


def compute_rank_score(
    candidate: RankingCandidate,
    *,
    weights: RankingWeights,
    reference_time: datetime,
    seen_author_ids: set[UUID],
    seen_primary_genres: set[str],
    preferred_genres: list[str] | None = None,
) -> float:
    """Compute the weighted ranking score for a single candidate."""
    quality = normalize_quality_score(candidate.quality_score)
    recency = compute_recency_score(candidate.created_at, reference_time)
    hook = normalize_hook_score(candidate.hook_score)
    semantic = normalize_semantic_similarity(candidate.semantic_similarity)
    genre = compute_genre_match(
        candidate.primary_genre,
        preferred_genres,
        candidate.sub_genres,
    )
    diversity = compute_diversity_penalty(
        candidate,
        seen_author_ids,
        seen_primary_genres,
    )

    return (
        weights.semantic_similarity * semantic
        + weights.quality_score * quality
        + weights.recency * recency
        + weights.hook_score * hook
        + weights.genre_match * genre
        - weights.diversity_penalty * diversity
    )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def rank_candidates(
    candidates: list[RankingCandidate],
    *,
    reference_time: datetime | None = None,
    weights: RankingWeights | None = None,
    preferred_genres: list[str] | None = None,
    seen_author_ids: set[UUID] | None = None,
    seen_primary_genres: set[str] | None = None,
    apply_greedy_diversity: bool = True,
) -> list[RankingCandidate]:
    """Return candidates ordered by descending rank score.

    When *apply_greedy_diversity* is ``True`` (default), each selection
    updates the seen-author and seen-genre sets so later picks are penalised
    for repeating earlier authors or primary genres within the same result.

    Tie-breaking is deterministic via ascending ``snippet_id`` string order.
    """
    if not candidates:
        return []

    ref_time = reference_time or datetime.now(timezone.utc)
    active_weights = weights or DEFAULT_PERSONALIZED_WEIGHTS
    seen_authors = set(seen_author_ids or ())
    seen_genres = set(seen_primary_genres or ())

    if not apply_greedy_diversity:
        ranked = [
            replace(
                candidate,
                rank_score=compute_rank_score(
                    candidate,
                    weights=active_weights,
                    reference_time=ref_time,
                    seen_author_ids=seen_authors,
                    seen_primary_genres=seen_genres,
                    preferred_genres=preferred_genres,
                ),
            )
            for candidate in candidates
        ]
        return sorted(ranked, key=_sort_key)

    remaining = list(candidates)
    ranked: list[RankingCandidate] = []

    while remaining:
        best_score = float("-inf")
        best_candidate: RankingCandidate | None = None

        for candidate in remaining:
            score = compute_rank_score(
                candidate,
                weights=active_weights,
                reference_time=ref_time,
                seen_author_ids=seen_authors,
                seen_primary_genres=seen_genres,
                preferred_genres=preferred_genres,
            )
            if best_candidate is None or (score, _tie_break_key(candidate)) > (
                best_score,
                _tie_break_key(best_candidate),
            ):
                best_score = score
                best_candidate = candidate

        assert best_candidate is not None
        ranked.append(replace(best_candidate, rank_score=best_score))
        seen_authors.add(best_candidate.author_id)
        seen_genres.add(best_candidate.primary_genre)
        remaining.remove(best_candidate)

    return ranked


def _sort_key(candidate: RankingCandidate) -> tuple[float, str]:
    return (-candidate.rank_score, str(candidate.snippet_id))


def _tie_break_key(candidate: RankingCandidate) -> str:
    return str(candidate.snippet_id)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
