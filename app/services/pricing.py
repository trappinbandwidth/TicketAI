"""
Pricing estimator — V1.
Looks up historical attorney cost from Price_Summary__c snapshot (pricing_table.json),
adds the Rig Resolve service fee, and returns a 15–20% variance range.

The table is loaded once at import time. To refresh it after a Salesforce export,
replace pricing_table.json and restart the server.
"""
import json
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CDL_FEE = 400          # flat Rig Resolve service fee added to every attorney cost
MARGIN_LOW = 0.15      # lower bound: 15% below base
MARGIN_HIGH = 0.20     # upper bound: 20% above base

_TABLE_PATH = Path(__file__).parent / "pricing_table.json"

# Load once at startup
try:
    _PRICING_TABLE: dict = json.loads(_TABLE_PATH.read_text())
    logger.info("pricing: loaded %d states from %s", len(_PRICING_TABLE), _TABLE_PATH.name)
except FileNotFoundError:
    _PRICING_TABLE = {}
    logger.warning("pricing: pricing_table.json not found — all estimates will be unavailable")


@dataclass
class PriceEstimate:
    state: str
    violation_category: str
    avg_attny_price: float
    cdl_fee: int
    driver_price_base: int
    driver_price_low: int
    driver_price_high: int
    win_rate_pct: float
    sample_size: int
    high_risk: bool
    data_source: str   # "historical" | "fallback" | "unavailable"
    note: str = ""


def get_price_estimate(state: str, violation_category: str) -> PriceEstimate:
    """
    Returns a price estimate for the given state + violation category.
    Falls back to state-level median if exact match not found.
    Falls back to national median if state not found.
    """
    state_data = _PRICING_TABLE.get(state, {})
    row = state_data.get(violation_category)

    if row:
        return PriceEstimate(
            state=state,
            violation_category=violation_category,
            avg_attny_price=row["avg_attny_price"],
            cdl_fee=CDL_FEE,
            driver_price_base=row["driver_price_base"],
            driver_price_low=row["driver_price_low"],
            driver_price_high=row["driver_price_high"],
            win_rate_pct=row["win_rate_pct"],
            sample_size=row["sample_size"],
            high_risk=row["high_risk"],
            data_source="historical",
        )

    # Fallback 1: state median across all violations
    if state_data:
        prices = [v["avg_attny_price"] for v in state_data.values()]
        avg = sum(prices) / len(prices)
        base = round(avg + CDL_FEE)
        return PriceEstimate(
            state=state,
            violation_category=violation_category,
            avg_attny_price=round(avg, 2),
            cdl_fee=CDL_FEE,
            driver_price_base=base,
            driver_price_low=round(base * (1 - MARGIN_LOW)),
            driver_price_high=round(base * (1 + MARGIN_HIGH)),
            win_rate_pct=0.0,
            sample_size=0,
            high_risk=False,
            data_source="fallback",
            note=f"No exact match for '{violation_category}' in {state} — using state average.",
        )

    # Fallback 2: national median
    all_prices = [
        v["avg_attny_price"]
        for state_rows in _PRICING_TABLE.values()
        for v in state_rows.values()
    ]
    if all_prices:
        avg = sum(all_prices) / len(all_prices)
        base = round(avg + CDL_FEE)
        return PriceEstimate(
            state=state,
            violation_category=violation_category,
            avg_attny_price=round(avg, 2),
            cdl_fee=CDL_FEE,
            driver_price_base=base,
            driver_price_low=round(base * (1 - MARGIN_LOW)),
            driver_price_high=round(base * (1 + MARGIN_HIGH)),
            win_rate_pct=0.0,
            sample_size=0,
            high_risk=False,
            data_source="fallback",
            note=f"No data for {state} — using national average.",
        )

    return PriceEstimate(
        state=state,
        violation_category=violation_category,
        avg_attny_price=0,
        cdl_fee=CDL_FEE,
        driver_price_base=0,
        driver_price_low=0,
        driver_price_high=0,
        win_rate_pct=0.0,
        sample_size=0,
        high_risk=False,
        data_source="unavailable",
        note="Pricing table not loaded.",
    )
