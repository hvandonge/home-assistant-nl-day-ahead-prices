"""Current price score."""

from __future__ import annotations

from typing import Any

from ..models import PriceEntry


def calculate_price_score(current: float | None, prices: list[PriceEntry]) -> dict[str, Any]:
    """Map a price onto a stable 0-100 score, including negative prices."""
    if current is None or not prices:
        return {"score": None, "score_label": None, "percentile": None}
    values = sorted(item.price for item in prices)
    low, high = values[0], values[-1]
    score = 50.0 if high == low else (high - current) / (high - low) * 100
    score = min(100.0, max(0.0, score))
    percentile = sum(value <= current for value in values) / len(values) * 100
    return {
        "score": round(score),
        "percentile": round(percentile, 1),
        "min_reference_price": round(low, 6),
        "max_reference_price": round(high, 6),
        "average_reference_price": round(sum(values) / len(values), 6),
        "score_label": score_label(score),
    }


def score_label(score: float) -> str:
    """Return the label for a numeric price score."""
    if score >= 90:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 40:
        return "normal"
    if score >= 20:
        return "expensive"
    return "very_expensive"
