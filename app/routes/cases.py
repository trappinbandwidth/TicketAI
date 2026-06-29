"""
Case management routes — admin assigns attorneys to tickets and tracks the
full lifecycle from New → Admin Assigned → Atty Contacted → Accepted → Active
→ Outcome Logged → Closed.

All endpoints require x-api-key header.
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

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_CASE_STATUSES = {
    "pending_approval", "active", "attorney_declined",
    "outcome_logged", "payout_sent", "closed", "rejected",
}

_TICKET_STATUS_MAP = {
    "pending_approval": "Admin Assigned",
    "active": "Accepted",
    "attorney_declined": "Atty Declined",
    "outcome_logged": "Outcome Logged",
    "payout_sent": "Payout Sent",
    "closed": "Closed",
    "rejected": "Rejected",
}


def _check_auth(x_api_key: Optional[str]):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


# ── Attorneys list (for assignment dropdown) ──────────────────────────────────

@router.get("/admin/attorneys/list")
def list_attorneys(x_api_key: Optional[str] = Header(None)):
    """Active attorneys for the case assignment dropdown."""
    _check_auth(x_api_key)
    db = _db()
    try:
        docs = db.collection("attorneys").where("status", "==", "active").stream()
        attorneys = []
        for d in docs:
            data = d.to_dict()
            attorneys.append({
                "attorney_id": d.id,
                "full_name": data.get("full_name", ""),
                "firm_name": data.get("firm_name", ""),
                "tier": data.get("tier", ""),
                "states_licensed": data.get("states_licensed", []),
                "counties_covered": data.get("counties_covered", []),
                "win_rate": data.get("win_rate"),
                "cases_active": data.get("cases_active", 0),
                "max_active_cases": data.get("max_active_cases", 999),
                "phone": data.get("phone", ""),
                "email": data.get("email", ""),
                "preferred_contact_method": data.get("preferred_contact_method", "phone"),
            })
        attorneys.sort(key=lambda a: (a.get("win_rate") or 0), reverse=True)
        return {"attorneys": attorneys, "total": len(attorneys)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Available tickets (New — awaiting attorney assignment) ────────────────────

@router.get("/admin/cases/available")
def get_available_tickets(x_api_key: Optional[str] = Header(None)):
    """Tickets in 'New' status that haven't been assigned to a case yet."""
    _check_auth(x_api_key)
    db = _db()
    try:
        # Get New tickets
        ticket_docs = db.collection("tickets").where("attorney_status", "==", "New").stream()
        tickets = []
        for d in ticket_docs:
            data = d.to_dict()
            tickets.append({
                "ticket_id": d.id,
                "driver_name": data.get("driver_full_name") or data.get("driver_name") or "",
                "driver_id": data.get("driver_id") or "",
                "violation_category": data.get("violation_category") or "",
                "violation_description": data.get("violation_description") or "",
                "ticket_state": data.get("ticket_state") or "",
                "ticket_county": data.get("ticket_county") or "",
                "court_date": data.get("court_date") or "",
                "date_of_ticket": data.get("date_of_ticket") or "",
                "citation_number": data.get("citation_number") or "",
                "urgency_level": data.get("urgency_level") or "LOW",
                "urgency_reason": data.get("urgency_reason") or "",
                "completeness_score": data.get("completeness_score"),
                "price_display": data.get("price_display") or "",
                "price_low": data.get("price_low"),
                "price_high": data.get("price_high"),
                "pass_status": data.get("pass_status") or "",
                "reviewed_by": data.get("reviewed_by") or "",
                "reviewed_at": str(data.get("reviewed_at") or ""),
                "created_at": str(data.get("created_at") or ""),
            })

        # Sort CRITICAL first, then by court date
        _urgency_order = {"CRITICAL": 0, "HIGH": 1, "STANDARD": 2, "LOW": 3}
        tickets.sort(key=lambda t: (
            _urgency_order.get(t["urgency_level"], 3),
            t.get("court_date") or "9999",
        ))
        return {"tickets": tickets, "total": len(tickets)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Cases list ────────────────────────────────────────────────────────────────

@router.get("/admin/cases")
def list_cases(
    status: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """List cases, optionally filtered by status."""
    _check_auth(x_api_key)
    db = _db()
    try:
        query = db.collection("cases")
        if status:
            query = query.where("status", "==", status)
        docs = query.stream()
        cases = []
        for d in docs:
            data = d.to_dict()
            cases.append({
                "case_id": d.id,
                **{k: str(v) if hasattr(v, 'tzinfo') else v for k, v in data.items()},
            })
        # Sort by created_at descending
        cases.sort(key=lambda c: c.get("created_at") or "", reverse=True)
        return {"cases": cases, "total": len(cases)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Create case (assign attorney) ─────────────────────────────────────────────

class CreateCaseBody(BaseModel):
    ticket_id: str
    attorney_id: str
    assigned_by: str
    contact_method: Optional[str] = "phone"
    note: Optional[str] = None


@router.post("/admin/cases")
def create_case(body: CreateCaseBody, x_api_key: Optional[str] = Header(None)):
    """
    Assign an attorney to a ticket. Creates a cases/ document and updates
    the ticket's attorney_status from 'New' to 'Admin Assigned'.
    """
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        # Validate ticket exists and is in New status
        ticket_ref = db.collection("tickets").document(body.ticket_id)
        ticket_doc = ticket_ref.get()
        if not ticket_doc.exists:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_id} not found.")
        ticket_data = ticket_doc.to_dict()
        if ticket_data.get("attorney_status") not in ("New",):
            raise HTTPException(
                status_code=400,
                detail=f"Ticket is {ticket_data.get('attorney_status')!r} — must be 'New' to assign.",
            )

        # Validate attorney exists
        atty_ref = db.collection("attorneys").document(body.attorney_id)
        atty_doc = atty_ref.get()
        if not atty_doc.exists:
            raise HTTPException(status_code=404, detail=f"Attorney {body.attorney_id} not found.")
        atty_data = atty_doc.to_dict()

        case_id = str(uuid.uuid4())
        atty_name = atty_data.get("full_name", "")
        atty_phone = atty_data.get("phone", "")
        atty_email = atty_data.get("email", "")

        # Create case document
        case_doc = {
            "ticket_id": body.ticket_id,
            "attorney_id": body.attorney_id,
            "assigned_by": body.assigned_by,
            "assigned_at": SERVER_TIMESTAMP,
            "status": "pending_approval",
            "contact_method": body.contact_method,
            "contacted_at": None,
            "attorney_response_at": None,
            "next_followup_date": None,
            "outcome": None,
            "outcome_notes": None,
            "outcome_state": None,
            "closed_at": None,
            "last_updated_by": body.assigned_by,
            "last_updated_at": SERVER_TIMESTAMP,
            "created_at": SERVER_TIMESTAMP,
            # Denormalized
            "attorney_name": atty_name,
            "attorney_phone": atty_phone,
            "driver_name": ticket_data.get("driver_full_name") or "",
            "violation": ticket_data.get("violation_category") or "",
            "ticket_state": ticket_data.get("ticket_state") or "",
            "court_date": ticket_data.get("court_date") or "",
        }
        db.collection("cases").document(case_id).set(case_doc)

        # Initial activity log entry
        activity_id = str(uuid.uuid4())
        db.collection("cases").document(case_id).collection("activity").document(activity_id).set({
            "type": "assigned",
            "note": body.note or f"Case created — {atty_name} assigned by {body.assigned_by}.",
            "old_status": "New",
            "new_status": "pending_approval",
            "created_by": body.assigned_by,
            "created_by_name": body.assigned_by,
            "created_at": SERVER_TIMESTAMP,
        })

        # Update ticket status
        ticket_ref.update({
            "attorney_status": "Admin Assigned",
            "attorney_name": atty_name,
            "attorney_phone": atty_phone,
            "attorney_email": atty_email,
            "case_id": case_id,
            "last_modified_date": SERVER_TIMESTAMP,
        })

        # Increment attorney active case count
        atty_ref.update({"cases_active": (atty_data.get("cases_active") or 0) + 1})

        logger.warning(
            "[cases] created case=%s ticket=%s attorney=%s assigned_by=%s",
            case_id, body.ticket_id, body.attorney_id, body.assigned_by,
        )
        return {
            "success": True,
            "case_id": case_id,
            "ticket_id": body.ticket_id,
            "attorney_name": atty_name,
            "attorney_status": "Admin Assigned",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Get case detail + activity log ───────────────────────────────────────────

@router.get("/admin/cases/{case_id}")
def get_case(case_id: str, x_api_key: Optional[str] = Header(None)):
    """Case detail including full activity log."""
    _check_auth(x_api_key)
    db = _db()
    try:
        case_ref = db.collection("cases").document(case_id)
        case_doc = case_ref.get()
        if not case_doc.exists:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

        case_data = case_doc.to_dict()

        # Load activity log
        activity_docs = case_ref.collection("activity").order_by("created_at").stream()
        activity = []
        for a in activity_docs:
            entry = a.to_dict()
            entry["activity_id"] = a.id
            # Serialize timestamps
            for k, v in entry.items():
                if hasattr(v, 'tzinfo') or hasattr(v, 'isoformat'):
                    entry[k] = str(v)
            activity.append(entry)

        # Load linked ticket
        ticket_data = {}
        if case_data.get("ticket_id"):
            t = db.collection("tickets").document(case_data["ticket_id"]).get()
            if t.exists:
                ticket_data = t.to_dict()
                for k, v in ticket_data.items():
                    if hasattr(v, 'tzinfo') or hasattr(v, 'isoformat'):
                        ticket_data[k] = str(v)

        # Serialize case timestamps
        for k, v in case_data.items():
            if hasattr(v, 'tzinfo') or hasattr(v, 'isoformat'):
                case_data[k] = str(v)

        return {
            "case_id": case_id,
            **case_data,
            "activity": activity,
            "ticket": ticket_data,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Log activity / status update ─────────────────────────────────────────────

class ActivityBody(BaseModel):
    type: str  # assigned | contacted | attorney_update | status_change | outcome_logged | payout_created | note_added
    note: str
    new_status: Optional[str] = None
    created_by: str
    created_by_name: Optional[str] = None


@router.post("/admin/cases/{case_id}/activity")
def log_activity(
    case_id: str,
    body: ActivityBody,
    x_api_key: Optional[str] = Header(None),
):
    """
    Log an activity entry on a case. Optionally updates case status and the
    linked ticket's attorney_status.
    """
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        case_ref = db.collection("cases").document(case_id)
        case_doc = case_ref.get()
        if not case_doc.exists:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

        case_data = case_doc.to_dict()
        old_status = case_data.get("status", "")

        activity_id = str(uuid.uuid4())
        activity_entry = {
            "type": body.type,
            "note": body.note,
            "old_status": old_status if body.new_status else None,
            "new_status": body.new_status,
            "created_by": body.created_by,
            "created_by_name": body.created_by_name or body.created_by,
            "created_at": SERVER_TIMESTAMP,
        }
        case_ref.collection("activity").document(activity_id).set(activity_entry)

        # Update case
        case_update: dict = {
            "last_updated_by": body.created_by,
            "last_updated_at": SERVER_TIMESTAMP,
        }
        if body.new_status:
            if body.new_status not in _VALID_CASE_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{body.new_status}'. Valid: {sorted(_VALID_CASE_STATUSES)}",
                )
            case_update["status"] = body.new_status
            if body.type == "contacted":
                case_update["contacted_at"] = SERVER_TIMESTAMP
            if body.new_status == "closed":
                case_update["closed_at"] = SERVER_TIMESTAMP

        case_ref.update(case_update)

        # Sync ticket attorney_status
        if body.new_status and case_data.get("ticket_id"):
            ticket_attorney_status = _TICKET_STATUS_MAP.get(body.new_status)
            if ticket_attorney_status:
                db.collection("tickets").document(case_data["ticket_id"]).update({
                    "attorney_status": ticket_attorney_status,
                    "last_modified_date": SERVER_TIMESTAMP,
                })

        logger.warning(
            "[cases] activity case=%s type=%s status=%s→%s by=%s",
            case_id, body.type, old_status, body.new_status, body.created_by,
        )
        return {
            "success": True,
            "case_id": case_id,
            "activity_id": activity_id,
            "new_status": body.new_status or old_status,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Direct assignment ("Thinking of You") ─────────────────────────────────────

class DirectAssignBody(BaseModel):
    ticket_id: str
    attorney_id: str
    assigned_by: str
    message: Optional[str] = None  # personal note to attorney


@router.post("/admin/direct-assign")
def direct_assign(body: DirectAssignBody, x_api_key: Optional[str] = Header(None)):
    """
    AP-09 — Direct assignment ("Thinking of You").
    Staff assigns a specific attorney without claim/bid flow.
    Sets direct_assignment=True; attorney portal shows 'Directly Assigned' badge.
    """
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        ticket_ref = db.collection("tickets").document(body.ticket_id)
        ticket_doc = ticket_ref.get()
        if not ticket_doc.exists:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_id} not found.")
        ticket_data = ticket_doc.to_dict()

        if ticket_data.get("attorney_status") not in ("New", "AI Review", "Admin Assigned"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot directly assign — status is '{ticket_data.get('attorney_status')}'.",
            )

        atty_ref = db.collection("attorneys").document(body.attorney_id)
        atty_doc = atty_ref.get()
        if not atty_doc.exists:
            raise HTTPException(status_code=404, detail=f"Attorney {body.attorney_id} not found.")
        atty_data = atty_doc.to_dict()

        case_id = str(uuid.uuid4())
        atty_name = atty_data.get("full_name", "")
        atty_phone = atty_data.get("phone", "")
        atty_email = atty_data.get("email", "")
        personal_msg = body.message or f"{body.assigned_by} has selected you for this case."

        db.collection("cases").document(case_id).set({
            "ticket_id": body.ticket_id, "attorney_id": body.attorney_id,
            "assigned_by": body.assigned_by, "assigned_at": SERVER_TIMESTAMP,
            "status": "active", "direct_assignment": True,
            "direct_assignment_message": personal_msg,
            "attorney_name": atty_name, "attorney_phone": atty_phone,
            "driver_name": ticket_data.get("driver_full_name") or "",
            "violation": ticket_data.get("violation_category") or "",
            "ticket_state": ticket_data.get("ticket_state") or "",
            "court_date": ticket_data.get("court_date") or "",
            "last_updated_by": body.assigned_by, "last_updated_at": SERVER_TIMESTAMP,
            "created_at": SERVER_TIMESTAMP,
        })

        ticket_ref.update({
            "attorney_status": "Accepted", "attorney_name": atty_name,
            "attorney_phone": atty_phone, "attorney_email": atty_email,
            "assigned_attorney_id": body.attorney_id, "direct_assignment": True,
            "case_id": case_id, "last_modified_date": SERVER_TIMESTAMP,
        })

        try:
            notif_id = str(uuid.uuid4())
            db.collection("attorney_notifications").document(body.attorney_id)\
              .collection("items").document(notif_id).set({
                "notif_id": notif_id, "type": "direct_assignment",
                "ticket_id": body.ticket_id, "title": "New Case — Directly Assigned to You",
                "body": personal_msg, "read": False, "created_at": SERVER_TIMESTAMP,
              })
            from app.services.notifications import send_sms, send_email
            if atty_phone:
                send_sms(atty_phone, f"Rig Resolve: {personal_msg} Log in: rigresolve-attorney.web.app")
            if atty_email:
                send_email(atty_email, "You've been selected for a new case",
                           f"<p>{personal_msg}</p><p><a href='https://rigresolve-attorney.web.app'>View case →</a></p>")
        except Exception as notif_exc:
            logger.warning("[direct_assign] notification failed: %s", notif_exc)

        logger.warning("[cases] direct_assign ticket=%s attorney=%s by=%s case=%s",
                       body.ticket_id, body.attorney_id, body.assigned_by, case_id)
        return {"success": True, "case_id": case_id, "ticket_id": body.ticket_id,
                "attorney_id": body.attorney_id, "attorney_name": atty_name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
