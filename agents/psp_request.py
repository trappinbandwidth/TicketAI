"""
PSP Request — queues a Pre-employment Screening Program (PSP) report pull.

PSP is an FMCSA service (49 CFR Part 391) that provides:
  - 5 years of crash history from the MCMIS database
  - 3 years of inspection and violation history

This is the primary document CDL defense attorneys use to understand a
driver's prior federal record and build a mitigation argument.

Consent requirement: the driver must consent under 49 CFR 391.23 before
an employer or third party can access PSP. Rig Resolve collects consent
during driver enrollment; the scan_id ties back to that record.

Production path: enqueues a Cloud Task that calls the FMCSA PSP API and
writes the resulting report to Firestore once available.

Currently: prepares and records the request metadata; status = "pending".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "psp_request"


def _fv(extraction: dict, field: str) -> str:
    f = extraction.get(field)
    if isinstance(f, dict):
        return (f.get("value") or "").strip()
    return ""


def psp_request(state: TicketState) -> dict:
    filename    = state.get("filename", "unknown")
    scan_id     = state.get("scan_id", "")
    driver_id   = state.get("driver_id") or ""
    extraction  = state.get("extraction") or {}

    cdl_number  = _fv(extraction, "CDL_Number__c")
    driver_name = state.get("driver_name") or _fv(extraction, "Driver_Name__c")
    driver_dob  = _fv(extraction, "Driver_DOB__c")

    if not cdl_number:
        logger.warning("[psp_request] file=%s — no CDL number extracted, skipping", filename)
        log_agent_event(scan_id, AGENT_NAME, "skipped", {"reason": "no_cdl_number"})
        return {"psp_request": None}

    request_data = {
        "status": "pending",
        "driver_id": driver_id,
        "driver_name": driver_name,
        "cdl_number": cdl_number,
        "driver_dob": driver_dob,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "scan_id": scan_id,
        "report_type": "PSP",
        "fmcsa_dataset": "MCMIS",
        "covers": {
            "crash_history_years": 5,
            "inspection_violation_years": 3,
        },
        "consent_required": True,
        "note": "Requires driver consent per 49 CFR 391.23. Production: enqueue FMCSA PSP API call via Cloud Tasks.",
    }

    logger.warning(
        "[psp_request] QUEUED file=%s driver=%r cdl=%r dob=%r",
        filename, driver_name, cdl_number, driver_dob,
    )
    log_agent_event(scan_id, AGENT_NAME, "queued", {
        "cdl_number": cdl_number,
        "driver_dob": driver_dob,
    })
    return {"psp_request": request_data}
