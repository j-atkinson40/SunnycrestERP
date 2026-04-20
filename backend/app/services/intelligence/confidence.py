"""Confidence score → tier mapping.

Every Intelligence prompt that asks for a confidence score returns a
float in [0.0, 1.0]. Consumers that want a user-facing tier
(green/amber/gray) need to translate consistently. Centralizing the
thresholds here prevents the translation from drifting between
callers.

Thresholds (approved for the arc):
  >= 0.80 → "high"
  >= 0.50 → "medium"
  else   → "low"

Callers:
  - triage AI question panel (follow-up 2)
  - future AI-response consumers (spec signals reuse)

If future work needs different thresholds for different domains, add
a `domain: str` kwarg here rather than re-implementing in each
caller. The threshold set is cheap to parameterize once we have a
real second use case.
"""

from __future__ import annotations

from typing import Literal

ConfidenceTier = Literal["high", "medium", "low"]

# Thresholds are inclusive on the lower bound.
_HIGH_THRESHOLD: float = 0.80
_MEDIUM_THRESHOLD: float = 0.50


def to_tier(score: float | int | None) -> ConfidenceTier:
    """Map a numeric confidence score to a tier label.

    Defensive: non-numeric / None / out-of-range inputs collapse to
    "low" rather than raising. Intelligence responses occasionally
    come back without the field; we'd rather show a grey dot than
    500 the whole request.
    """
    if score is None:
        return "low"
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "low"
    if value >= _HIGH_THRESHOLD:
        return "high"
    if value >= _MEDIUM_THRESHOLD:
        return "medium"
    return "low"


__all__ = ["ConfidenceTier", "to_tier"]
