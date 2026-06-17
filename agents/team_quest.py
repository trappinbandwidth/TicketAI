"""
Team Quest — attorney matching agent.
Matches driver + violation to the top 3 available CDL attorneys
by state/county using the local SQLite attorney database.

Runs as the final graph node so all extraction data is available.
"""
from __future__ import annotations
import logging

from app.services.attorney_matching import find_attorneys
from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "team_quest"


def team_quest(state: TicketState) -> dict:
    filename  = state.get("filename", "unknown")
    scan_id   = state.get("scan_id", "")
    extraction = state.get("extraction") or {}

    def fv(field: str) -> str:
        f = extraction.get(field)
        return (f.get("value", "") if isinstance(f, dict) else "") or ""

    ticket_state  = fv("Ticket_State__c")
    ticket_county = fv("Ticket_County__c")

    if not ticket_state:
        logger.warning("[team_quest] file=%s — no state, skipping attorney match", filename)
        log_agent_event(scan_id, AGENT_NAME, "skipped", {"reason": "no_state"})
        return {"attorney_matches": [], "no_attorney_flag": True}

    matches, no_attorney = find_attorneys(ticket_state, ticket_county)

    logger.warning(
        "[team_quest] file=%s state=%r county=%r → %d match(es) no_attorney=%s",
        filename, ticket_state, ticket_county, len(matches), no_attorney,
    )

    log_agent_event(scan_id, AGENT_NAME, "complete", {
        "state": ticket_state,
        "county": ticket_county,
        "matches_found": len(matches),
        "no_attorney": no_attorney,
        "match_types": [m.match_type for m in matches],
    })

    return {"attorney_matches": matches, "no_attorney_flag": no_attorney}
