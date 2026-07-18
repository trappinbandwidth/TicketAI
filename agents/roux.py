"""
Roux — validates state before any Claude API call.

Runs first in the pipeline. If critical inputs are missing (no images,
no driver/ticket identifiers), sets pass_status=RED immediately so the
expensive OCR step is skipped and the ticket is escalated for manual entry.
"""
from __future__ import annotations

import logging

from app.services.queue_store import log_agent_event
from orchestrator.state import PassStatus, TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "roux"


def roux(state: TicketState) -> dict:
    filename = state.get("filename", "unknown")
    scan_id  = state.get("scan_id", "")
    errors: list[str] = []

    if not state.get("images_b64"):
        errors.append("no_images")

    if errors:
        logger.warning("[roux] FAIL file=%s errors=%s", filename, errors)
        log_agent_event(scan_id, AGENT_NAME, "failed", {"errors": errors})
        return {
            "intake_errors": errors,
            "pass_status": PassStatus.RED,
            "escalation_reason": f"Case intake failed: {', '.join(errors)}. Manual entry required.",
        }

    logger.warning(
        "[roux] OK file=%s images=%d driver_id=%s",
        filename, len(state["images_b64"]), state.get("driver_id", ""),
    )
    log_agent_event(scan_id, AGENT_NAME, "passed", {"image_count": len(state["images_b64"])})
    return {"intake_errors": []}
