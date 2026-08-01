"""Captain ticket workspace.

This route composes existing ticket, case, document, marketplace, and portal
records into one staff operating view. Mutations are append-only work-log
events with explicit audience and delivery state; they never claim that an
external phone call or SMS happened without provider evidence.
"""
from __future__ import annotations

import os
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.routes._common import get_db, iso, require_staff
from app.services.staff_audit import write_staff_audit

router = APIRouter(tags=["captain-ticket-workspace"])


def _clean(data: dict) -> dict:
    return {key: iso(value) for key, value in (data or {}).items()}


def _items(query) -> list[dict]:
    rows = [{"id": snap.id, **_clean(snap.to_dict() or {})} for snap in query.stream()]
    rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return rows


def _find_case(db, ticket_id: str):
    matches = list(db.collection("cases").where("ticket_id", "==", ticket_id).limit(1).stream())
    return matches[0] if matches else None


def _recommendations(ticket: dict) -> dict:
    missing = ticket.get("missing_fields") or []
    driver = [
        "Review the Driver TIP Score evidence and resolve source conflicts before requesting recalculation.",
        "Keep MVR, PSP, medical certificate, and CDL documents current; challenge eligible inaccuracies through DataQs.",
        "Complete coaching actions tied to verified violations. Scores change only from governed evidence and rules.",
    ]
    carrier = [
        "Prioritize alerted CSA BASIC categories and the inspections producing the largest verified exposure.",
        "Use DataQs for factually incorrect inspection or crash records and retain supporting documents.",
        "Track corrective training, maintenance, and hiring controls; verify results against the next FMCSA snapshot.",
    ]
    if missing:
        driver.insert(0, f"Complete missing ticket evidence: {', '.join(str(value) for value in missing)}.")
    return {
        "driver": driver,
        "carrier": carrier,
        "disclaimer": (
            "TIP Score and FMCSA CSA are separate systems. Guidance is operational, "
            "not a promise of a score change or legal outcome."
        ),
    }


@router.get("/admin/tickets/{ticket_id}/workspace")
def get_ticket_workspace(ticket_id: str, authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = get_db()
    ticket_snap = db.collection("tickets").document(ticket_id).get()
    if not ticket_snap.exists:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket = _clean(ticket_snap.to_dict() or {})
    case_snap = _find_case(db, ticket_id)
    case = {"case_id": case_snap.id, **_clean(case_snap.to_dict() or {})} if case_snap else None
    activity = _items(case_snap.reference.collection("activity")) if case_snap else []
    bids = _items(case_snap.reference.collection("bids")) if case_snap else []
    documents = _items(ticket_snap.reference.collection("driver_documents"))
    requests = _items(db.collection("document_requests").where("ticket_id", "==", ticket_id))
    work_log = _items(ticket_snap.reference.collection("captain_work_log"))
    sms_configured = bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
    return {
        "ticket_id": ticket_id,
        "ticket": ticket,
        "case": case,
        "activity": activity,
        "bids": bids,
        "documents": documents,
        "document_requests": requests,
        "work_log": work_log,
        "communications": {
            "in_app": {"configured": True, "delivery": "immediate"},
            "sms": {
                "configured": sms_configured,
                "delivery": "provider-backed" if sms_configured else "unavailable",
                "message": (
                    "SMS provider is configured."
                    if sms_configured
                    else "SMS is not configured. Use in-app messaging or record a manual contact attempt."
                ),
            },
        },
        "recommendations": _recommendations(ticket),
    }


class WorkItemBody(BaseModel):
    kind: Literal["note", "document_task", "court_contact", "court_date_request", "communication"]
    text: str = Field(min_length=1, max_length=5000)
    audience: Literal["internal", "attorney", "driver"] = "internal"
    status: Literal["open", "attempted", "requested", "confirmed", "completed", "blocked"] = "open"
    channel: Optional[Literal["in_app", "phone", "email", "sms"]] = None
    requested_court_date: Optional[str] = None
    confirmed_court_date: Optional[str] = None


def _notify(db, ticket_id: str, ticket: dict, actor: dict, item_id: str, body: WorkItemBody) -> str:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    if body.audience == "internal":
        return "not_applicable"
    if body.channel == "sms":
        if not (os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")):
            return "provider_not_configured"
        # Provider credentials alone do not prove delivery. A dispatch worker can
        # consume this durable outbox record and attach a provider message id.
        db.collection("communication_outbox").document(item_id).set({
            "item_id": item_id, "ticket_id": ticket_id, "channel": "sms",
            "audience": body.audience, "message": body.text, "status": "queued",
            "created_by": actor.get("uid") or actor.get("email") or "staff",
            "created_at": SERVER_TIMESTAMP,
        })
        return "queued"
    if body.channel in {"phone", "email"}:
        return "manual_contact_recorded"
    if body.audience == "attorney":
        attorney_id = ticket.get("assigned_attorney_id") or ticket.get("attorney_id")
        if not attorney_id:
            return "recipient_unavailable"
        db.collection("attorney_notifications").document(attorney_id).collection("items").document(item_id).set({
            "notif_id": item_id, "type": "captain_message", "ticket_id": ticket_id,
            "title": "Message from Rig Resolve", "message": body.text,
            "read": False, "created_at": SERVER_TIMESTAMP,
        })
        return "delivered_in_app"
    driver_id = ticket.get("driver_id")
    if not driver_id:
        return "recipient_unavailable"
    db.collection("drivers").document(driver_id).collection("notifications").document(item_id).set({
        "notif_id": item_id, "type": "captain_message", "ticket_id": ticket_id,
        "title": "Update from Rig Resolve", "message": body.text,
        "read": False, "created_at": SERVER_TIMESTAMP,
    })
    return "delivered_in_app"


@router.post("/admin/tickets/{ticket_id}/work-items", status_code=201)
def create_work_item(
    ticket_id: str,
    body: WorkItemBody,
    authorization: Optional[str] = Header(None),
):
    actor = require_staff(authorization)
    db = get_db()
    ticket_ref = db.collection("tickets").document(ticket_id)
    ticket_snap = ticket_ref.get()
    if not ticket_snap.exists:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket = ticket_snap.to_dict() or {}
    if body.status == "confirmed" and body.kind == "court_date_request" and not body.confirmed_court_date:
        raise HTTPException(status_code=400, detail="A confirmed court-date request requires the confirmed date.")
    item_id = str(uuid.uuid4())
    delivery_status = _notify(db, ticket_id, ticket, actor, item_id, body)
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    payload = {
        "item_id": item_id,
        **body.model_dump(),
        "delivery_status": delivery_status,
        "created_by": actor.get("email") or actor.get("uid") or "staff",
        "created_at": SERVER_TIMESTAMP,
    }
    ticket_ref.collection("captain_work_log").document(item_id).set(payload)
    if body.kind == "document_task" and body.audience == "driver":
        db.collection("document_requests").document(item_id).set({
            "document_request_id": item_id,
            "ticket_id": ticket_id,
            "driver_id": ticket.get("driver_id"),
            "description": body.text,
            "status": "pending",
            "requested_by": actor.get("email") or actor.get("uid") or "staff",
            "requested_at": SERVER_TIMESTAMP,
            "created_at": SERVER_TIMESTAMP,
            "source": "captain_ticket_workspace",
        })
    if body.confirmed_court_date:
        ticket_ref.update({"court_date": body.confirmed_court_date, "last_modified_date": SERVER_TIMESTAMP})
    write_staff_audit(
        db, actor, "captain_work_item_created", "ticket", ticket_id,
        after={**body.model_dump(), "delivery_status": delivery_status},
        reason=body.text[:500],
    )
    return {"item_id": item_id, "delivery_status": delivery_status, "status": body.status}
