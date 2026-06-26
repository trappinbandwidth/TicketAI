"""
MVR Request — queues a Motor Vehicle Record pull for the driver's CDL state.

MVR reports show the driver's full state driving history: prior violations,
suspensions, revocations, and points. Attorneys need this before accepting
any CDL defense case to assess risk and prior record.

Production path: sends a task to Cloud Tasks which calls the state DMV API
(or an MVR vendor such as Driving Record Inc / Verisk / iiX) and writes the
result back to Firestore once available. The attorney portal will show
"MVR Requested" until the result arrives.

Currently: prepares and records the request metadata; status = "pending".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "mvr_request"


def _fv(extraction: dict, field: str) -> str:
    f = extraction.get(field)
    if isinstance(f, dict):
        return (f.get("value") or "").strip()
    return ""


def mvr_request(state: TicketState) -> dict:
    filename     = state.get("filename", "unknown")
    scan_id      = state.get("scan_id", "")
    driver_id    = state.get("driver_id") or ""
    extraction   = state.get("extraction") or {}

    cdl_number   = _fv(extraction, "CDL_Number__c")
    driver_name  = state.get("driver_name") or _fv(extraction, "Driver_Name__c")
    ticket_state = _fv(extraction, "Ticket_State__c")

    if not cdl_number or not ticket_state:
        logger.warning(
            "[mvr_request] file=%s — missing CDL=%r or state=%r, skipping",
            filename, bool(cdl_number), bool(ticket_state),
        )
        log_agent_event(scan_id, AGENT_NAME, "skipped", {
            "reason": "missing_cdl_or_state",
            "cdl_present": bool(cdl_number),
            "state_present": bool(ticket_state),
        })
        return {"mvr_request": None}

    request_data = {
        "status": "pending",
        "driver_id": driver_id,
        "driver_name": driver_name,
        "cdl_number": cdl_number,
        "cdl_state": ticket_state,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "scan_id": scan_id,
        "note": "Pending MVR pull from state DMV. Production: enqueue via Cloud Tasks.",
    }

    logger.warning(
        "[mvr_request] QUEUED file=%s driver=%r cdl=%r state=%r",
        filename, driver_name, cdl_number, ticket_state,
    )
    log_agent_event(scan_id, AGENT_NAME, "queued", {
        "cdl_number": cdl_number,
        "cdl_state": ticket_state,
    })
    return {"mvr_request": request_data}
