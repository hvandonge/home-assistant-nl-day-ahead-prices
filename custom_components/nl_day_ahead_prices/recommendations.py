"""Reusable EnerPrice recommendation snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .advisor import build_price_advice
from .analysis.rating import price_ratings
from .analysis.trend import trend_for_prices
from .analysis.volatility import volatility
from .models import PriceEntry, current_price
from .scoring import calculate_opportunity, calculate_price_score


def recommendation_snapshot(prices: list[PriceEntry], now: datetime) -> dict[str, Any]:
    """Calculate shared advisor, score, and opportunity data once."""
    current = current_price(prices, now)
    score = calculate_price_score(current, prices)
    _, rating = price_ratings(current, prices)
    trend = trend_for_prices(prices, now)
    stats = volatility(prices)
    advisor = build_price_advice(
        current_price=current,
        all_in_price=current,
        score=score,
        rating=rating,
        trend=trend["trend"],
        volatility=stats["level"],
    )
    return {
        "price_score": score,
        "advisor": advisor,
        "opportunity": calculate_opportunity(prices),
    }
