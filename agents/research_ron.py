"""
Research Ron — jurisdiction enrichment agent.
Reads state/county/violation from the extraction and packages
court system context, CDL-specific rules, and appearance requirements
into a structured jurisdiction_context dict for downstream use by
attorneys and the reviewer dashboard.

Phase 1: local data only (court_rulebook + CDL point map).
Phase 2 (pending S3): will cross-reference the 30K ticket corpus
  by state/county/violation for pattern-based defense context.
"""
from __future__ import annotations
import logging

from app.services.court_lookup import lookup_court
from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "research_ron"

# CDL-specific disqualification thresholds per FMCSA 49 CFR 383.51
_SERIOUS_VIOLATIONS = {
    "Speeding (15+)",
    "Reckless Driving",
    "Following too close",
    "Lane Violation",
    "Cell Phone",
    "Failure to yield to emergency vehicle",
}

_MAJOR_VIOLATIONS = {
    "Alcohol / Drug related violation",
    "Driver license violation",
}

_DQ_RULE = (
    "Two serious violations within 3 years = 60-day CDL disqualification. "
    "Three serious violations within 3 years = 120-day disqualification."
)

_MAJOR_DQ_RULE = (
    "Major violation = 1-year CDL disqualification (first offense). "
    "Disqualification is mandatory regardless of plea — even amended charges trigger it."
)


def _appearance_note(court_data: dict | None, violation: str, mandatory_val: str) -> str:
    if mandatory_val.lower() == "yes":
        return "Mandatory court appearance required per ticket."
    if court_data and court_data.get("appear_required"):
        return "State rules require CDL holder to appear for this violation type."
    if violation in _SERIOUS_VIOLATIONS or violation in _MAJOR_VIOLATIONS:
        return "Serious/major CDL violation — attorney strongly recommended; appearance likely required."
    return "Appearance may be optional for minor violations — confirm with court."


def research_ron(state: TicketState) -> dict:
    filename = state.get("filename", "unknown")
    scan_id = state.get("scan_id", "")
    extraction = state.get("extraction") or {}

    def fv(field: str) -> str:
        f = extraction.get(field)
        return (f.get("value", "") if isinstance(f, dict) else "") or ""

    ticket_state    = fv("Ticket_State__c")
    ticket_county   = fv("Ticket_County__c")
    violation       = fv("Violation_Category__c")
    mandatory_val   = fv("Mandatory_Appearance__c")
    school_zone     = fv("School_Zone__c")
    construction_zone = fv("Construction_Zone__c")
    court_date      = fv("Court_Date__c")
    citation_number = fv("Citation_Number__c")

    if not ticket_state:
        logger.warning("[research_ron] file=%s — no state extracted, skipping jurisdiction lookup", filename)
        log_agent_event(scan_id, AGENT_NAME, "skipped", {"reason": "no_state"})
        return {"jurisdiction_context": None}

    # Court system lookup
    court_data = lookup_court(ticket_state, ticket_county, violation)

    # Build CDL violation classification
    is_serious  = violation in _SERIOUS_VIOLATIONS
    is_major    = violation in _MAJOR_VIOLATIONS
    dq_rule     = _MAJOR_DQ_RULE if is_major else (_DQ_RULE if is_serious else None)

    # Zone modifier note
    zone_notes: list[str] = []
    if school_zone.lower() == "yes":
        zone_notes.append("School zone — many states double points and fines.")
    if construction_zone.lower() == "yes":
        zone_notes.append("Construction zone — enhanced penalties typically apply.")

    appearance_note = _appearance_note(court_data, violation, mandatory_val)

    # Attorney action timeline
    timeline_note = ""
    if court_date:
        timeline_note = f"Court date on file: {court_date}. Attorney should contact court at least 5–7 business days prior."
    elif citation_number:
        timeline_note = "No court date extracted — attorney should contact court immediately to confirm hearing date."
    else:
        timeline_note = "No court date or citation number — verify ticket details with driver."

    context = {
        "state": ticket_state,
        "county": ticket_county,
        "violation": violation,
        "is_serious_violation": is_serious,
        "is_major_violation": is_major,
        "disqualification_rule": dq_rule,
        "zone_notes": zone_notes,
        "appearance_note": appearance_note,
        "attorney_timeline": timeline_note,
        "court_system": court_data.get("court_system", "") if court_data else "",
        "state_portal": court_data.get("state_portal", "") if court_data else "",
        "online_payment_url": court_data.get("online_payment_url", "") if court_data else "",
        "state_notes": court_data.get("notes", "") if court_data else "",
        "county_court_name": (
            court_data["county_court"]["court_name"]
            if court_data and court_data.get("county_court") else ""
        ),
        "county_court_phone": (
            court_data["county_court"]["phone"]
            if court_data and court_data.get("county_court") else ""
        ),
        "county_court_address": (
            court_data["county_court"]["address"]
            if court_data and court_data.get("county_court") else ""
        ),
        "county_scheduling_url": (
            court_data["county_court"]["scheduling_url"]
            if court_data and court_data.get("county_court") else ""
        ),
    }

    logger.warning(
        "[research_ron] file=%s state=%r county=%r violation=%r serious=%s major=%s court_found=%s county_found=%s",
        filename, ticket_state, ticket_county, violation, is_serious, is_major,
        bool(court_data), bool(court_data and court_data.get("county_court")),
    )

    log_agent_event(scan_id, AGENT_NAME, "complete", {
        "state": ticket_state,
        "county": ticket_county,
        "violation": violation,
        "is_serious": is_serious,
        "is_major": is_major,
        "court_found": bool(court_data),
        "county_court_found": bool(court_data and court_data.get("county_court")),
        "zone_flags": zone_notes,
    })

    return {"jurisdiction_context": context}
