"""
CDL point estimation service.
Loads cdl_point_estimates.json and returns a CdlPointEstimate for a given
state + violation category + zone flags.

All values are estimates for attorney/driver reference — not legal advice.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from app.models.response import CdlPointEstimate

logger = logging.getLogger(__name__)

_DATA: Optional[dict] = None
_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cdl_point_estimates.json")

_STATE_ABBR_TO_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}


def _load() -> dict:
    global _DATA
    if _DATA is None:
        try:
            with open(os.path.abspath(_DATA_PATH)) as f:
                _DATA = json.load(f)
        except Exception as exc:
            logger.warning("cdl_point_estimates.json not loaded: %s", exc)
            _DATA = {}
    return _DATA


def _normalize_state(state: str) -> str:
    """Return 2-letter abbreviation. Accepts full names or abbreviations."""
    s = (state or "").strip()
    if len(s) == 2:
        return s.upper()
    return _STATE_ABBR_TO_ABBR.get(s, s.upper()[:2])


def estimate_cdl_points(
    state: str,
    violation_category: str,
    school_zone: bool = False,
    construction_zone: bool = False,
) -> Optional[CdlPointEstimate]:
    """
    Return a CdlPointEstimate for the given state and violation category.
    Returns None if the category is not found in the lookup table.
    """
    data = _load()
    categories = data.get("categories", {})
    cat = categories.get(violation_category)
    if not cat:
        logger.warning("[cdl_points] unknown category=%r — no estimate available", violation_category)
        return None

    state_code = _normalize_state(state)
    overrides = cat.get("state_overrides", {})
    state_data = overrides.get(state_code)

    if state_data:
        base_min = state_data["min"]
        base_max = state_data["max"]
        src = "state_schedule"
    else:
        base_min = cat["default_min"]
        base_max = cat["default_max"]
        src = "estimate"

    zone_add = 0
    if school_zone:
        zone_add = max(zone_add, cat.get("school_zone_add", 0))
    if construction_zone:
        zone_add = max(zone_add, cat.get("construction_zone_add", 0))

    total_min = base_min + zone_add
    total_max = base_max + zone_add

    if total_min == total_max:
        display = f"{total_min} pt{'s' if total_min != 1 else ''}"
    else:
        display = f"{total_min}–{total_max} pts"

    if total_min == 0 and total_max == 0:
        display = "0 pts (no state points)"

    return CdlPointEstimate(
        violation_category=violation_category,
        state=state_code,
        state_points_min=total_min,
        state_points_max=total_max,
        state_points_display=display,
        federal_serious_violation=cat["federal_serious"],
        federal_major_violation=cat["federal_major"],
        disqualification_risk=cat["disqualification_risk"],
        disqualification_note=cat["disqualification_note"],
        csa_severity_weight=cat["csa_severity_weight"],
        insurance_impact=cat["insurance_impact"],
        school_zone_applied=school_zone,
        construction_zone_applied=construction_zone,
        zone_points_added=zone_add,
        data_source=src,
    )
