"""
Operational Agents — continuous case management endpoints.

All endpoints are protected by the same x-api-key as the process endpoint.
Designed to be called by Cloud Scheduler (cron) or manually by the team.

  POST /operations/court-deadlines        Court Deadline Monitor  (cron: daily 8am)
  POST /operations/record-outcome/{id}    Outcome Recorder        (attorney portal trigger)
  GET  /operations/payment-alerts         Payment Alert           (cron: daily)
  GET  /operations/case-status            Case Status Tracker     (on demand)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.driver_concierge import notify_court_reminder, notify_driver

logger = logging.getLogger(__name__)
router = APIRouter()

_DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
    "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
]
_URGENCY_ORDER = {"CRITICAL": 0, "HIGH": 1, "STANDARD": 2, "LOW": 3}


def _check_auth(x_api_key: Optional[str]):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _parse_date(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        from dateutil import parser as du
        dt = du.parse(s, dayfirst=False)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _firestore_client():
    from app.services.firebase_service import _init, _firestore_client as _fc
    _init()
    if _fc is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _fc


# ── Agent 3: Court Deadline Monitor ──────────────────────────────────────────

@router.post("/operations/court-deadlines")
def run_court_deadline_monitor(
    send_driver_reminders: bool = True,
    x_api_key: Optional[str] = Header(None),
):
    """
    Scans all open tickets in Firestore for approaching court dates.
    Generates the case manager's daily priority work queue.
    Optionally sends court reminder notifications to drivers.

    CRITICAL  < 7 days  — attorney must act today
    HIGH      7–21 days — assign within 24 hours
    STANDARD  21–60 days
    LOW       > 60 days or no date
    """
    _check_auth(x_api_key)
    db = _firestore_client()
    now = datetime.now(timezone.utc)

    open_statuses = ["New", "Accepted", "AI Review"]
    buckets: dict[str, list] = {"CRITICAL": [], "HIGH": [], "STANDARD": [], "LOW": [], "NO_DATE": []}
    reminders_sent = 0

    try:
        for status in open_statuses:
            docs = db.collection("tickets").where("attorney_status", "==", status).stream()
            for d in docs:
                data = d.to_dict()
                ticket_id   = d.id
                court_date  = data.get("court_date") or ""
                driver_id   = data.get("driver_id") or ""
                driver_name = data.get("driver_full_name") or data.get("driver_name") or ""
                atty_name   = data.get("attorney_name") or ""
                violation   = data.get("violation_category") or ""
                state       = data.get("ticket_state") or ""
                urgency     = data.get("urgency_level") or "LOW"

                court_dt = _parse_date(court_date)
                days_until = (court_dt - now).days if court_dt else None

                card = {
                    "ticket_id": ticket_id,
                    "driver_id": driver_id,
                    "driver_name": driver_name,
                    "violation": violation,
                    "state": state,
                    "court_date": court_date,
                    "days_until_court": days_until,
                    "attorney_status": status,
                    "attorney_name": atty_name,
                    "urgency_level": urgency,
                }

                if days_until is None:
                    buckets["NO_DATE"].append(card)
                elif days_until < 0:
                    card["urgency_level"] = "CRITICAL"
                    buckets["CRITICAL"].append(card)
                elif days_until < 7:
                    card["urgency_level"] = "CRITICAL"
                    buckets["CRITICAL"].append(card)
                    if send_driver_reminders and driver_id:
                        notify_court_reminder(driver_id, ticket_id, court_date, days_until, atty_name)
                        reminders_sent += 1
                elif days_until < 21:
                    card["urgency_level"] = "HIGH"
                    buckets["HIGH"].append(card)
                    if send_driver_reminders and driver_id and days_until in (7, 14):
                        notify_court_reminder(driver_id, ticket_id, court_date, days_until, atty_name)
                        reminders_sent += 1
                elif days_until < 60:
                    buckets["STANDARD"].append(card)
                else:
                    buckets["LOW"].append(card)

        # Sort each bucket by soonest court date
        for bucket in buckets.values():
            bucket.sort(key=lambda t: t.get("days_until_court") if t.get("days_until_court") is not None else 9999)

        total = sum(len(v) for v in buckets.values())
        logger.warning(
            "[court_deadline_monitor] total=%d critical=%d high=%d reminders=%d",
            total, len(buckets["CRITICAL"]), len(buckets["HIGH"]), reminders_sent,
        )
        return {
            "run_at": now.isoformat(),
            "total_open": total,
            "critical_count": len(buckets["CRITICAL"]),
            "high_count": len(buckets["HIGH"]),
            "no_date_count": len(buckets["NO_DATE"]),
            "driver_reminders_sent": reminders_sent,
            "work_queue": buckets,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Agent 4: Outcome Recorder ─────────────────────────────────────────────────

class OutcomeRequest(BaseModel):
    outcome: str                        # won | dismissed | reduced | lost | transferred
    outcome_notes: Optional[str] = None
    final_charge: Optional[str] = None # if reduced, what was the final charge
    attorney_id: Optional[str] = None
    attorney_name: Optional[str] = None

_VALID_OUTCOMES = {"won", "dismissed", "reduced", "lost", "transferred"}

@router.post("/operations/record-outcome/{ticket_id}")
def record_outcome(
    ticket_id: str,
    body: OutcomeRequest,
    x_api_key: Optional[str] = Header(None),
):
    """
    Records the final case outcome after an attorney closes a case.
    Writes to both Firestore paths (tickets/ and drivers/.../tickets/).
    Triggers Driver Concierge to notify the driver.
    Feeds outcome data back for attorney performance tracking.
    """
    _check_auth(x_api_key)
    if body.outcome not in _VALID_OUTCOMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome '{body.outcome}'. Must be one of: {', '.join(sorted(_VALID_OUTCOMES))}",
        )

    db = _firestore_client()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        ref = db.collection("tickets").document(ticket_id)
        doc = ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")

        data = doc.to_dict()
        driver_id = data.get("driver_id") or ""
        atty_name = body.attorney_name or data.get("attorney_name") or ""

        outcome_payload = {
            "attorney_status": "Ticket Closed",
            "outcome": body.outcome,
            "outcome_notes": body.outcome_notes,
            "final_charge": body.final_charge,
            "closed_by_attorney_id": body.attorney_id,
            "closed_by_attorney_name": atty_name,
            "closed_at": SERVER_TIMESTAMP,
            "last_modified_date": SERVER_TIMESTAMP,
        }

        # Write to attorney portal path
        ref.update(outcome_payload)

        # Write to driver app path
        if driver_id:
            driver_ref = (
                db.collection("drivers").document(driver_id)
                  .collection("tickets").document(ticket_id)
            )
            if driver_ref.get().exists:
                driver_ref.update({
                    "status": "Ticket Closed",
                    "outcome": body.outcome,
                    "outcome_notes": body.outcome_notes,
                    "final_charge": body.final_charge,
                    "updated_at": SERVER_TIMESTAMP,
                })

            # Notify driver
            notify_driver(
                driver_id, ticket_id, "Ticket Closed",
                context={"outcome": _outcome_display(body.outcome, body.final_charge)},
            )

        logger.warning(
            "[outcome_recorder] ticket=%s outcome=%r attorney=%r driver=%s",
            ticket_id, body.outcome, atty_name, driver_id,
        )
        return {
            "success": True,
            "ticket_id": ticket_id,
            "outcome": body.outcome,
            "attorney_status": "Ticket Closed",
            "driver_notified": bool(driver_id),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _outcome_display(outcome: str, final_charge: Optional[str]) -> str:
    labels = {
        "won": "Case Won — violation dismissed",
        "dismissed": "Charges Dismissed",
        "reduced": f"Charge Reduced{f' to {final_charge}' if final_charge else ''}",
        "lost": "Case closed — violation upheld",
        "transferred": "Case transferred to another jurisdiction",
    }
    return labels.get(outcome, outcome.title())


# ── Agent 5: Payment Alert ────────────────────────────────────────────────────

@router.get("/operations/payment-alerts")
def get_payment_alerts(x_api_key: Optional[str] = Header(None)):
    """
    Scans all driver profiles for subscription issues:
      - lapsed / cancelled subscriptions
      - subscriptions expiring within 7 days
      - drivers with open cases but lapsed subscriptions (critical)

    Returns a prioritized alert list for the accounting team.
    """
    _check_auth(x_api_key)
    db = _firestore_client()
    now = datetime.now(timezone.utc)

    alerts: list[dict] = []
    expiring_soon: list[dict] = []
    critical: list[dict] = []  # open case + lapsed subscription

    try:
        drivers = db.collection("drivers").stream()

        for d in drivers:
            data = d.to_dict()
            driver_id   = d.id
            name        = data.get("full_name") or data.get("name") or driver_id
            email       = data.get("email") or ""
            sub_status  = (data.get("subscription_status") or "unknown").lower()
            plan        = data.get("plan") or ""
            end_raw     = data.get("subscription_end_date")

            days_left = None
            end_str   = ""
            if end_raw:
                try:
                    end_dt = end_raw
                    if hasattr(end_dt, "tzinfo") and end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    end_str = end_dt.strftime("%m/%d/%Y")
                    days_left = (end_dt - now).days
                except Exception:
                    pass

            card = {
                "driver_id": driver_id,
                "name": name,
                "email": email,
                "subscription_status": sub_status,
                "plan": plan,
                "expires": end_str,
                "days_left": days_left,
            }

            if sub_status in ("lapsed", "cancelled"):
                # Check for open cases — these are the most urgent
                open_cases = db.collection("tickets") \
                    .where("driver_id", "==", driver_id) \
                    .where("attorney_status", "in", ["New", "Accepted", "AI Review"]) \
                    .limit(1).stream()
                open_case_ids = [c.id for c in open_cases]
                if open_case_ids:
                    card["open_cases"] = open_case_ids
                    card["alert_type"] = "OPEN_CASE_LAPSED"
                    critical.append(card)
                else:
                    card["alert_type"] = "LAPSED"
                    alerts.append(card)

            elif sub_status == "active" and days_left is not None and 0 <= days_left <= 7:
                card["alert_type"] = "EXPIRING_SOON"
                expiring_soon.append(card)

        expiring_soon.sort(key=lambda c: c.get("days_left") or 999)
        alerts.sort(key=lambda c: c.get("name") or "")

        logger.warning(
            "[payment_alert] critical=%d lapsed=%d expiring=%d",
            len(critical), len(alerts), len(expiring_soon),
        )
        return {
            "run_at": now.isoformat(),
            "critical_count": len(critical),
            "lapsed_count": len(alerts),
            "expiring_soon_count": len(expiring_soon),
            "critical": critical,          # lapsed with open cases — top priority
            "lapsed": alerts,              # lapsed with no open cases
            "expiring_soon": expiring_soon,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Agent 6: Case Status Tracker ─────────────────────────────────────────────

@router.get("/operations/case-status")
def get_case_status(
    state: Optional[str] = None,
    urgency: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """
    Case manager's unified work queue — all active cases across all statuses,
    sorted by urgency then by court date.

    Optional filters:
      ?state=TX          filter by ticket state
      ?urgency=CRITICAL  filter by urgency level
    """
    _check_auth(x_api_key)
    db = _firestore_client()
    now = datetime.now(timezone.utc)

    active_statuses = ["AI Review", "New", "Accepted"]
    by_status: dict[str, list] = {s: [] for s in active_statuses}
    urgency_counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "STANDARD": 0, "LOW": 0}
    all_cases: list[dict] = []

    try:
        for status in active_statuses:
            query = db.collection("tickets").where("attorney_status", "==", status)
            if state:
                query = query.where("ticket_state", "==", state.upper())

            for d in query.stream():
                data = d.to_dict()
                case_urgency = data.get("urgency_level") or "LOW"

                if urgency and case_urgency != urgency.upper():
                    continue

                court_date = data.get("court_date") or ""
                court_dt   = _parse_date(court_date)
                days_until = (court_dt - now).days if court_dt else None

                sor        = data.get("statement_of_record") or {}
                driver_profile = data.get("driver_profile") or {}

                card = {
                    "ticket_id": d.id,
                    "driver_name": data.get("driver_full_name") or data.get("driver_name") or "",
                    "driver_id": data.get("driver_id") or "",
                    "violation": data.get("violation_category") or "",
                    "state": data.get("ticket_state") or "",
                    "county": data.get("ticket_county") or "",
                    "court_date": court_date,
                    "days_until_court": days_until,
                    "attorney_status": status,
                    "attorney_name": data.get("attorney_name") or "",
                    "urgency_level": case_urgency,
                    "urgency_reason": data.get("urgency_reason") or "",
                    "completeness_score": data.get("completeness_score"),
                    "missing_fields": data.get("missing_fields") or [],
                    "conflict_count": sor.get("conflict_count", 0),
                    "cdl_match": driver_profile.get("cdl_match", "unverified"),
                    "mvr_status": (data.get("mvr_request") or {}).get("status"),
                    "psp_status": (data.get("psp_request") or {}).get("status"),
                    "created_at": str(data.get("created_at") or ""),
                }

                by_status[status].append(card)
                all_cases.append(card)
                urgency_counts[case_urgency] = urgency_counts.get(case_urgency, 0) + 1

        # Sort each status bucket by urgency then court date
        for bucket in by_status.values():
            bucket.sort(key=lambda c: (
                _URGENCY_ORDER.get(c["urgency_level"], 3),
                c.get("days_until_court") if c.get("days_until_court") is not None else 9999,
            ))

        all_cases.sort(key=lambda c: (
            _URGENCY_ORDER.get(c["urgency_level"], 3),
            c.get("days_until_court") if c.get("days_until_court") is not None else 9999,
        ))

        needs_action = [
            c for c in all_cases
            if c["urgency_level"] in ("CRITICAL", "HIGH")
            or c["cdl_match"] == "mismatch"
            or (c["completeness_score"] is not None and c["completeness_score"] < 0.6)
        ]

        logger.warning(
            "[case_status_tracker] total=%d critical=%d high=%d needs_action=%d",
            len(all_cases), urgency_counts.get("CRITICAL", 0),
            urgency_counts.get("HIGH", 0), len(needs_action),
        )
        return {
            "run_at": now.isoformat(),
            "filters": {"state": state, "urgency": urgency},
            "total_active": len(all_cases),
            "urgency_breakdown": urgency_counts,
            "needs_action_count": len(needs_action),
            "needs_action": needs_action,
            "by_status": by_status,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
