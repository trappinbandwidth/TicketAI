import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_RULEBOOK: Optional[dict] = None
_RULEBOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "court_rulebook.json")


def _load() -> dict:
    global _RULEBOOK
    if _RULEBOOK is None:
        try:
            with open(os.path.abspath(_RULEBOOK_PATH), "r") as f:
                _RULEBOOK = json.load(f)
        except Exception as exc:
            logger.warning("court_rulebook.json not loaded: %s", exc)
            _RULEBOOK = {}
    return _RULEBOOK


def lookup_court(state: str, county: str, violation_category: str = "") -> Optional[dict]:
    """
    Returns court info for the given state/county.
    Tries county-level first, falls back to state-level defaults.
    Returns None if state is not in rulebook.
    """
    rb = _load()
    state_upper = (state or "").strip().upper()
    county_clean = (county or "").strip()

    state_data = rb.get(state_upper)
    if not state_data:
        # Try matching by full state name (e.g. "Minnesota")
        for code, data in rb.items():
            if isinstance(data, dict) and data.get("name", "").lower() == state_upper.lower():
                state_data = data
                state_upper = code
                break
    if not state_data or state_upper == "_meta":
        return None

    result = {
        "state": state_upper,
        "state_name": state_data.get("name", ""),
        "court_system": state_data.get("court_system", ""),
        "state_portal": state_data.get("state_portal", ""),
        "online_payment_url": state_data.get("online_payment_url", ""),
        "scheduling_url": state_data.get("scheduling_url") or state_data.get("online_payment_url", ""),
        "cdl_info_url": state_data.get("cdl_info_url", ""),
        "appear_required_for_serious": state_data.get("appear_required_for_serious", True),
        "notes": state_data.get("notes", ""),
        "county_court": None,
    }

    # County match — case-insensitive prefix or exact
    counties = state_data.get("counties", {})
    matched_county = _match_county(county_clean, counties)
    if matched_county:
        c = counties[matched_county]
        result["county_court"] = {
            "county": matched_county,
            "court_name": c.get("court_name", ""),
            "website": c.get("website", ""),
            "scheduling_url": c.get("scheduling_url", result["scheduling_url"]),
            "phone": c.get("phone", ""),
            "address": c.get("address", ""),
            "notes": c.get("notes", ""),
        }

    # If serious violation, surface the must-appear note
    if violation_category and result["appear_required_for_serious"]:
        result["appear_required"] = True
    else:
        result["appear_required"] = False

    return result


def _match_county(county: str, counties: dict) -> Optional[str]:
    if not county or not counties:
        return None
    county_lower = county.lower().strip()
    # Exact match
    for key in counties:
        if key.lower() == county_lower:
            return key
    # Prefix match (e.g. "St. Louis" matches "St. Louis City")
    for key in counties:
        if county_lower in key.lower() or key.lower() in county_lower:
            return key
    return None
