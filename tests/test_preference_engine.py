"""Tests for app/services/preference_engine.py (Phase 5.3).

All tests are pure-Python and require no database or network access.
"""

from __future__ import annotations

import math

import pytest

from app.models.engagement_event import EngagementEventType
from app.services.preference_engine import (
    INTERACTION_WEIGHTS,
    cosine_similarity,
    normalize_vector,
    update_preference_vector,
    validate_vector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIM = 384


def unit_vector(index: int, dim: int = DIM) -> list[float]:
    """Return a unit basis vector with 1.0 at *index* and 0.0 elsewhere."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


def make_vector(value: float, dim: int = DIM) -> list[float]:
    """Return a uniform vector that will be normalised to the unit sphere."""
    return [value] * dim


def is_normalised(vector: list[float], tol: float = 1e-9) -> bool:
    magnitude = math.sqrt(sum(v * v for v in vector))
    return abs(magnitude - 1.0) < tol


# ---------------------------------------------------------------------------
# validate_vector
# ---------------------------------------------------------------------------


class TestValidateVector:
    def test_valid_vector_passes(self):
        validate_vector([0.1, 0.2, 0.3])

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_vector([])

    def test_non_list_raises(self):
        with pytest.raises((ValueError, AttributeError)):
            validate_vector(None)  # type: ignore[arg-type]

    def test_nan_raises(self):
        with pytest.raises(ValueError, match="not finite"):
            validate_vector([1.0, float("nan"), 0.5])

    def test_inf_raises(self):
        with pytest.raises(ValueError, match="not finite"):
            validate_vector([1.0, float("inf")])

    def test_zero_vector_raises(self):
        with pytest.raises(ValueError, match="zero vector"):
            validate_vector([0.0, 0.0, 0.0])

    def test_non_numeric_element_raises(self):
        with pytest.raises(ValueError, match="not a number"):
            validate_vector([1.0, "bad", 0.5])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# normalize_vector
# ---------------------------------------------------------------------------


class TestNormalizeVector:
    def test_unit_vector_unchanged(self):
        v = unit_vector(0, dim=3)
        result = normalize_vector(v)
        assert abs(result[0] - 1.0) < 1e-9
        assert is_normalised(result)

    def test_uniform_vector_normalised(self):
        v = [2.0, 2.0, 2.0]
        result = normalize_vector(v)
        assert is_normalised(result)

    def test_zero_vector_raises(self):
        with pytest.raises(ValueError, match="zero vector"):
            normalize_vector([0.0, 0.0])

    def test_large_dim_normalised(self):
        v = make_vector(3.14)
        result = normalize_vector(v)
        assert is_normalised(result)


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_unit_vectors(self):
        v = unit_vector(0, dim=3)
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = unit_vector(0, dim=3)
        b = unit_vector(1, dim=3)
        assert abs(cosine_similarity(a, b)) < 1e-9

    def test_opposite_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-9

    def test_dimension_mismatch_raises(self):
        with pytest.raises(ValueError, match="Dimension mismatch"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_zero_vector_raises(self):
        with pytest.raises(ValueError, match="zero vector"):
            cosine_similarity([0.0, 0.0], [1.0, 0.0])


# ---------------------------------------------------------------------------
# update_preference_vector — first interaction
# ---------------------------------------------------------------------------


class TestFirstInteraction:
    """An empty current_vector signals a brand-new reader."""

    def test_first_view_initialises_from_snippet(self):
        snippet = unit_vector(5)
        result = update_preference_vector(
            current_vector=[],
            snippet_vector=snippet,
            event_type=EngagementEventType.view,
            update_count=0,
        )
        assert len(result) == DIM
        assert is_normalised(result)
        # Direction should equal the snippet vector (already a unit vector)
        assert abs(cosine_similarity(result, snippet) - 1.0) < 1e-9

    def test_first_read_complete_initialises_from_snippet(self):
        snippet = make_vector(1.0)
        result = update_preference_vector(
            current_vector=[],
            snippet_vector=snippet,
            event_type=EngagementEventType.read_complete,
            update_count=0,
        )
        assert is_normalised(result)

    def test_first_skip_returns_snippet_as_seed(self):
        """Skip on empty history still seeds the vector rather than raising."""
        snippet = unit_vector(10)
        result = update_preference_vector(
            current_vector=[],
            snippet_vector=snippet,
            event_type=EngagementEventType.skip,
            update_count=0,
        )
        assert len(result) == DIM
        assert is_normalised(result)

    def test_first_tap_through_returns_normalised(self):
        snippet = make_vector(0.5)
        result = update_preference_vector(
            current_vector=[],
            snippet_vector=snippet,
            event_type=EngagementEventType.tap_through,
            update_count=0,
        )
        assert is_normalised(result)


# ---------------------------------------------------------------------------
# update_preference_vector — repeated interactions
# ---------------------------------------------------------------------------


class TestRepeatedInteraction:
    def test_repeated_read_complete_converges_toward_snippet(self):
        """After many read_complete events on the same snippet, the
        preference vector should be very close to that snippet's direction."""
        snippet = unit_vector(0)
        current = unit_vector(DIM - 1)  # start pointing away
        update_count = 1

        for _ in range(50):
            current = update_preference_vector(
                current_vector=current,
                snippet_vector=snippet,
                event_type=EngagementEventType.read_complete,
                update_count=update_count,
            )
            update_count += 1

        similarity = cosine_similarity(current, snippet)
        assert similarity > 0.9, f"Expected convergence, got similarity={similarity}"

    def test_view_moves_vector_less_than_read_complete(self):
        """A view interaction produces a smaller shift than read_complete."""
        snippet = unit_vector(1)
        start = unit_vector(0)

        result_view = update_preference_vector(
            current_vector=start,
            snippet_vector=snippet,
            event_type=EngagementEventType.view,
            update_count=1,
        )
        result_read = update_preference_vector(
            current_vector=start,
            snippet_vector=snippet,
            event_type=EngagementEventType.read_complete,
            update_count=1,
        )

        sim_view = cosine_similarity(result_view, snippet)
        sim_read = cosine_similarity(result_read, snippet)
        assert sim_read > sim_view

    def test_result_always_normalised_after_repeated_updates(self):
        snippet = make_vector(0.7)
        current = make_vector(0.3)
        # Normalise the seed manually to satisfy validate_vector
        current = normalize_vector(current)

        for event in [
            EngagementEventType.view,
            EngagementEventType.tap_through,
            EngagementEventType.read_complete,
            EngagementEventType.view,
        ]:
            current = update_preference_vector(
                current_vector=current,
                snippet_vector=snippet,
                event_type=event,
                update_count=1,
            )
            assert is_normalised(current), f"Not normalised after {event}"


# ---------------------------------------------------------------------------
# update_preference_vector — read_complete influence
# ---------------------------------------------------------------------------


class TestReadCompleteInfluence:
    def test_read_complete_has_highest_weight(self):
        assert (
            INTERACTION_WEIGHTS[EngagementEventType.read_complete]
            >= INTERACTION_WEIGHTS[EngagementEventType.tap_through]
            >= INTERACTION_WEIGHTS[EngagementEventType.view]
        )

    def test_read_complete_shifts_vector_toward_snippet(self):
        snippet = unit_vector(2)
        current = unit_vector(3)  # orthogonal to snippet

        result = update_preference_vector(
            current_vector=current,
            snippet_vector=snippet,
            event_type=EngagementEventType.read_complete,
            update_count=1,
        )
        # The result should have a positive component in the snippet direction
        similarity = cosine_similarity(result, snippet)
        assert similarity > 0.0


# ---------------------------------------------------------------------------
# update_preference_vector — skip influence
# ---------------------------------------------------------------------------


class TestSkipInfluence:
    def test_skip_moves_vector_away_from_snippet(self):
        """After a skip, the preference should be *less* similar to the
        skipped snippet than before."""
        snippet = unit_vector(0)
        current = normalize_vector([0.8] + [0.2] * (DIM - 1))

        similarity_before = cosine_similarity(current, snippet)

        result = update_preference_vector(
            current_vector=current,
            snippet_vector=snippet,
            event_type=EngagementEventType.skip,
            update_count=1,
        )

        similarity_after = cosine_similarity(result, snippet)
        assert similarity_after < similarity_before

    def test_skip_does_not_produce_zero_vector(self):
        """Even pushing away from a very similar snippet must yield a
        valid, non-zero normalised vector."""
        snippet = unit_vector(0)
        current = unit_vector(0)  # current == snippet

        result = update_preference_vector(
            current_vector=current,
            snippet_vector=snippet,
            event_type=EngagementEventType.skip,
            update_count=1,
        )
        assert is_normalised(result)

    def test_skip_weight_is_negative(self):
        assert INTERACTION_WEIGHTS[EngagementEventType.skip] < 0

    def test_skip_result_is_normalised(self):
        snippet = normalize_vector(make_vector(1.0))
        current = normalize_vector(make_vector(0.5))

        result = update_preference_vector(
            current_vector=current,
            snippet_vector=snippet,
            event_type=EngagementEventType.skip,
            update_count=5,
        )
        assert is_normalised(result)


# ---------------------------------------------------------------------------
# Normalization invariant
# ---------------------------------------------------------------------------


class TestNormalization:
    @pytest.mark.parametrize(
        "event_type",
        [
            EngagementEventType.view,
            EngagementEventType.tap_through,
            EngagementEventType.read_complete,
            EngagementEventType.skip,
        ],
    )
    def test_all_events_return_normalised_vector(self, event_type):
        snippet = normalize_vector(make_vector(1.0))
        current = normalize_vector(make_vector(0.5))

        result = update_preference_vector(
            current_vector=current,
            snippet_vector=snippet,
            event_type=event_type,
            update_count=3,
        )
        assert is_normalised(result), (
            f"Vector not normalised after {event_type}: "
            f"magnitude={math.sqrt(sum(v*v for v in result))}"
        )

    def test_first_interaction_returns_normalised(self):
        snippet = make_vector(7.0)
        result = update_preference_vector(
            current_vector=[],
            snippet_vector=snippet,
            event_type=EngagementEventType.read_complete,
            update_count=0,
        )
        assert is_normalised(result)


# ---------------------------------------------------------------------------
# Dimension mismatch
# ---------------------------------------------------------------------------


class TestDimensionMismatch:
    def test_snippet_wrong_dim_raises(self):
        current = unit_vector(0, dim=DIM)
        snippet_wrong = [1.0] * 128  # wrong dimension

        with pytest.raises(ValueError, match="[Dd]imension"):
            update_preference_vector(
                current_vector=current,
                snippet_vector=snippet_wrong,
                event_type=EngagementEventType.view,
                update_count=1,
            )

    def test_current_and_snippet_different_dims_raises(self):
        current = [1.0] * 10
        snippet = [1.0] * 20

        with pytest.raises(ValueError, match="[Dd]imension"):
            update_preference_vector(
                current_vector=current,
                snippet_vector=snippet,
                event_type=EngagementEventType.read_complete,
                update_count=1,
            )


# ---------------------------------------------------------------------------
# Invalid vector handling
# ---------------------------------------------------------------------------


class TestInvalidVectors:
    def test_nan_in_snippet_raises(self):
        snippet = [1.0] * DIM
        snippet[100] = float("nan")

        with pytest.raises(ValueError, match="not finite"):
            update_preference_vector(
                current_vector=[],
                snippet_vector=snippet,
                event_type=EngagementEventType.view,
                update_count=0,
            )

    def test_inf_in_snippet_raises(self):
        snippet = [1.0] * DIM
        snippet[0] = float("inf")

        with pytest.raises(ValueError, match="not finite"):
            update_preference_vector(
                current_vector=[],
                snippet_vector=snippet,
                event_type=EngagementEventType.view,
                update_count=0,
            )

    def test_empty_snippet_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            update_preference_vector(
                current_vector=[],
                snippet_vector=[],
                event_type=EngagementEventType.view,
                update_count=0,
            )


# ---------------------------------------------------------------------------
# Zero vector handling
# ---------------------------------------------------------------------------


class TestZeroVectorHandling:
    def test_zero_snippet_vector_raises(self):
        with pytest.raises(ValueError, match="zero vector"):
            update_preference_vector(
                current_vector=[],
                snippet_vector=[0.0] * DIM,
                event_type=EngagementEventType.view,
                update_count=0,
            )

    def test_zero_current_vector_raises_on_subsequent_update(self):
        """A zero current_vector on a non-first update must be rejected."""
        with pytest.raises(ValueError, match="zero vector"):
            update_preference_vector(
                current_vector=[0.0] * DIM,
                snippet_vector=unit_vector(0),
                event_type=EngagementEventType.view,
                update_count=1,
            )

    def test_skip_current_equals_snippet_still_returns_valid(self):
        """Skipping a snippet that exactly equals the current preference
        vector is the worst-case for vector explosion — must still produce
        a valid unit vector."""
        v = unit_vector(7)
        result = update_preference_vector(
            current_vector=v,
            snippet_vector=v,
            event_type=EngagementEventType.skip,
            update_count=1,
        )
        assert len(result) == DIM
        assert is_normalised(result)
