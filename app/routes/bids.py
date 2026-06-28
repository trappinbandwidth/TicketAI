"""
Attorney Bid routes — per-case bid management + intelligence search.

Flow:
  1. POST /admin/cases/{id}/request-bids → opens 72-business-hour window
  2. POST /admin/cases/{id}/bids         → manually enter each attorney's response
  3. PUT  /admin/cases/{id}/bids/{bid}   → update bid details
  4. POST /admin/cases/{id}/bids/{bid}/select → award case to this bid
  5. GET  /admin/bids/search             → intelligence: past bids by state+county+violation

Bids are written to two places:
  cases/{case_id}/bids/{bid_id}   — fast per-case reads
  bids/{bid_id}                   — top-level for cross-case intelligence search
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_auth(x_api_key: Optional[str]) -> None:
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _db():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _ts(v) -> Optional[str]:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _serialize(data: dict) -> dict:
    return {k: (_ts(v) if (v is not None and (hasattr(v, "isoformat") or hasattr(v, "tzinfo"))) else v)
            for k, v in data.items()}


def _add_business_hours(start: datetime, hours: int) -> datetime:
    """Advance `start` by `hours` business hours (Mon–Fri, any time of day counts)."""
    current = start
    remaining = hours
    while remaining > 0:
        current += timedelta(hours=1)
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            remaining -= 1
    return current


# ── Request bids (open 72-business-hour window) ───────────────────────────────

class RequestBidsBody(BaseModel):
    requested_by: str
    note: Optional[str] = None
    override_deadline_hours: Optional[int] = None  # default 72


@router.post("/admin/cases/{case_id}/request-bids")
def request_bids(case_id: str, body: RequestBidsBody, x_api_key: Optional[str] = Header(None)):
    """Open the bid window for a case. Sets a 72-business-hour deadline."""
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        case_ref = db.collection("cases").document(case_id)
        case_doc = case_ref.get()
        if not case_doc.exists:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

        hours = body.override_deadline_hours or 72
        now = datetime.now(timezone.utc)
        deadline = _add_business_hours(now, hours)

        case_ref.update({
            "bid_status": "open",
            "bid_requested_at": SERVER_TIMESTAMP,
            "bid_deadline": deadline.isoformat(),
            "bid_requested_by": body.requested_by,
            "last_updated_by": body.requested_by,
            "last_updated_at": SERVER_TIMESTAMP,
        })

        # Log activity
        activity_id = str(uuid.uuid4())
        note = body.note or f"Bid process started — deadline {deadline.strftime('%a %b %d %I:%M %p UTC')} ({hours} business hours)"
        case_ref.collection("activity").document(activity_id).set({
            "type": "bid_requested",
            "note": note,
            "created_by": body.requested_by,
            "created_by_name": body.requested_by,
            "created_at": SERVER_TIMESTAMP,
        })

        logger.warning("[bids] bid window opened case=%s deadline=%s by=%s", case_id, deadline.isoformat(), body.requested_by)
        return {
            "success": True,
            "bid_deadline": deadline.isoformat(),
            "business_hours": hours,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── List bids for a case ──────────────────────────────────────────────────────

@router.get("/admin/cases/{case_id}/bids")
def list_bids(case_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        docs = db.collection("cases").document(case_id).collection("bids").stream()
        bids = []
        for d in docs:
            data = d.to_dict()
            bids.append({"bid_id": d.id, **_serialize(data)})
        bids.sort(key=lambda b: (b.get("fee_amount") or 9999999))
        return {"bids": bids, "total": len(bids)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Submit a bid (manually entered) ──────────────────────────────────────────

class SubmitBidBody(BaseModel):
    # Attorney info
    attorney_name: str
    attorney_firm: Optional[str] = None
    attorney_email: Optional[str] = None
    attorney_phone: Optional[str] = None
    attorney_bar_number: Optional[str] = None

    # Fee
    fee_amount: Optional[float] = None
    fee_structure: Optional[str] = "flat"       # flat | hourly | contingency
    fee_includes: Optional[str] = None          # what's covered (trial, appeals, etc.)
    fee_notes: Optional[str] = None

    # Timeline
    timeline_estimate: Optional[str] = None     # free text: "2 court dates, ~60 days"
    timeline_court_appearances: Optional[int] = None
    timeline_days_estimate: Optional[int] = None

    # Outcome projections
    outcome_confidence: Optional[str] = None    # high | medium | low
    outcome_best_case: Optional[str] = None
    outcome_likely: Optional[str] = None
    outcome_worst_case: Optional[str] = None

    # Experience
    local_court_experience: Optional[bool] = None
    local_court_notes: Optional[str] = None     # judges known, tendencies, etc.
    similar_cases_count: Optional[int] = None
    similar_cases_win_rate: Optional[float] = None   # 0–1

    notes: Optional[str] = None
    entered_by: str


@router.post("/admin/cases/{case_id}/bids")
def submit_bid(case_id: str, body: SubmitBidBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        case_ref = db.collection("cases").document(case_id)
        case_doc = case_ref.get()
        if not case_doc.exists:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
        case_data = case_doc.to_dict()

        bid_id = str(uuid.uuid4())

        bid_doc = {
            **body.model_dump(),
            "bid_id": bid_id,
            "case_id": case_id,
            "ticket_id": case_data.get("ticket_id"),
            # Denormalized for intelligence search
            "violation_category": case_data.get("violation"),
            "ticket_state": case_data.get("ticket_state"),
            "driver_name": case_data.get("driver_name"),
            "court_date": case_data.get("court_date"),
            "bid_status": "submitted",
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
            # Post-case (filled after resolution)
            "actual_outcome": None,
            "actual_outcome_notes": None,
            "attorney_performance_rating": None,
            "would_use_again": None,
        }

        # Write to per-case subcollection
        case_ref.collection("bids").document(bid_id).set(bid_doc)

        # Also write to top-level bids/ for cross-case intelligence search
        db.collection("bids").document(bid_id).set(bid_doc)

        logger.warning("[bids] bid added case=%s bid=%s attorney=%s", case_id, bid_id, body.attorney_name)
        return {"success": True, "bid_id": bid_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Update a bid ──────────────────────────────────────────────────────────────

class UpdateBidBody(BaseModel):
    attorney_name: Optional[str] = None
    attorney_firm: Optional[str] = None
    attorney_email: Optional[str] = None
    attorney_phone: Optional[str] = None
    fee_amount: Optional[float] = None
    fee_structure: Optional[str] = None
    fee_includes: Optional[str] = None
    fee_notes: Optional[str] = None
    timeline_estimate: Optional[str] = None
    timeline_court_appearances: Optional[int] = None
    timeline_days_estimate: Optional[int] = None
    outcome_confidence: Optional[str] = None
    outcome_best_case: Optional[str] = None
    outcome_likely: Optional[str] = None
    outcome_worst_case: Optional[str] = None
    local_court_experience: Optional[bool] = None
    local_court_notes: Optional[str] = None
    similar_cases_count: Optional[int] = None
    notes: Optional[str] = None
    # Post-case fields
    actual_outcome: Optional[str] = None
    actual_outcome_notes: Optional[str] = None
    attorney_performance_rating: Optional[int] = None
    would_use_again: Optional[bool] = None


@router.put("/admin/cases/{case_id}/bids/{bid_id}")
def update_bid(case_id: str, bid_id: str, body: UpdateBidBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
        updates["updated_at"] = SERVER_TIMESTAMP
        db.collection("cases").document(case_id).collection("bids").document(bid_id).update(updates)
        db.collection("bids").document(bid_id).update(updates)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Delete a bid ──────────────────────────────────────────────────────────────

@router.delete("/admin/cases/{case_id}/bids/{bid_id}")
def delete_bid(case_id: str, bid_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        db.collection("cases").document(case_id).collection("bids").document(bid_id).delete()
        db.collection("bids").document(bid_id).update({"bid_status": "removed"})
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Select a bid (award case) ─────────────────────────────────────────────────

class SelectBidBody(BaseModel):
    selected_by: str
    note: Optional[str] = None


@router.post("/admin/cases/{case_id}/bids/{bid_id}/select")
def select_bid(case_id: str, bid_id: str, body: SelectBidBody, x_api_key: Optional[str] = Header(None)):
    """
    Select a bid: marks bid as 'selected', updates case with attorney info,
    marks other bids 'rejected', and logs activity.
    """
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    try:
        case_ref = db.collection("cases").document(case_id)
        bid_ref = case_ref.collection("bids").document(bid_id)
        bid_doc = bid_ref.get()
        if not bid_doc.exists:
            raise HTTPException(status_code=404, detail=f"Bid {bid_id} not found.")
        bid_data = bid_doc.to_dict()

        # Mark selected bid
        bid_ref.update({"bid_status": "selected", "updated_at": SERVER_TIMESTAMP})
        db.collection("bids").document(bid_id).update({"bid_status": "selected", "updated_at": SERVER_TIMESTAMP})

        # Reject other bids
        other_bids = case_ref.collection("bids").stream()
        for b in other_bids:
            if b.id != bid_id and b.to_dict().get("bid_status") != "removed":
                b.reference.update({"bid_status": "rejected"})
                db.collection("bids").document(b.id).update({"bid_status": "rejected"})

        # Update case with selected attorney
        attorney_name = bid_data.get("attorney_name", "")
        attorney_phone = bid_data.get("attorney_phone", "")
        attorney_email = bid_data.get("attorney_email", "")
        fee_amount = bid_data.get("fee_amount")

        case_ref.update({
            "attorney_name": attorney_name,
            "attorney_phone": attorney_phone,
            "bid_status": "awarded",
            "bid_awarded_to": bid_id,
            "bid_awarded_at": SERVER_TIMESTAMP,
            "attorney_fee_amount": fee_amount,
            "last_updated_by": body.selected_by,
            "last_updated_at": SERVER_TIMESTAMP,
        })

        # Update linked ticket
        case_data = case_ref.get().to_dict() or {}
        if case_data.get("ticket_id"):
            db.collection("tickets").document(case_data["ticket_id"]).update({
                "attorney_name": attorney_name,
                "attorney_phone": attorney_phone,
                "attorney_email": attorney_email,
            })

        # Log activity
        activity_id = str(uuid.uuid4())
        note = body.note or f"Bid selected — {attorney_name} awarded the case. Fee: ${fee_amount or 'TBD'}"
        case_ref.collection("activity").document(activity_id).set({
            "type": "bid_awarded",
            "note": note,
            "created_by": body.selected_by,
            "created_by_name": body.selected_by,
            "created_at": SERVER_TIMESTAMP,
        })

        logger.warning("[bids] bid selected case=%s bid=%s attorney=%s", case_id, bid_id, attorney_name)
        return {"success": True, "attorney_name": attorney_name, "fee_amount": fee_amount}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Intelligence search ───────────────────────────────────────────────────────

@router.get("/admin/bids/search")
def search_bids(
    state: Optional[str] = None,
    county: Optional[str] = None,
    violation: Optional[str] = None,
    limit: int = 20,
    x_api_key: Optional[str] = Header(None),
):
    """
    Search past attorney bids for intelligence on future case assignment.
    Filter by state, county, and/or violation category.
    Returns bids with actual outcomes (post-case data) for informed decisions.
    """
    _check_auth(x_api_key)
    db = _db()
    try:
        query = db.collection("bids")

        if state:
            query = query.where("ticket_state", "==", state)

        docs = query.limit(200).stream()
        results = []
        for d in docs:
            data = d.to_dict()
            if data.get("bid_status") == "removed":
                continue
            # Additional filter: county (Firestore doesn't support multi-where on different fields easily)
            if county and data.get("ticket_county", "").lower() != county.lower():
                continue
            # Violation: substring match
            if violation:
                v = (data.get("violation_category") or "").lower()
                if violation.lower() not in v:
                    continue
            results.append({"bid_id": d.id, **_serialize(data)})

        # Sort: selected bids first (most useful), then by fee ascending
        status_order = {"selected": 0, "submitted": 1, "rejected": 2}
        results.sort(key=lambda b: (
            status_order.get(b.get("bid_status", ""), 9),
            b.get("fee_amount") or 9999999
        ))

        return {"bids": results[:limit], "total": len(results)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
