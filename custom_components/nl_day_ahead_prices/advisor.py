"""Central EnerPrice advice engine."""

from __future__ import annotations

from typing import Any


def build_price_advice(
    *,
    current_price: float | None,
    all_in_price: float | None,
    score: dict[str, Any],
    rating: str | None,
    trend: str,
    volatility: str | None,
    language: str = "en",
) -> dict[str, Any]:
    """Combine price signals into one practical recommendation."""
    numeric = score.get("score")
    if numeric is None:
        return _advice("neutral", 50, current_price, all_in_price, rating, trend, volatility, language)
    if numeric >= 90 or (all_in_price is not None and all_in_price < 0):
        state = "excellent"
    elif numeric >= 70:
        state = "good"
    elif numeric < 10 or (numeric < 20 and trend in {"rising", "strongly_rising"}):
        state = "critical"
    elif numeric < 40:
        state = "avoid"
    else:
        state = "neutral"
    return _advice(state, numeric, current_price, all_in_price, rating, trend, volatility, language)


def _advice(
    state: str,
    score: float,
    current_price: float | None,
    all_in_price: float | None,
    rating: str | None,
    trend: str,
    volatility: str | None,
    language: str,
) -> dict[str, Any]:
    is_dutch = language.lower().startswith("nl")
    content = (
        {
            "excellent": ("Zeer goedkoop moment", "Dit is een van de goedkoopste beschikbare periodes.", "Goed moment om grootverbruikers te starten."),
            "good": ("Gunstige prijs", "De huidige prijs is lager dan de meeste beschikbare periodes.", "Gebruik flexibele apparaten waar mogelijk nu."),
            "neutral": ("Normale prijs", "De huidige prijs ligt rond het normale niveau.", "Er is geen directe actie nodig."),
            "avoid": ("Duur moment", "Er zijn goedkopere periodes beschikbaar.", "Stel grootverbruikers indien mogelijk uit."),
            "critical": ("Zeer duur moment", "Dit is een van de duurste beschikbare periodes.", "Vermijd nu onnodig energieverbruik."),
        }
        if is_dutch
        else {
            "excellent": ("Very cheap moment", "This is one of the cheapest available periods.", "Good time to start large consumers."),
            "good": ("Favorable price", "The current price is below most available periods.", "Use flexible appliances now where practical."),
            "neutral": ("Normal price", "The current price is around the normal range.", "No urgent action is needed."),
            "avoid": ("Expensive moment", "Cheaper periods are available.", "Postpone large consumers if possible."),
            "critical": ("Very expensive moment", "This is one of the most expensive available periods.", "Avoid optional consumption now."),
        }
    )
    title, message, recommendation = content[state]
    cheap_actions = (
        ["EV laden", "Boiler verwarmen", "Wasmachine draaien", "Thuisbatterij laden"]
        if is_dutch
        else ["Charge EV", "Heat boiler", "Run washing machine", "Charge home battery"]
    )
    expensive_actions = (
        ["EV laden", "Droger gebruiken", "Boiler elektrisch bijverwarmen"]
        if is_dutch
        else ["Charge EV", "Use dryer", "Use electric boiler boost"]
    )
    return {
        "state": state,
        "title": title,
        "message": message,
        "recommendation": recommendation,
        "score": round(score),
        "current_price": current_price,
        "all_in_price": all_in_price,
        "rating_5_level": rating,
        "trend": trend,
        "volatility": volatility,
        "best_actions": cheap_actions if state in {"excellent", "good"} else [],
        "avoid_actions": expensive_actions if state in {"avoid", "critical"} else [],
        "reason": (
            f"Score {round(score)}/100, beoordeling {rating or 'onbekend'}, trend {trend}."
            if is_dutch
            else f"Score {round(score)}/100, rating {rating or 'unknown'}, trend {trend}."
        ),
    }
