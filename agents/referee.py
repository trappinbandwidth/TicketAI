"""
Referee — confidence scoring and pass/fail routing agent.
Reads Lone Ranger's extraction, calibrates scores, assigns pass status.

Green  (avg ≥ 0.85, no critical field < 0.70) → zero human intervention
Yellow (avg ≥ 0.60, or any non-critical field low) → flag for review
Red    (avg < 0.60, or any critical field < 0.70) → human escalation
"""
from __future__ import annotations
import logging
import re

from app.services.queue_store import log_agent_event
from orchestrator.state import PassStatus, TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "referee"

CRITICAL_FIELDS = {
    "Court_Date__c",
    "Date_of_Ticket__c",
    "Citation_Number__c",
    "Violation_Category__c",
    "Drivers_License_Type__c",
}

# These states do not print Citation_Number__c on their tickets (per Book of Tickets).
# Missing citation number for these states is expected, not an extraction failure.
_NO_CITATION_STATES = {
    "Alabama", "Alaska", "California", "Connecticut", "Kentucky", "Maryland",
    "Massachusetts", "Minnesota", "Montana", "Nebraska", "Nevada", "New Mexico",
    "New York", "South Carolina", "Utah", "Vermont", "Virginia", "West Virginia",
}

# These states do not print Ticket_County__c on their tickets.
_NO_COUNTY_STATES = {"Colorado", "Virginia"}

GREEN_THRESHOLD = 0.85
YELLOW_THRESHOLD = 0.60
CRITICAL_FLOOR = 0.70

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")

_VALID_VIOLATION_CATEGORIES = {
    "Driver license violation",
    "Alcohol / Drug related violation",
    "Reckless Driving",
    "Speeding (15+)",
    "Cell Phone",
    "Failure to yield to emergency vehicle",
    "Following too close",
    "Careless Driving",
    "Lane Violation",
    "Failure to Obey Traffic Control Device",
    "Too Fast for Conditions",
    "Speeding (1-14)",
    "Seatbelt",
    "ELD/Logs",
    "Equipment/Maintenance",
    "Registration Violations",
    "Overweight/Overlength",
    "Parking",
}

# All forms a CDL license type might appear as on a ticket
_VALID_CDL_TYPES = {
    "CDL", "Non-CDL",
    "CDL-A", "CDL-B", "CDL-C",
    "Class A", "Class B", "Class C",
    "Class A CDL", "Class B CDL", "Class C CDL",
    "Commercial", "Commercial Driver License",
    "A", "B", "C",
}


def _calibrate_scores(data_fields: dict, effective_critical: set | None = None) -> dict[str, float]:
    """
    Cap Claude's self-reported confidence where extracted values fail
    format validation — prevents false-green outcomes.
    effective_critical: the set of critical fields that actually apply for this ticket's state.
    """
    if effective_critical is None:
        effective_critical = CRITICAL_FIELDS
    scores = {k: v["confidence_score"] for k, v in data_fields.items()}
    capped = []

    for field, meta in data_fields.items():
        value = meta.get("value", "")

        if field in ("Date_of_Ticket__c", "Court_Date__c"):
            if value and not _DATE_RE.match(value):
                scores[field] = min(scores[field], 0.50)
                capped.append(f"{field}=date_format")

        elif field == "Court_Phone_Number__c":
            if value and not _PHONE_RE.match(value):
                scores[field] = min(scores[field], 0.50)
                capped.append(f"{field}=phone_format")

        elif field == "Violation_Category__c":
            if value and value not in _VALID_VIOLATION_CATEGORIES:
                scores[field] = min(scores[field], 0.40)
                capped.append(f"{field}=unknown_category({value!r})")

        elif field == "Drivers_License_Type__c":
            if value and value not in _VALID_CDL_TYPES:
                scores[field] = min(scores[field], 0.30)
                capped.append(f"{field}=unknown_license_type({value!r})")

        if field in effective_critical and not value:
            scores[field] = 0.0
            capped.append(f"{field}=empty_critical")

    if capped:
        logger.warning("[referee] score_caps applied: %s", ", ".join(capped))

    return scores


def referee(state: TicketState) -> dict:
    filename = state.get("filename", "unknown")
    logger.warning("[referee] START file=%s", filename)

    extraction = state.get("extraction") or {}

    data_fields = {
        k: v for k, v in extraction.items()
        if isinstance(v, dict) and "confidence_score" in v
    }

    if not data_fields:
        logger.error("[referee] FAILED file=%s — no extractable fields in extraction output. "
                     "Likely cause: lone_ranger returned non-standard JSON. "
                     "Check prompt v%s output shape.", filename, state.get("prompt_version", "v1"))
        log_agent_event(state.get("scan_id", ""), AGENT_NAME, "error", {
            "error": "no_extractable_fields",
            "prompt_version": state.get("prompt_version", "v1"),
        })
        return {
            "pass_status": PassStatus.RED,
            "low_confidence_fields": [],
            "referee_notes": "No extractable fields found — check lone_ranger output shape.",
        }

    # Determine which critical fields actually apply for this doc type / state
    ticket_state = (data_fields.get("Ticket_State__c") or {}).get("value", "")
    file_type = (data_fields.get("file_type") or {})
    # file_type may be a plain string (top-level key, not an ExtractedField)
    if isinstance(file_type, dict):
        doc_type = file_type.get("value", "Ticket")
    else:
        doc_type = extraction.get("file_type", "Ticket") or "Ticket"

    effective_critical = set(CRITICAL_FIELDS)

    # Non-ticket/warning types don't have court dates — remove from critical set
    if doc_type not in ("Ticket", "Warning"):
        effective_critical.discard("Court_Date__c")
        logger.warning("[referee] file=%s doc_type=%r — Court_Date__c not required for this doc type", filename, doc_type)

    if ticket_state in _NO_CITATION_STATES:
        effective_critical.discard("Citation_Number__c")
        logger.warning("[referee] file=%s state=%r — Citation_Number__c not required for this state", filename, ticket_state)
    if ticket_state in _NO_COUNTY_STATES:
        logger.warning("[referee] file=%s state=%r — Ticket_County__c not required for this state", filename, ticket_state)

    scores = _calibrate_scores(data_fields, effective_critical=effective_critical)

    # Average only over fields that matter for this document:
    # - fields with a non-empty extracted value (they were found and scored)
    # - critical fields always count (empty critical = 0.0, which is correct)
    # Excluding empty optional fields prevents 30+ zero-confidence placeholder
    # fields from dragging a clean ticket extraction into RED.
    scored_fields = {
        k: s for k, s in scores.items()
        if (data_fields.get(k, {}).get("value", "").strip() or k in effective_critical)
    }
    avg_score = sum(scored_fields.values()) / len(scored_fields) if scored_fields else 0.0

    low_confidence = [k for k, s in scored_fields.items() if s < YELLOW_THRESHOLD]
    critical_failures = [k for k in effective_critical if scores.get(k, 0) < CRITICAL_FLOOR]

    if critical_failures:
        pass_status = PassStatus.RED
        notes = f"Critical field(s) below floor: {', '.join(critical_failures)}"
        logger.warning("[referee] RED file=%s avg=%.2f critical_failures=%s",
                       filename, avg_score, critical_failures)
    elif avg_score >= GREEN_THRESHOLD and not low_confidence:
        pass_status = PassStatus.GREEN
        notes = f"All fields high confidence. Avg score: {avg_score:.2f}"
        logger.warning("[referee] GREEN file=%s avg=%.2f", filename, avg_score)
    elif avg_score >= YELLOW_THRESHOLD:
        pass_status = PassStatus.YELLOW
        notes = f"Some fields need review. Avg: {avg_score:.2f}. Low: {', '.join(low_confidence) or 'none'}"
        logger.warning("[referee] YELLOW file=%s avg=%.2f low=%s", filename, avg_score, low_confidence)
    else:
        pass_status = PassStatus.RED
        notes = f"Overall confidence too low: {avg_score:.2f}"
        logger.warning("[referee] RED file=%s avg=%.2f (below threshold)", filename, avg_score)

    scan_id = state.get("scan_id", "")
    log_agent_event(scan_id, AGENT_NAME, "scored", {
        "pass_status": pass_status,
        "avg_score": round(avg_score, 3),
        "doc_type": doc_type,
        "low_confidence_fields": low_confidence,
        "critical_failures": critical_failures,
        "effective_critical": list(effective_critical),
        "scored_field_count": len(scored_fields),
        "total_field_count": len(scores),
        "field_scores": {k: round(v, 3) for k, v in scored_fields.items()},
        "notes": notes,
    })

    return {
        "pass_status": pass_status,
        "low_confidence_fields": low_confidence,
        "referee_notes": notes,
    }
