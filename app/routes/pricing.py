"""
Pricing endpoint — GET /api/v1/price-estimate
Returns driver price range for a given state + violation category.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query
import os
from pydantic import BaseModel

from app.services.pricing import get_price_estimate

router = APIRouter()


class PriceEstimateResponse(BaseModel):
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
    data_source: str
    note: str
    display: str  # human-readable summary e.g. "$765 – $1,080"


@router.get("/price-estimate", response_model=PriceEstimateResponse)
def price_estimate(
    state: str = Query(..., description="Full state name, e.g. 'Florida'"),
    violation: str = Query(..., description="Violation category from picklist"),
    x_api_key: Optional[str] = Header(None),
):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    est = get_price_estimate(state, violation)
    display = (
        f"${est.driver_price_low:,} – ${est.driver_price_high:,}"
        if est.driver_price_base > 0
        else "Unavailable"
    )
    return PriceEstimateResponse(
        **est.__dict__,
        display=display,
    )
