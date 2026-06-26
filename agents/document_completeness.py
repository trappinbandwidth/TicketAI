"""
Document Completeness Checker — audits field-by-field extraction quality.

Runs after the Referee scores GREEN or YELLOW. Produces:
  - missing_fields: list of critical field keys Lone Ranger could not extract
  - completeness_score: 0.0–1.0 ratio of critical fields successfully extracted

Attorneys use this to know upfront what information they need to gather
manually before accepting a case.
"""
from __future__ import annotations

import logging

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "document_completeness"

_CRITICAL_FIELDS = [
    "Citation_Number__c",
    "Date_of_Ticket__c",
    "Court_Date__c",
    "Violation_Category__c",
    "Violation_Description__c",
    "Ticket_State__c",
    "Ticket_County__c",
    "Driver_Name__c",
    "CDL_Number__c",
    "Court_Location__c",
]


def _field_present(extraction: dict, field: str) -> bool:
    f = extraction.get(field)
    if isinstance(f, dict):
        return bool((f.get("value") or "").strip())
    return False


def document_completeness(state: TicketState) -> dict:
    filename   = state.get("filename", "unknown")
    scan_id    = state.get("scan_id", "")
    extraction = state.get("extraction") or {}

    missing = [f for f in _CRITICAL_FIELDS if not _field_present(extraction, f)]
    score   = round(1.0 - (len(missing) / len(_CRITICAL_FIELDS)), 2)

    logger.warning(
        "[document_completeness] file=%s score=%.2f missing=%d/%d %s",
        filename, score, len(missing), len(_CRITICAL_FIELDS), missing,
    )
    log_agent_event(scan_id, AGENT_NAME, "complete", {
        "completeness_score": score,
        "missing_count": len(missing),
        "missing_fields": missing,
    })
    return {
        "completeness_score": score,
        "missing_fields": missing,
    }
