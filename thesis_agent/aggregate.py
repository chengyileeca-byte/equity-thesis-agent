"""Rules-based overall rating — a deterministic *cross-check*, not the verdict.

The model gives the authoritative `overall_rating` (its holistic judgment is more
accurate than any fixed formula). This module computes a simple, confidence-
weighted baseline from the dimension ratings and shows it alongside, so a reader
can see when the model's gestalt diverges from a mechanical roll-up — and the
eval harness measures that agreement (calibration) and the model's run-to-run
stability. Same dimensions in → same baseline out.

A known blind spot (any `insufficient_data` dimension) caps baseline confidence.
"""

from .schema import Confidence, DimensionAssessment, Rating

_RATING_SCORE = {
    "strong_positive": 2.0,
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
    "strong_negative": -2.0,
}
_CONF_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}


def compute_overall(
    dimensions: list[DimensionAssessment],
) -> tuple[Rating, Confidence]:
    total = len(dimensions)
    contrib = [d for d in dimensions if d.rating.value != "insufficient_data"]
    if not contrib:
        return Rating.insufficient_data, Confidence.low

    weights = [_CONF_WEIGHT[d.confidence.value] for d in contrib]
    wsum = sum(weights)
    score = sum(
        _RATING_SCORE[d.rating.value] * w for d, w in zip(contrib, weights)
    ) / wsum

    if score >= 1.25:
        rating = Rating.strong_positive
    elif score >= 0.4:
        rating = Rating.positive
    elif score > -0.4:
        rating = Rating.neutral
    elif score > -1.25:
        rating = Rating.negative
    else:
        rating = Rating.strong_negative

    coverage = len(contrib) / total
    mean_conf = wsum / len(contrib)
    if coverage >= 0.8 and mean_conf >= 0.7:
        confidence = Confidence.high
    elif coverage < 0.5 or mean_conf < 0.45:
        confidence = Confidence.low
    else:
        confidence = Confidence.medium

    # A known blind spot caps confidence.
    n_insufficient = total - len(contrib)
    if n_insufficient >= total / 2:
        confidence = Confidence.low
    elif n_insufficient > 0 and confidence == Confidence.high:
        confidence = Confidence.medium

    return rating, confidence
