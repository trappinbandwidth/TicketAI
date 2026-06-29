"""
AE-08 — Attorney-facing bid routes.

Attorneys can self-submit bids on cases where the bid window is open.
These routes use Firebase Bearer token auth (not API key).

Flow:
  1. Staff opens bid window: POST /admin/cases/{id}/request-bids  (include attorney_ids list)
  2. Each attorney receives a bid_invitation notification
  3. Attorney clicks notification → /bid/{case_id} page in portal
  4. Attorney submits bid: POST /bids/submit
  5. Staff awards: POST /admin/cases/{id}/bids/{bid_id}/select
  6. Attorney notified of win/loss via attorney_notifications
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-bids"])


def _db():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _verify_token(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    try:
        return fb_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def _ts(v) -> Optional[str]:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _serialize(data: dict) -> dict:
    return {k: (_ts(v) if (v is not None and hasattr(v, "isoformat")) else v)
            for k, v in data.items()}


class AttorneyBidBody(BaseModel):
    case_id: str
    ticket_id: Optional[str] = None
    fee_amount: Optional[float] = None
    fee_structure: Optional[str] = "flat"       # flat | hourly | contingency
    fee_includes: Optional[str] = None
    timeline_estimate: Optional[str] = None
    outcome_confidence: Optional[str] = None    # high | medium | low
    outcome_likely: Optional[str] = None
    local_court_experience: Optional[bool] = None
    notes: Optional[str] = None


@router.post("/bids/submit")
def submit_bid(
    body: AttorneyBidBody,
    authorization: Optional[str] = Header(None),
):
    """Attorney self-submits a bid on an open case."""
    decoded = _verify_token(authorization)
    attorney_uid = decoded["uid"]
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    case_ref = db.collection("cases").document(body.case_id)
    case_doc = case_ref.get()
    if not case_doc.exists:
        raise HTTPException(status_code=404, detail=f"Case {body.case_id} not found.")

    case_data = case_doc.to_dict()
    if case_data.get("bid_status") != "open":
        raise HTTPException(status_code=400, detail="Bid window is not open for this case.")

    # Fetch attorney profile for name/firm
    atty_doc = db.collection("attorneys").document(attorney_uid).get()
    atty_data = atty_doc.to_dict() if atty_doc.exists else {}
    attorney_name = (
        atty_data.get("full_name")
        or atty_data.get("Name")
        or decoded.get("name", "")
        or "Attorney"
    )
    attorney_firm = atty_data.get("firm_name", "")
    attorney_email = atty_data.get("email") or decoded.get("email", "")
    attorney_phone = atty_data.get("phone", "")

    # Check if attorney already has a bid on this case
    existing = list(case_ref.collection("bids").where("attorney_uid", "==", attorney_uid).limit(1).stream())
    if existing:
        raise HTTPException(status_code=409, detail="You have already submitted a bid on this case.")

    bid_id = str(uuid.uuid4())
    bid_doc = {
        "bid_id": bid_id,
        "case_id": body.case_id,
        "ticket_id": body.ticket_id or case_data.get("ticket_id"),
        "attorney_uid": attorney_uid,
        "attorney_name": attorney_name,
        "attorney_firm": attorney_firm,
        "attorney_email": attorney_email,
        "attorney_phone": attorney_phone,
        # Fee
        "fee_amount": body.fee_amount,
        "fee_structure": body.fee_structure,
        "fee_includes": body.fee_includes,
        # Timeline
        "timeline_estimate": body.timeline_estimate,
        # Outcome
        "outcome_confidence": body.outcome_confidence,
        "outcome_likely": body.outcome_likely,
        # Experience
        "local_court_experience": body.local_court_experience,
        # Meta
        "notes": body.notes,
        "bid_status": "submitted",
        "entered_by": attorney_name,
        # Denormalized
        "violation_category": case_data.get("violation"),
        "ticket_state": case_data.get("ticket_state"),
        "court_date": case_data.get("court_date"),
        "driver_name": case_data.get("driver_name"),
        "created_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
        # Post-case
        "actual_outcome": None,
        "attorney_performance_rating": None,
    }

    case_ref.collection("bids").document(bid_id).set(bid_doc)
    db.collection("bids").document(bid_id).set(bid_doc)

    logger.info("[attorney_bids] bid submitted case=%s bid=%s attorney=%s uid=%s",
                body.case_id, bid_id, attorney_name, attorney_uid)
    return {"success": True, "bid_id": bid_id}


@router.get("/bids/my-bids")
def my_bids(authorization: Optional[str] = Header(None)):
    """Return all bids the calling attorney has submitted, newest first."""
    decoded = _verify_token(authorization)
    attorney_uid = decoded["uid"]
    db = _db()

    docs = db.collection("bids").where("attorney_uid", "==", attorney_uid).limit(50).stream()
    results = []
    for d in docs:
        data = d.to_dict()
        if data.get("bid_status") == "removed":
            continue
        results.append({"bid_id": d.id, **_serialize(data)})

    results.sort(key=lambda b: b.get("created_at") or "", reverse=True)
    return {"bids": results, "total": len(results)}


@router.get("/bids/case/{case_id}")
def get_case_for_bid(
    case_id: str,
    authorization: Optional[str] = Header(None),
):
    """Return case details + ticket info for the bid form page."""
    _verify_token(authorization)
    db = _db()

    case_doc = db.collection("cases").document(case_id).get()
    if not case_doc.exists:
        raise HTTPException(status_code=404, detail="Case not found.")

    case_data = case_doc.to_dict()
    ticket_id = case_data.get("ticket_id")
    ticket_data: dict = {}
    if ticket_id:
        t = db.collection("tickets").document(ticket_id).get()
        if t.exists:
            ticket_data = t.to_dict()

    return {
        "case": _serialize(case_data),
        "ticket": _serialize(ticket_data),
        "case_id": case_id,
    }
