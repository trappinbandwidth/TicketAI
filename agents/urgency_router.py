"""
Urgency Router — calculates case priority from court date proximity.

Attorneys see urgency on the case card in the portal. CRITICAL cases surface
at the top and trigger immediate assignment notifications.

  CRITICAL  → court date in < 7 days (or already passed)
  HIGH      → 7–21 days
  STANDARD  → 21–60 days
  LOW       → > 60 days or no court date on file
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "urgency_router"

_DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
    "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
]


def _parse_court_date(date_str: str) -> Optional[datetime]:
    s = (date_str or "").strip()
    if not s:
        return None
    try:
        from dateutil import parser as du
        return du.parse(s, dayfirst=False)
    except Exception:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fv(extraction: dict, field: str) -> str:
    f = extraction.get(field)
    if isinstance(f, dict):
        return (f.get("value") or "").strip()
    return ""


def urgency_router(state: TicketState) -> dict:
    filename   = state.get("filename", "unknown")
    scan_id    = state.get("scan_id", "")
    extraction = state.get("extraction") or {}

    court_date_str = _fv(extraction, "Court_Date__c")
    court_dt = _parse_court_date(court_date_str)

    if not court_dt:
        logger.warning("[urgency_router] file=%s — no parseable court date → LOW", filename)
        log_agent_event(scan_id, AGENT_NAME, "complete", {
            "urgency_level": "LOW",
            "reason": "no_court_date",
        })
        return {
            "urgency_level": "LOW",
            "urgency_reason": "No court date on file — assign attorney once court date is confirmed.",
        }

    now = datetime.now(timezone.utc)
    if court_dt.tzinfo is None:
        court_dt = court_dt.replace(tzinfo=timezone.utc)

    days_until = (court_dt - now).days

    if days_until < 0:
        level  = "CRITICAL"
        reason = (
            f"Court date {court_date_str} has PASSED ({abs(days_until)} day(s) ago). "
            "Immediate attorney review required."
        )
    elif days_until < 7:
        level  = "CRITICAL"
        reason = (
            f"Court date {court_date_str} is {days_until} day(s) away. "
            "Attorney must be assigned immediately."
        )
    elif days_until < 21:
        level  = "HIGH"
        reason = (
            f"Court date {court_date_str} is {days_until} days away. "
            "Assign attorney within 24 hours."
        )
    elif days_until < 60:
        level  = "STANDARD"
        reason = f"Court date {court_date_str} is {days_until} days away. Normal queue."
    else:
        level  = "LOW"
        reason = f"Court date {court_date_str} is {days_until} days away. No immediate action needed."

    logger.warning(
        "[urgency_router] file=%s court_date=%r days=%d → %s",
        filename, court_date_str, days_until, level,
    )
    log_agent_event(scan_id, AGENT_NAME, "complete", {
        "urgency_level": level,
        "court_date": court_date_str,
        "days_until_court": days_until,
    })
    return {
        "urgency_level": level,
        "urgency_reason": reason,
    }
