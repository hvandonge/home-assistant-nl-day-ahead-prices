"""Home battery arbitrage planner."""

from __future__ import annotations

from typing import Any

from ..models import PriceEntry
from ..optimizer import optimize_intervals


def plan_battery(
    prices: list[PriceEntry],
    *,
    battery_capacity_kwh: float,
    current_soc_percent: float,
    min_soc_percent: float,
    max_soc_percent: float,
    charge_power_kw: float,
    discharge_power_kw: float,
    roundtrip_efficiency_percent: float = 90,
    allow_grid_charge: bool = True,
    allow_export: bool = False,
    margin: float = 0.01,
) -> dict[str, Any]:
    """Build a simple efficiency-aware charge/discharge strategy."""
    if battery_capacity_kwh <= 0 or charge_power_kw <= 0 or discharge_power_kw <= 0:
        raise ValueError("battery capacity and power values must be positive")
    if not 0 < roundtrip_efficiency_percent <= 100:
        raise ValueError("roundtrip_efficiency_percent must be between 0 and 100")
    if not min_soc_percent <= current_soc_percent <= max_soc_percent:
        raise ValueError("current SOC must be between min and max SOC")
    usable_charge = battery_capacity_kwh * (max_soc_percent - current_soc_percent) / 100
    usable_discharge = battery_capacity_kwh * (current_soc_percent - min_soc_percent) / 100
    charge_minutes = max(15, round(usable_charge / max(charge_power_kw, 0.001) * 60))
    discharge_minutes = max(15, round(usable_discharge / max(discharge_power_kw, 0.001) * 60))
    charge = optimize_intervals(prices, charge_minutes) if allow_grid_charge and usable_charge > 0 else None
    inverted = [PriceEntry(item.time, -item.price) for item in prices]
    discharge_raw = optimize_intervals(inverted, discharge_minutes) if usable_discharge > 0 else None
    discharge_average = -discharge_raw["average_price"] if discharge_raw else None
    charge_average = charge["average_price"] if charge else None
    efficiency = roundtrip_efficiency_percent / 100
    opportunity = bool(
        charge_average is not None
        and discharge_average is not None
        and discharge_average * efficiency - charge_average > margin
    )
    shifted = min(usable_charge, usable_discharge) * efficiency
    savings = (discharge_average * efficiency - charge_average) * shifted if opportunity else 0.0
    return {
        "charge_windows": [charge] if charge and opportunity else [],
        "discharge_windows": [
            {
                **discharge_raw,
                "average_price": round(discharge_average, 6),
                "mode": "export" if allow_export else "avoid_grid_import",
            }
        ] if discharge_raw and (opportunity or not allow_grid_charge) else [],
        "expected_savings": round(max(0.0, savings), 4),
        "expected_cycle_cost": round(charge_average * usable_charge, 4) if charge_average is not None else 0.0,
        "arbitrage_opportunity": opportunity,
        "recommendation": (
            "Charge low and discharge high."
            if opportunity
            else "Discharge during peak prices to avoid grid import."
            if discharge_raw and not allow_grid_charge
            else "Price spread does not cover efficiency loss and margin."
        ),
    }
