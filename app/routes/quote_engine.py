"""
Quote-and-assignment engine routes (Attorney Dashboard Eng Spec v2, §5).

Two auth models (see _common.py):
  - Attorney-facing routes: Firebase Bearer token (each attorney has their own account).
  - Admin/AAM routes: x-api-key, actor passed explicitly in the body — the admin
    console (frontend-qa) has no per-staff Firebase login, just a reviewer-name picker.
Thin layer over app/services/case_lifecycle.py.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.routes._common import get_db as _db, verify_token as _verify, require_api_key
from app.services import case_lifecycle as cl

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quote-engine"])


def _bad(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ── AAM / staff (admin console — x-api-key) ──────────────────────────────────
@router.get("/admin/quote-requests")
def list_quote_requests(status: Optional[str] = None, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    return {"requests": cl.list_quote_requests(_db(), status)}


@router.get("/admin/assignment-offers/pending-finalization")
def pending_finalization(x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    return {"broadcasts": cl.list_broadcasts_pending_finalization(_db())}


class OpenQuoteRequestBody(BaseModel):
    initiated_by: str


@router.post("/admin/quote-requests/{ticket_id}")
def open_quote_request(ticket_id: str, body: OpenQuoteRequestBody, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    try:
        return cl.open_quote_request(db, ticket_id, cl.actor("staff", body.initiated_by))
    except ValueError as e:
        raise _bad(e)


@router.get("/admin/quote-requests/{request_id}/review")
def quote_review(request_id: str, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    try:
        return cl.review_payload(db, request_id)
    except ValueError as e:
        raise _bad(e)


class AssignBody(BaseModel):
    selected_attorney_ids: list[str]
    assigned_by: str


@router.post("/admin/quote-requests/{request_id}/assign")
def assign(request_id: str, body: AssignBody, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    if not body.selected_attorney_ids:
        raise HTTPException(status_code=400, detail="selected_attorney_ids is required.")
    db = _db()
    try:
        return cl.send_assignment_offers(db, request_id, body.selected_attorney_ids,
                                         cl.actor("staff", body.assigned_by))
    except ValueError as e:
        raise _bad(e)


class FinalizeBody(BaseModel):
    selected_attorney_id: str
    decided_by: str


@router.post("/admin/assignment-offers/{broadcast_group_id}/finalize")
def finalize(broadcast_group_id: str, body: FinalizeBody, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    try:
        return cl.finalize_assignment(db, broadcast_group_id, body.selected_attorney_id,
                                      cl.actor("staff", body.decided_by))
    except ValueError as e:
        raise _bad(e)


@router.get("/admin/decline-reasons")
def get_decline_reasons(x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    return {"reasons": cl.get_decline_reasons(_db())}


class DeclineReasonUpsert(BaseModel):
    code: str
    label: str
    description: Optional[str] = None
    active: bool = True


@router.put("/admin/decline-reasons")
def put_decline_reason(body: DeclineReasonUpsert, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    db.collection("decline_reasons").document(body.code).set({
        "code": body.code, "label": body.label,
        "description": body.description or body.label, "active": body.active,
    }, merge=True)
    return {"ok": True, "code": body.code}


# ── Attorney-facing ─────────────────────────────────────────────────────────
@router.get("/decline-reasons")
def attorney_decline_reasons(authorization: Optional[str] = Header(None)):
    """Active decline reasons for the attorney's decline picker (any authed user)."""
    _verify(authorization)
    return {"reasons": [r for r in cl.get_decline_reasons(_db()) if r.get("active", True)]}


@router.get("/first-view")
def first_view(authorization: Optional[str] = Header(None)):
    decoded = _verify(authorization)
    return {"cases": cl.first_view_for_attorney(_db(), decoded["uid"])}


@router.get("/first-view/{ticket_id}/case")
def first_view_case(ticket_id: str, authorization: Optional[str] = Header(None)):
    """
    Charges / violation / ticket info for the quote decision — PII-safe. The attorney
    reviews the merits here; driver identity and contact are never exposed (anti-
    disintermediation). Only visible to attorneys invited to quote (or already on the case).
    """
    decoded = _verify(authorization)
    uid = decoded["uid"]
    db = _db()
    tsnap = db.collection("tickets").document(ticket_id).get()
    if not tsnap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    t = tsnap.to_dict()
    rid = t.get("quote_request_id")
    invited = False
    if rid:
        req = db.collection("case_quote_requests").document(rid).get()
        invited = req.exists and uid in (req.to_dict().get("attorneys_notified") or [])
    owns = uid in (t.get("assigned_attorney_id"), t.get("claimed_by"))
    if not (invited or owns):
        raise HTTPException(status_code=403, detail="Not authorized to view this case.")
    return {"ticket_id": ticket_id, "charges": cl.charges_view(t)}


class QuoteBody(BaseModel):
    fee_no_trial: float
    fee_trial: Optional[float] = None
    notes: Optional[str] = None


@router.post("/first-view/{ticket_id}/quote")
def submit_quote(ticket_id: str, body: QuoteBody, authorization: Optional[str] = Header(None)):
    decoded = _verify(authorization)
    db = _db()
    tsnap = db.collection("tickets").document(ticket_id).get()
    if not tsnap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    request_id = tsnap.to_dict().get("quote_request_id")
    if not request_id:
        raise HTTPException(status_code=409, detail="No open quote request for this case.")
    try:
        qid = cl.submit_quote(db, request_id, decoded["uid"],
                              body.fee_no_trial, body.fee_trial, body.notes)
        return {"ok": True, "quote_id": qid}
    except ValueError as e:
        raise _bad(e)


@router.get("/assignment-offers")
def my_offers(authorization: Optional[str] = Header(None)):
    decoded = _verify(authorization)
    return {"offers": cl.list_pending_offers_for_attorney(_db(), decoded["uid"])}


@router.post("/assignment-offers/{offer_id}/accept")
def accept(offer_id: str, authorization: Optional[str] = Header(None)):
    decoded = _verify(authorization)
    try:
        return cl.accept_offer(_db(), offer_id, decoded["uid"])
    except ValueError as e:
        raise _bad(e)


class DeclineBody(BaseModel):
    reason_code: str
    notes: Optional[str] = None


@router.post("/assignment-offers/{offer_id}/decline")
def decline(offer_id: str, body: DeclineBody, authorization: Optional[str] = Header(None)):
    decoded = _verify(authorization)
    db = _db()
    if not cl.valid_decline_code(db, body.reason_code):
        raise HTTPException(status_code=400, detail=f"Unknown decline reason '{body.reason_code}'.")
    if body.reason_code == "other" and not (body.notes or "").strip():
        raise HTTPException(status_code=400, detail="Notes are required when reason is 'other'.")
    try:
        return cl.decline_offer(db, offer_id, decoded["uid"], body.reason_code, body.notes)
    except ValueError as e:
        raise _bad(e)
