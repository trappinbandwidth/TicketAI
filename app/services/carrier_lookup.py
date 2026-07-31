"""
Carrier lookup service — backed by data/motus_carriers.json.

Provides O(1) DOT# lookups for:
  - Carrier name, status, location
  - Active/suspended/revoked flag
  - Human-readable carrier context note for Banneker

Loaded once at startup. Re-run scripts/ingest_motus_carriers.py to refresh.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
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
_SEARCH_SOURCE_ID: int | None = None
_SEARCH_ROWS: list[tuple[str, str, str, str, str]] = []
_DOCKET_INDEX: dict[str, list[str]] = {}
_PHONE_INDEX: dict[str, list[str]] = {}
_NON_ALPHANUMERIC = re.compile(r"[^A-Z0-9]+")


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


def _normalized_text(value: Any) -> str:
    return " ".join(_NON_ALPHANUMERIC.sub(" ", str(value).upper()).split())


def _digits(value: Any) -> str:
    return "".join(character for character in str(value) if character.isdigit())


def _ensure_search_index() -> None:
    global _SEARCH_SOURCE_ID, _SEARCH_ROWS, _DOCKET_INDEX, _PHONE_INDEX
    if _SEARCH_SOURCE_ID == id(_CARRIERS):
        return
    rows: list[tuple[str, str, str, str, str]] = []
    docket_index: dict[str, list[str]] = {}
    phone_index: dict[str, list[str]] = {}
    for dot_number, carrier in _CARRIERS.items():
        legal = _normalized_text(carrier.get("legal_name", ""))
        dba = _normalized_text(carrier.get("dba_name", ""))
        city = _normalized_text(carrier.get("city", ""))
        state = str(carrier.get("state") or "").upper()
        rows.append((dot_number, legal, dba, city, state))
        docket = _normalized_text(carrier.get("docket_number", ""))
        phone = _digits(carrier.get("phone", ""))
        if docket:
            docket_index.setdefault(docket, []).append(dot_number)
        if phone:
            phone_index.setdefault(phone, []).append(dot_number)
    _SEARCH_ROWS = rows
    _DOCKET_INDEX = docket_index
    _PHONE_INDEX = phone_index
    _SEARCH_SOURCE_ID = id(_CARRIERS)


def warm_carrier_search_index() -> int:
    """Load and normalize the public index during app startup, not first search."""
    _load()
    _ensure_search_index()
    return len(_SEARCH_ROWS)


def _source_provenance() -> dict[str, Any]:
    try:
        modified = datetime.fromtimestamp(
            _CARRIERS_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    except OSError:
        modified = None
    return {
        "source": "FMCSA public motor-carrier authority data",
        "source_kind": "authoritative_public",
        "local_index": _CARRIERS_PATH.name,
        "cached_at": modified,
        "official_record_update_note": (
            "Changes made in TIP do not update FMCSA. Use the applicable FMCSA process "
            "to change the official record."
        ),
    }


def public_carrier_record(dot_number: str, include_contact: bool = True) -> dict[str, Any] | None:
    """Return only whitelisted public FMCSA fields with explicit provenance."""
    carrier = lookup_carrier(_digits(dot_number))
    if carrier is None:
        return None
    phone = _digits(carrier.get("phone", ""))
    record = {
        "dot_number": str(carrier.get("usdot_number") or _digits(dot_number)),
        "docket_number": carrier.get("docket_number") or None,
        "legal_name": carrier.get("legal_name") or None,
        "dba_name": carrier.get("dba_name") or None,
        "operating_status": carrier.get("status") or "Unknown",
        "authority_type": carrier.get("auth_type") or None,
        "city": carrier.get("city") or None,
        "state": carrier.get("state") or None,
        "zip": carrier.get("zip") or None,
        "minimum_coverage": carrier.get("min_coverage") or None,
        "passenger": bool(carrier.get("passenger", False)),
        "hazmat": bool(carrier.get("hazmat", False)),
        "phone": phone or None if include_contact else None,
        "phone_last4": phone[-4:] if len(phone) >= 4 else None,
    }
    if not include_contact:
        record.pop("phone")
    return record


def search_carriers(
    query: str, state: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """Bounded local search across public USDOT, docket, name, city, and phone."""
    _load()
    normalized_query = _normalized_text(query)
    query_digits = _digits(query)
    state = (state or "").strip().upper()
    if len(normalized_query) < 2 or not _CARRIERS:
        return []

    matches: list[tuple[int, str, dict[str, Any]]] = []
    if query_digits and query_digits in _CARRIERS:
        exact = public_carrier_record(query_digits, include_contact=False)
        if exact and (not state or exact.get("state") == state):
            return [exact]

    _ensure_search_index()
    exact_identifiers = {
        *(_DOCKET_INDEX.get(normalized_query) or []),
        *((_PHONE_INDEX.get(query_digits) or []) if len(query_digits) >= 7 else ()),
    }
    for dot_number in exact_identifiers:
        public = public_carrier_record(dot_number, include_contact=False)
        if public and (not state or public.get("state") == state):
            matches.append((95, _normalized_text(public.get("legal_name", "")), public))

    exact_set = set(exact_identifiers)
    for dot_number, legal, dba, city, carrier_state in _SEARCH_ROWS:
        if dot_number in exact_set or (state and carrier_state != state):
            continue
        score = 0
        if normalized_query in {legal, dba}:
            score = 85
        elif any(value.startswith(normalized_query) for value in (legal, dba) if value):
            score = 75
        elif any(normalized_query in value for value in (legal, dba) if value):
            score = 60
        elif city.startswith(normalized_query):
            score = 40
        if score:
            public = public_carrier_record(dot_number, include_contact=False)
            if public:
                matches.append((score, legal or dba, public))
    matches.sort(key=lambda item: (-item[0], item[1], item[2]["dot_number"]))
    return [item[2] for item in matches[: max(1, min(limit, 20))]]


def carrier_discovery_detail(dot_number: str) -> dict[str, Any] | None:
    """Return a selected public Carrier record plus carrier-level crash context."""
    record = public_carrier_record(dot_number, include_contact=True)
    if record is None:
        return None
    crash = lookup_crash_history(record["dot_number"]) or {}
    return {
        **record,
        "carrier_level_crash_context": {
            "crash_count": int(crash.get("crash_count") or 0),
            "fatal_count": int(crash.get("fatal_count") or 0),
            "most_recent_year": crash.get("most_recent_year"),
            "scope_note": (
                "Carrier-level public context. This is not an individual Driver safety record."
            ),
        },
        "provenance": _source_provenance(),
    }


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
    Returns a structured dict for Banneker's jurisdiction_context.
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
