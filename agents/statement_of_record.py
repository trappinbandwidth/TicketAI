"""
Statement of Record — Agent 9.

Builds the dual-account statement the attorney reads before accepting a case:
  - Officer's account: derived from Lone Ranger's extracted ticket fields
  - Driver's account: the 9-field structured statement captured at upload
  - Conflict map: field-by-field divergences between the two accounts
  - Evidence index: driver-submitted audio/video/photos tagged to disputes

Runs after Team Quest so all extraction data is stable and scored.
Does not affect routing — output is informational only, passed through to
the final result and written to Firestore for attorney portal display.
"""
from __future__ import annotations

import logging
import re

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "statement_of_record"

# Fields the driver can directly dispute through the statement form
_DISPUTEABLE_FIELDS = {
    "Violation_Category__c":     "officer_stated_violation",
    "Ticket_State__c":           "location_when_stopped",
    "Ticket_County__c":          "location_when_stopped",
    "School_Zone__c":            "road_signs_visible",
    "Construction_Zone__c":      "road_signs_visible",
}

_SPEED_RE = re.compile(r'\b(\d{2,3})\s*(?:mph|miles?\s*per\s*hour)', re.IGNORECASE)


def _fv(extraction: dict, field: str) -> str:
    """Safe field value extractor."""
    f = extraction.get(field)
    if isinstance(f, dict):
        return (f.get("value") or "").strip()
    return ""


def _build_officer_account(extraction: dict) -> dict:
    """Summarise what the ticket itself says happened."""
    return {
        "violation_category": _fv(extraction, "Violation_Category__c"),
        "violation_description": _fv(extraction, "Violation_Description__c"),
        "location_state": _fv(extraction, "Ticket_State__c"),
        "location_county": _fv(extraction, "Ticket_County__c"),
        "location_city": _fv(extraction, "Ticket_City__c"),
        "school_zone": _fv(extraction, "School_Zone__c"),
        "construction_zone": _fv(extraction, "Construction_Zone__c"),
        "date_of_ticket": _fv(extraction, "Date_of_Ticket__c"),
        "court_date": _fv(extraction, "Court_Date__c"),
        "citation_number": _fv(extraction, "Citation_Number__c"),
        "source": "ticket_fields",
    }


def _extract_officer_speed(violation_description: str) -> str | None:
    """Pull the first mph figure from the officer's violation description."""
    m = _SPEED_RE.search(violation_description)
    return m.group(1) if m else None


def _build_conflict_map(
    officer: dict,
    driver_stmt: dict,
    violation_description: str,
) -> list[dict]:
    conflicts: list[dict] = []

    # Violation description: does driver's stated violation match the ticket category?
    officer_viol = officer.get("violation_category", "")
    driver_viol  = (driver_stmt.get("officer_stated_violation") or "").strip()
    if driver_viol and officer_viol and driver_viol.lower() != officer_viol.lower():
        conflicts.append({
            "field": "violation",
            "officer_says": officer_viol,
            "driver_says": driver_viol,
            "conflict_type": "VIOLATION_DESCRIPTION_MISMATCH",
            "note": "Driver's description of the stated violation differs from ticket classification.",
        })

    # Speed: extract officer's mph from violation description, compare to driver's stated speed
    officer_speed_str = _extract_officer_speed(violation_description)
    driver_speed_str  = (driver_stmt.get("your_speed") or "").strip()
    if officer_speed_str and driver_speed_str:
        driver_speed_match = _SPEED_RE.search(driver_speed_str)
        driver_mph = int(driver_speed_match.group(1)) if driver_speed_match else None
        officer_mph = int(officer_speed_str)
        if driver_mph and driver_mph != officer_mph:
            conflicts.append({
                "field": "speed",
                "officer_says": f"{officer_mph} mph",
                "driver_says": driver_speed_str,
                "conflict_type": "SPEED_DISPUTE",
                "note": f"Driver disputes speed: officer recorded {officer_mph} mph, driver states {driver_mph} mph.",
            })

    # School zone: ticket says yes, driver says signs not visible
    school_zone = officer.get("school_zone", "")
    signs_note = (driver_stmt.get("road_signs_visible") or "").lower()
    if school_zone.lower() == "yes" and signs_note and any(
        kw in signs_note for kw in ("no sign", "not visible", "obscured", "missing", "hidden", "couldn't see")
    ):
        conflicts.append({
            "field": "school_zone",
            "officer_says": "School zone active",
            "driver_says": driver_stmt.get("road_signs_visible", ""),
            "conflict_type": "ZONE_SIGN_DISPUTE",
            "note": "Officer recorded school zone; driver disputes sign visibility.",
        })

    # Construction zone: same pattern
    construction_zone = officer.get("construction_zone", "")
    if construction_zone.lower() == "yes" and signs_note and any(
        kw in signs_note for kw in ("no sign", "not visible", "obscured", "missing", "inactive", "not active")
    ):
        conflicts.append({
            "field": "construction_zone",
            "officer_says": "Construction zone active",
            "driver_says": driver_stmt.get("road_signs_visible", ""),
            "conflict_type": "ZONE_SIGN_DISPUTE",
            "note": "Officer recorded construction zone; driver disputes zone was active.",
        })

    # Catch-all: driver explicitly flagged ticket errors
    dispute_text = (driver_stmt.get("dispute_ticket_details") or "").strip()
    if dispute_text:
        conflicts.append({
            "field": "driver_flagged_errors",
            "officer_says": "(see ticket)",
            "driver_says": dispute_text,
            "conflict_type": "DRIVER_FLAGGED_ERROR",
            "note": "Driver explicitly identified factual errors on the ticket.",
        })

    return conflicts


def _build_evidence_index(
    evidence_files: list,
    conflicts: list[dict],
) -> list[dict]:
    """
    Tag each evidence file to the conflict(s) its caption most likely supports.
    Matching is keyword-based — attorneys can override in the portal.
    """
    KEYWORD_MAP = {
        "SPEED_DISPUTE":       ["speed", "mph", "speedometer", "radar"],
        "ZONE_SIGN_DISPUTE":   ["sign", "zone", "school", "construction", "visible"],
        "VIOLATION_DESCRIPTION_MISMATCH": ["violation", "charge", "stop", "officer said"],
        "DRIVER_FLAGGED_ERROR": ["wrong", "incorrect", "error", "mistake", "plate", "license"],
    }

    conflict_types = {c["conflict_type"] for c in conflicts}
    indexed = []

    for ef in evidence_files:
        caption = (ef.get("caption") or "").lower()
        linked_conflicts: list[str] = []

        for conflict_type, keywords in KEYWORD_MAP.items():
            if conflict_type in conflict_types and any(kw in caption for kw in keywords):
                linked_conflicts.append(conflict_type)

        indexed.append({
            "filename": ef.get("filename", ""),
            "file_type": ef.get("file_type", ""),
            "url": ef.get("url", ""),
            "caption": ef.get("caption", ""),
            "linked_conflicts": linked_conflicts,
            "status": "linked" if linked_conflicts else "uncategorized",
        })

    return indexed


def statement_of_record(state: TicketState) -> dict:
    filename    = state.get("filename", "unknown")
    scan_id     = state.get("scan_id", "")
    driver_stmt = state.get("driver_statement") or {}
    evidence    = state.get("evidence_files") or []
    extraction  = state.get("extraction") or {}

    if not driver_stmt:
        logger.warning("[statement_of_record] file=%s — no driver statement, skipping", filename)
        log_agent_event(scan_id, AGENT_NAME, "skipped", {"reason": "no_driver_statement"})
        return {"statement_of_record": None}

    officer_account = _build_officer_account(extraction)
    violation_desc  = _fv(extraction, "Violation_Description__c")

    driver_account = {
        "location_when_stopped":  driver_stmt.get("location_when_stopped", ""),
        "action_at_time":         driver_stmt.get("action_at_time", ""),
        "weather_conditions":     driver_stmt.get("weather_conditions", ""),
        "road_signs_visible":     driver_stmt.get("road_signs_visible", ""),
        "your_speed":             driver_stmt.get("your_speed", ""),
        "officer_stated_violation": driver_stmt.get("officer_stated_violation", ""),
        "had_dashcam":            driver_stmt.get("had_dashcam", ""),
        "other_witnesses":        driver_stmt.get("other_witnesses", ""),
        "dispute_ticket_details": driver_stmt.get("dispute_ticket_details", ""),
        "source": "driver_form",
    }

    conflict_map   = _build_conflict_map(officer_account, driver_stmt, violation_desc)
    evidence_index = _build_evidence_index(evidence, conflict_map)

    sor = {
        "officer_account":  officer_account,
        "driver_account":   driver_account,
        "conflict_map":     conflict_map,
        "evidence_index":   evidence_index,
        "conflict_count":   len(conflict_map),
        "evidence_count":   len(evidence_index),
        "uncategorized_evidence": sum(1 for e in evidence_index if e["status"] == "uncategorized"),
    }

    logger.warning(
        "[statement_of_record] file=%s conflicts=%d evidence=%d uncategorized=%d",
        filename, sor["conflict_count"], sor["evidence_count"], sor["uncategorized_evidence"],
    )

    log_agent_event(scan_id, AGENT_NAME, "complete", {
        "conflict_count": sor["conflict_count"],
        "conflict_types": [c["conflict_type"] for c in conflict_map],
        "evidence_count": sor["evidence_count"],
        "uncategorized_evidence": sor["uncategorized_evidence"],
    })

    return {"statement_of_record": sor}
