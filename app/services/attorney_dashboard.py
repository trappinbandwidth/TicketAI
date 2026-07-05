"""
Attorney Dashboard system — Slice 1 helpers.

Companion to Specs/Attorney_Levels/attorney_dashboard_engineering_spec.md (v1).

Ownership boundary (spec §0): this module owns the Dashboard-doc fields on
attorneys/{id} (§2.3) — profile completion, the self_sourced gate, bar-verification
status. Performance Level / win-rate / XP fields belong to attorney_levels.py and are
NOT redefined here.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Placeholder gate threshold (§8) — tunable via app_config/attorney_dashboard.
DEFAULT_SELF_SOURCED_MIN_COMPLETION = 0.80

# Fields that count toward profile_completion_pct (the §5.3 shared field set).
# states_covered / counties_covered are reused from the existing attorneys schema.
PROFILE_COMPLETION_FIELDS = [
    "bar_number",
    "bar_state",
    "states_covered",
    "counties_covered",
    "firm_name",
    "firm_address",
    "firm_phone",
    "bio",
    "profile_photo_url",
    "payout_method",
    "preferred_contact_method",
]

# Editable via PUT /profile (§4). Excludes anything gated by verification/leveling.
EDITABLE_PROFILE_FIELDS = PROFILE_COMPLETION_FIELDS + ["payout_details", "phone", "full_name"]


def dashboard_field_defaults() -> dict:
    """Defaults for the Dashboard-owned fields on attorneys/{id} (§2.3)."""
    return {
        "application_status": None,
        "application_id": None,
        "profile_completion_pct": 0.0,
        "profile_import_source": "manual",
        "bar_verification_status": "unverified",
        "bar_verification_checked_at": None,
        "self_sourced_enabled": False,
        # Pricing (Dashboard v2 §3.6). flat_rate_schedule is a map keyed by violation
        # category with a required "default", e.g. {"default": 500, "DUI": 900}. A plain
        # number is also accepted by the resolver and treated as the default.
        "pricing_mode": "case_by_case",   # "flat" | "case_by_case"
        "flat_rate_schedule": None,
    }


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def compute_profile_completion(attorney: dict) -> float:
    """Fraction (0.0–1.0) of the completion field set that is filled."""
    total = len(PROFILE_COMPLETION_FIELDS)
    if not total:
        return 0.0
    filled = sum(1 for f in PROFILE_COMPLETION_FIELDS if _is_filled(attorney.get(f)))
    return round(filled / total, 4)


def get_self_sourced_threshold(db) -> float:
    """Read the gate threshold from app_config, falling back to the default."""
    try:
        doc = db.collection("app_config").document("attorney_dashboard").get()
        if doc.exists:
            v = doc.to_dict().get("self_sourced_min_completion")
            if isinstance(v, (int, float)):
                return float(v)
    except Exception as exc:
        logger.warning("[attorney_dashboard] threshold read failed: %s", exc)
    return DEFAULT_SELF_SOURCED_MIN_COMPLETION


def recompute_profile_state(db, attorney: dict) -> dict:
    """
    Return the field updates to persist after a profile change:
    profile_completion_pct and the derived self_sourced_enabled gate (§3.1).

    Gate also requires bar verification not to be flagged — an unverified account
    can complete its profile, but a *flagged* bar status hard-blocks self-sourced.
    """
    pct = compute_profile_completion(attorney)
    threshold = get_self_sourced_threshold(db)
    bar_ok = attorney.get("bar_verification_status") != "flagged"
    return {
        "profile_completion_pct": pct,
        "self_sourced_enabled": bool(pct >= threshold and bar_ok),
    }
