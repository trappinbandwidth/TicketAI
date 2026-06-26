"""
Carrier lookup service — backed by data/motus_carriers.json.

Provides O(1) DOT# lookups for:
  - Carrier name, status, location
  - Active/suspended/revoked flag
  - Human-readable carrier context note for Research Ron

Loaded once at startup. Re-run scripts/ingest_motus_carriers.py to refresh.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR       = Path(__file__).parent.parent.parent / "data"
_CARRIERS_PATH  = _DATA_DIR / "motus_carriers.json"
_SUSPENDED_PATH = _DATA_DIR / "motus_suspended.json"
_CRASH_DOT_PATH = _DATA_DIR / "crash_by_dot.json"
_INSP_PATH      = _DATA_DIR / "inspection_national_stats.json"

_CARRIERS:    dict[str, Any] = {}
_SUSPENDED:   set[str]       = set()
_CRASH_DOT:   dict[str, Any] = {}
_INSP_STATS:  dict[str, Any] = {}
_LOADED = False


def _load() -> None:
    global _CARRIERS, _SUSPENDED, _CRASH_DOT, _INSP_STATS, _LOADED
    if _LOADED:
        return
    try:
        _CARRIERS = json.loads(_CARRIERS_PATH.read_text())
        logger.info("carrier_lookup: loaded %d carriers", len(_CARRIERS))
    except FileNotFoundError:
        logger.warning("motus_carriers.json not found — run scripts/ingest_motus_carriers.py")
        _CARRIERS = {}
    try:
        _SUSPENDED = set(json.loads(_SUSPENDED_PATH.read_text()))
    except FileNotFoundError:
        _SUSPENDED = set()
    try:
        _CRASH_DOT = json.loads(_CRASH_DOT_PATH.read_text())
        logger.info("carrier_lookup: loaded crash history for %d carriers", len(_CRASH_DOT))
    except FileNotFoundError:
        logger.warning("crash_by_dot.json not found — run scripts/ingest_crash_data.py")
        _CRASH_DOT = {}
    try:
        _INSP_STATS = json.loads(_INSP_PATH.read_text())
        logger.info("carrier_lookup: loaded inspection national stats (%d years)", len(_INSP_STATS))
    except FileNotFoundError:
        _INSP_STATS = {}
    _LOADED = True


def lookup_carrier(dot_number: str) -> dict[str, Any] | None:
    """
    Returns carrier record for the given DOT number, or None if not found.

    Result keys: usdot_number, legal_name, dba_name, status, auth_type,
                 state, city, zip, phone, min_coverage
    """
    _load()
    if not dot_number or not _CARRIERS:
        return None
    return _CARRIERS.get(str(dot_number).strip())


def is_carrier_active(dot_number: str) -> bool | None:
    """Returns True=active, False=suspended/revoked, None=unknown."""
    carrier = lookup_carrier(dot_number)
    if carrier is None:
        return None
    return carrier.get("status") == "Active"


def lookup_crash_history(dot_number: str) -> dict[str, Any] | None:
    """Returns crash history for a DOT#, or None if not in crash database."""
    _load()
    if not dot_number or not _CRASH_DOT:
        return None
    return _CRASH_DOT.get(str(dot_number).strip())


def get_national_inspection_stats(year: int | None = None) -> dict[str, Any]:
    """
    Returns national inspection stats for a given year (or most recent available).
    Keys: total_inspections, violation_rate, oos_rate, clean_rate
    """
    _load()
    if not _INSP_STATS:
        return {}
    if year and str(year) in _INSP_STATS:
        return _INSP_STATS[str(year)]
    # Most recent year
    latest = max(_INSP_STATS.keys(), default=None)
    return _INSP_STATS.get(latest, {}) if latest else {}


def carrier_context_note(dot_number: str) -> dict[str, Any]:
    """
    Returns a structured dict for Research Ron's jurisdiction_context.
    Always returns a dict (never None) so Ron's output is consistent.
    """
    _load()
    if not dot_number:
        return {"found": False, "note": "No DOT number on this document."}

    carrier = lookup_carrier(dot_number)
    if carrier is None:
        return {
            "found": False,
            "dot_number": dot_number,
            "note": f"DOT# {dot_number} not found in FMCSA carrier database.",
        }

    name   = carrier.get("dba_name") or carrier.get("legal_name") or "Unknown carrier"
    status = carrier.get("status", "Unknown")
    loc    = ", ".join(
        p for p in [carrier.get("city"), carrier.get("state")] if p
    )

    # Crash history enrichment
    crash = lookup_crash_history(dot_number)
    crash_note = ""
    if crash and crash.get("crash_count", 0) > 0:
        c = crash["crash_count"]
        f = crash.get("fatal_count", 0)
        recent = crash.get("most_recent_year")
        crash_note = f" Crash history: {c} crash{'es' if c != 1 else ''}"
        if f:
            crash_note += f", {f} fatal{'ities' if f != 1 else 'ity'}"
        if recent:
            crash_note += f" (most recent: {recent})"
        crash_note += "."

    if status == "Active":
        note = f"Carrier {name} (DOT# {dot_number}) — authority Active"
        if loc:
            note += f", based in {loc}"
        note += "."
    elif status in {"Inactive", "Revoked", "Revoked/Suspended"}:
        note = (
            f"⚠ Carrier {name} (DOT# {dot_number}) authority is {status}. "
            "This may indicate the driver is operating outside authorized carrier status — "
            "flag for attorney review."
        )
    else:
        note = f"Carrier {name} (DOT# {dot_number}) — status: {status}."

    if crash_note:
        note += crash_note

    return {
        "found":        True,
        "dot_number":   dot_number,
        "legal_name":   carrier.get("legal_name", ""),
        "dba_name":     carrier.get("dba_name", ""),
        "status":       status,
        "active":       status == "Active",
        "state":        carrier.get("state", ""),
        "city":         carrier.get("city", ""),
        "auth_type":    carrier.get("auth_type", ""),
        "crash_count":  crash.get("crash_count", 0)  if crash else 0,
        "fatal_count":  crash.get("fatal_count", 0)  if crash else 0,
        "crash_states": crash.get("states", [])       if crash else [],
        "note":         note,
    }
