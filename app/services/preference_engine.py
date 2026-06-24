"""Preference vector engine for reader personalisation.

Implements a weighted moving-average update strategy: each interaction
blends the reader's current preference vector toward (or away from) the
snippet vector with a weight that reflects how strong the signal is.

No database access occurs here — callers are responsible for persisting
the returned vector and incrementing the update counter.
"""

from __future__ import annotations

import math

from app.models.engagement_event import EngagementEventType

# ---------------------------------------------------------------------------
# Interaction weights
# ---------------------------------------------------------------------------

INTERACTION_WEIGHTS: dict[EngagementEventType, float] = {
    EngagementEventType.view: 0.2,
    EngagementEventType.tap_through: 0.5,
    EngagementEventType.read_complete: 1.0,
    EngagementEventType.skip: -0.3,
}

# Clip magnitude for the skip repulsion step so the vector can never
# explode toward negative infinity.
_SKIP_CLIP_MIN: float = -1.0

# ---------------------------------------------------------------------------
# Vector utilities
# ---------------------------------------------------------------------------


def validate_vector(vector: list[float], *, label: str = "vector") -> None:
    """Raise ``ValueError`` for malformed or unusable vectors.

    Checks:
    * Must be a non-empty list.
    * Every element must be a finite float (no NaN / inf).
    * The magnitude must be non-zero (cannot update from a zero vector).
    """
    if not isinstance(vector, list) or len(vector) == 0:
        raise ValueError(f"{label} must be a non-empty list of floats")

    for i, v in enumerate(vector):
        if not isinstance(v, (int, float)):
            raise ValueError(
                f"{label}[{i}] is not a number: {v!r}"
            )
        if not math.isfinite(v):
            raise ValueError(
                f"{label}[{i}] is not finite: {v!r}"
            )

    if all(v == 0.0 for v in vector):
        raise ValueError(f"{label} is a zero vector and cannot be used for updates")


def normalize_vector(vector: list[float]) -> list[float]:
    """Return the L2-normalised form of *vector*.

    The caller must ensure *vector* is non-zero before calling this.
    """
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude == 0.0:
        raise ValueError("Cannot normalise a zero vector")
    inv = 1.0 / magnitude
    return [v * inv for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity in [-1, 1] between vectors *a* and *b*.

    Both vectors are assumed to already be L2-normalised; the function still
    works with un-normalised vectors but will be slower due to the extra
    magnitude divisions.
    """
    if len(a) != len(b):
        raise ValueError(
            f"Dimension mismatch: len(a)={len(a)}, len(b)={len(b)}"
        )
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        raise ValueError("Cannot compute cosine similarity for a zero vector")
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def update_preference_vector(
    current_vector: list[float],
    snippet_vector: list[float],
    event_type: EngagementEventType,
    update_count: int,
) -> list[float]:
    """Return an updated, normalised preference vector.

    Parameters
    ----------
    current_vector:
        The reader's existing preference vector, or an empty list ``[]``
        if no vector has been established yet.
    snippet_vector:
        The embedding for the snippet the reader interacted with.
        Must have 384 dimensions and must not be a zero vector.
    event_type:
        The interaction that triggered this update.
    update_count:
        How many times the reader's preference vector has previously been
        updated (``Reader.vector_update_count``).  Used to scale the
        learning rate on the very first positive interaction.

    Returns
    -------
    list[float]
        A normalised preference vector of the same dimensionality as
        *snippet_vector*.

    Raises
    ------
    ValueError
        If *snippet_vector* is malformed, is a zero vector, or if
        *current_vector* has a different dimensionality to *snippet_vector*.
    """
    # ---- validate the snippet vector first (always required) ---------------
    validate_vector(snippet_vector, label="snippet_vector")
    norm_snippet = normalize_vector(snippet_vector)

    weight = INTERACTION_WEIGHTS[event_type]
    is_first_interaction = len(current_vector) == 0

    # ---- first positive interaction: initialise from snippet ---------------
    if is_first_interaction:
        if weight <= 0:
            # A skip on a reader who has no history is a no-op; we have
            # nothing to push away from.  Return the snippet vector itself
            # as the seed so the reader gets *some* preference.
            return norm_snippet
        # Initialise directly with the (normalised) snippet vector.
        return norm_snippet

    # ---- subsequent interactions -------------------------------------------
    validate_vector(current_vector, label="current_vector")

    if len(current_vector) != len(snippet_vector):
        raise ValueError(
            f"Dimension mismatch: current_vector has {len(current_vector)} "
            f"dimensions but snippet_vector has {len(snippet_vector)} dimensions"
        )

    norm_current = normalize_vector(current_vector)

    if weight > 0:
        # Blend: move toward the snippet.
        # Learning rate decays as the reader accrues more updates so that
        # early interactions have a stronger influence.
        # alpha  = weight / (update_count + 1)  capped at *weight* itself.
        alpha = weight / max(update_count, 1)
        alpha = min(alpha, weight)

        blended = [
            norm_current[i] * (1.0 - alpha) + norm_snippet[i] * alpha
            for i in range(len(norm_current))
        ]
    else:
        # Skip: move *away* from the snippet.
        # We compute the repulsion component as: current - |weight| * snippet
        # then clip each component to _SKIP_CLIP_MIN to prevent explosion.
        repulsion = abs(weight)
        blended = [
            max(norm_current[i] - repulsion * norm_snippet[i], _SKIP_CLIP_MIN)
            for i in range(len(norm_current))
        ]

    # Guard against the pathological case where blending produces a zero vector
    # (e.g. current == -snippet after a skip).  Fall back to the current vector.
    if all(v == 0.0 for v in blended):
        return norm_current

    return normalize_vector(blended)
