"""
PII Match & Dedup — verifies driver identity against Firestore profile.

Compares the CDL number extracted from the ticket against the CDL number
stored on the driver's Firestore profile. Flags mismatches for attorney review —
a mismatch can indicate a data-entry error on the ticket, a CDL renewal, or
in rare cases a fraudulent filing.

Gracefully skips when driver_id is absent or Firestore is unavailable.
"""
from __future__ import annotations

import logging

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "pii_match"


def _fv(extraction: dict, field: str) -> str:
    f = extraction.get(field)
    if isinstance(f, dict):
        return (f.get("value") or "").strip().upper()
    return ""


def pii_match(state: TicketState) -> dict:
    filename   = state.get("filename", "unknown")
    scan_id    = state.get("scan_id", "")
    driver_id  = state.get("driver_id") or ""
    extraction = state.get("extraction") or {}

    if not driver_id:
        logger.warning("[pii_match] file=%s — no driver_id, skipping", filename)
        log_agent_event(scan_id, AGENT_NAME, "skipped", {"reason": "no_driver_id"})
        return {"driver_profile": None}

    extracted_cdl = _fv(extraction, "CDL_Number__c")

    try:
        import firebase_admin.firestore as fs
        db = fs.client()
        doc = db.collection("drivers").document(driver_id).get()

        if not doc.exists:
            logger.warning("[pii_match] file=%s driver_id=%s — no Firestore profile found", filename, driver_id)
            log_agent_event(scan_id, AGENT_NAME, "no_profile", {"driver_id": driver_id})
            return {"driver_profile": {"driver_id": driver_id, "status": "not_found"}}

        profile = doc.to_dict() or {}
        profile_cdl = (
            profile.get("cdl_number") or profile.get("CDL_Number__c") or ""
        ).strip().upper()

        if extracted_cdl and profile_cdl and extracted_cdl == profile_cdl:
            cdl_match = "match"
        elif extracted_cdl and profile_cdl:
            cdl_match = "mismatch"
        else:
            cdl_match = "unverified"

        result = {
            "driver_id": driver_id,
            "status": "found",
            "cdl_match": cdl_match,
            "profile_cdl": profile_cdl,
            "ticket_cdl": extracted_cdl,
            "driver_name_on_file": profile.get("full_name") or profile.get("name") or "",
        }

        if cdl_match == "mismatch":
            logger.warning(
                "[pii_match] CDL MISMATCH file=%s driver_id=%s ticket=%r profile=%r",
                filename, driver_id, extracted_cdl, profile_cdl,
            )
        else:
            logger.warning(
                "[pii_match] file=%s driver_id=%s cdl_match=%s", filename, driver_id, cdl_match,
            )

        log_agent_event(scan_id, AGENT_NAME, "complete", result)
        return {"driver_profile": result}

    except Exception as exc:
        logger.warning("[pii_match] Firestore lookup failed file=%s: %s", filename, exc)
        log_agent_event(scan_id, AGENT_NAME, "error", {"error": str(exc)})
        return {"driver_profile": {"driver_id": driver_id, "status": "error", "error": str(exc)}}
