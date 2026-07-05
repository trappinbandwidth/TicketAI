"""
Attorney cases + claim lifecycle — the reconciliation backend that lets the
attorney portal move off the legacy Flask service.

Firebase Bearer token auth. Attorney-facing routes are scoped to the caller;
staff/AM routes additionally require a staff-level role claim.

Assignment model (3 paths, gated by Performance Level):
  1. AM direct-assign         → /admin/direct-assign (in cases.py)
  2. Attorney claim           → /attorney/cases/{id}/claim
       • Platinum/Diamond claim WITHOUT approval (auto-accepted)
       • everyone else: claim is pending until an AM approves
  3. Bidding                  → /bids/* (attorney_bids.py)

  GET  /attorney/cases/available        Open cases an attorney can claim
  GET  /attorney/cases/mine             The caller's assigned/claimed/closed cases
  GET  /attorney/cases/{id}             Case detail (ownership- or availability-scoped)
  GET  /attorney/cases/{id}/activity    Activity/chat feed
  POST /attorney/cases/{id}/activity    Append an activity update
  POST /attorney/cases/{id}/claim       Claim a case (auto-accept if level qualifies)
  GET  /me                              Current user (token + attorney doc)
  GET  /notifications                   Caller's attorney_notifications

  GET  /admin/claims/pending            Claims awaiting AM approval (staff)
  POST /admin/cases/{id}/approve-claim  Approve a pending claim (staff)
  POST /admin/cases/{id}/reject-claim   Reject a pending claim (staff)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.routes._common import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-cases"])

# Levels that may claim without AM approval (attorney_levels.md ladder: Platinum+).
AUTO_APPROVE_LEVELS = {"platinum", "diamond"}

_AVAILABLE_STATUS = "New"
_ACCEPTED_STATUS = "Accepted"
# A case is "closed" (for the My Cases active/closed filter) once it reaches any of
# the v2 terminal statuses or the legacy "Ticket Closed".
_CLOSED_STATUSES = {"Ticket Closed", "Outcome Logged", "Payout Requested", "Payout Sent", "Closed"}


def _db():
    from app.services.firebase_service import _init, _firestore_client
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


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _card(doc_id: str, d: dict) -> dict:
    """A compact case card shared by list endpoints. Driver name is masked to
    'First L.' — attorneys never see full driver identity/contact (anti-disintermediation)."""
    from app.services.case_lifecycle import mask_driver_name
    return {
        "ticket_id": doc_id,
        "driver_name": mask_driver_name(d.get("driver_full_name") or d.get("driver_name")),
        "violation": d.get("violation_category") or "",
        "violation_description": d.get("violation_description") or "",
        "state": d.get("ticket_state") or "",
        "county": d.get("ticket_county") or "",
        "court_date": d.get("court_date") or "",
        "attorney_status": d.get("attorney_status"),
        "claim_status": d.get("claim_status"),
        "origin": d.get("origin") or "rr_pipeline",
        "urgency_level": d.get("urgency_level") or "LOW",
        "price_display": d.get("price_display"),
        "created_at": _iso(d.get("created_at")),
    }


# ── Available cases ───────────────────────────────────────────────────────────
@router.get("/attorney/cases/available")
def available_cases(
    state: Optional[str] = None,
    limit: int = 100,
    authorization: Optional[str] = Header(None),
):
    """Open cases an attorney can claim — New, not already claimed-pending."""
    _verify_token(authorization)
    db = _db()
    q = db.collection("tickets").where("attorney_status", "==", _AVAILABLE_STATUS)
    if state:
        q = q.where("ticket_state", "==", state.upper())
    cases = []
    for d in q.limit(limit).stream():
        data = d.to_dict()
        if data.get("claim_status") == "pending":
            continue  # already claimed by someone, awaiting approval
        cases.append(_card(d.id, data))
    cases.sort(key=lambda c: c.get("court_date") or "")
    return {"cases": cases, "count": len(cases)}


# ── My cases ──────────────────────────────────────────────────────────────────
@router.get("/attorney/cases/mine")
def my_cases(status: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """
    Cases belonging to the caller: assigned, claimed (pending), or closed by them.
    Optional ?status=active|closed filter.
    """
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()

    seen: dict[str, dict] = {}
    for field in ("assigned_attorney_id", "claimed_by", "closed_by_attorney_id"):
        for d in db.collection("tickets").where(field, "==", uid).stream():
            seen.setdefault(d.id, d.to_dict())

    cards = []
    for tid, data in seen.items():
        st = data.get("attorney_status")
        is_closed = st in _CLOSED_STATUSES
        if status == "active" and is_closed:
            continue
        if status == "closed" and not is_closed:
            continue
        cards.append(_card(tid, data))
    cards.sort(key=lambda c: c.get("court_date") or "")
    return {"cases": cards, "count": len(cards)}


# ── Case detail ───────────────────────────────────────────────────────────────
@router.get("/attorney/cases/{ticket_id}")
def case_detail(ticket_id: str, authorization: Optional[str] = Header(None)):
    """
    Full case detail. Visible if the case is available (New) or belongs to the
    caller (assigned / claimed / closed by them).
    """
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    snap = db.collection("tickets").document(ticket_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = snap.to_dict()

    owns = uid in (
        data.get("assigned_attorney_id"),
        data.get("claimed_by"),
        data.get("closed_by_attorney_id"),
    )
    if not owns and data.get("attorney_status") != _AVAILABLE_STATUS:
        raise HTTPException(status_code=403, detail="Not authorized to view this case.")

    # Strip all driver PII before returning to the attorney — masked display name only.
    from app.services.case_lifecycle import strip_driver_pii
    safe = strip_driver_pii(data)
    out = {k: _iso(v) for k, v in safe.items()}
    out["ticket_id"] = ticket_id
    out["owned_by_me"] = owns
    return out


# ── Activity feed ─────────────────────────────────────────────────────────────
@router.get("/attorney/cases/{ticket_id}/activity")
def get_activity(ticket_id: str, authorization: Optional[str] = Header(None)):
    _verify_token(authorization)
    db = _db()
    docs = db.collection("tickets").document(ticket_id).collection("activity").stream()
    items = []
    for d in docs:
        data = d.to_dict()
        items.append({"id": d.id, **{k: _iso(v) for k, v in data.items()}})
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"activity": items, "count": len(items)}


class ActivityUpdate(BaseModel):
    category: Optional[str] = None       # e.g. "Status Update", "Attorney Note"
    message: str


@router.post("/attorney/cases/{ticket_id}/activity")
def add_activity(ticket_id: str, body: ActivityUpdate, authorization: Optional[str] = Header(None)):
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    ref = db.collection("tickets").document(ticket_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    entry = {
        "author_uid": uid,
        "author_name": decoded.get("name") or decoded.get("email") or "Attorney",
        "category": body.category or "Attorney Note",
        "message": body.message,
        "created_at": SERVER_TIMESTAMP,
    }
    _, doc_ref = ref.collection("activity").add(entry)
    ref.update({"last_activity_at": SERVER_TIMESTAMP})
    return {"ok": True, "activity_id": doc_ref.id}


# ── Claim ─────────────────────────────────────────────────────────────────────
@router.post("/attorney/cases/{ticket_id}/claim")
def claim_case(ticket_id: str, authorization: Optional[str] = Header(None)):
    """
    Attorney claims an open case. Platinum/Diamond auto-accept; everyone else's
    claim is held pending AM approval.
    """
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    ref = db.collection("tickets").document(ticket_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = snap.to_dict()

    if data.get("attorney_status") != _AVAILABLE_STATUS:
        raise HTTPException(status_code=409, detail="Case is not available to claim.")
    if data.get("claim_status") == "pending":
        raise HTTPException(status_code=409, detail="Case already has a pending claim.")

    # Level-gated auto-approval.
    atty = db.collection("attorneys").document(uid).get()
    level = (atty.to_dict() or {}).get("performance_level", "bronze") if atty.exists else "bronze"
    auto = level in AUTO_APPROVE_LEVELS

    update = {
        "claimed_by": uid,
        "claimed_at": SERVER_TIMESTAMP,
        "last_modified_date": SERVER_TIMESTAMP,
    }
    if auto:
        update.update({
            "claim_status": "approved",
            "attorney_status": _ACCEPTED_STATUS,
            "assigned_attorney_id": uid,
            "assigned_at": SERVER_TIMESTAMP,
        })
    else:
        update["claim_status"] = "pending"
    ref.update(update)

    logger.warning("[attorney_cases] claim ticket=%s attorney=%s level=%s auto=%s",
                   ticket_id, uid, level, auto)
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "auto_approved": auto,
        "status": _ACCEPTED_STATUS if auto else "pending_approval",
        "message": ("Case accepted — it's now in My Cases."
                    if auto else "Claim submitted — pending account manager approval."),
    }


class DeclineBody(BaseModel):
    reason: str


@router.post("/attorney/cases/{ticket_id}/decline")
def decline_case(ticket_id: str, body: DeclineBody, authorization: Optional[str] = Header(None)):
    """An assigned attorney releases a case back to the pool."""
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    ref = db.collection("tickets").document(ticket_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = snap.to_dict()
    if uid not in (data.get("assigned_attorney_id"), data.get("claimed_by")):
        raise HTTPException(status_code=403, detail="This case is not assigned to you.")

    ref.update({
        "attorney_status": _AVAILABLE_STATUS,
        "assigned_attorney_id": None,
        "claimed_by": None,
        "claim_status": None,
        "declined_by": uid,
        "decline_reason": body.reason,
        "declined_at": SERVER_TIMESTAMP,
        "last_modified_date": SERVER_TIMESTAMP,
    })
    logger.warning("[attorney_cases] declined ticket=%s attorney=%s", ticket_id, uid)
    return {"ok": True, "ticket_id": ticket_id}


# ── Current user ──────────────────────────────────────────────────────────────
@router.get("/me")
def me(authorization: Optional[str] = Header(None)):
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    snap = db.collection("attorneys").document(uid).get()
    a = snap.to_dict() if snap.exists else {}
    return {
        "uid": uid,
        "email": decoded.get("email") or a.get("email"),
        "name": decoded.get("name") or a.get("full_name") or a.get("Name"),
        "role": decoded.get("role", "attorney"),
        "tier": a.get("tier"),
        "performance_level": a.get("performance_level"),
        "has_profile": snap.exists,
        "self_sourced_enabled": bool(a.get("self_sourced_enabled")),
    }


# ── Notifications ─────────────────────────────────────────────────────────────
@router.get("/notifications")
def notifications(limit: int = 50, authorization: Optional[str] = Header(None)):
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    docs = (db.collection("attorney_notifications")
              .where("attorney_uid", "==", uid).limit(limit).stream())
    items = []
    for d in docs:
        data = d.to_dict()
        items.append({"id": d.id, **{k: _iso(v) for k, v in data.items()}})
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    unread = sum(1 for i in items if not i.get("read"))
    return {"notifications": items, "count": len(items), "unread": unread}


# ── Staff: claim-approval queue ───────────────────────────────────────────────
# Admin-console routes (frontend-qa): x-api-key auth, actor passed explicitly in the
# body since the console has no per-staff Firebase login (see _common.py note).
@router.get("/admin/claims/pending")
def pending_claims(x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    docs = db.collection("tickets").where("claim_status", "==", "pending").stream()
    claims = []
    for d in docs:
        data = d.to_dict()
        card = _card(d.id, data)
        card["claimed_by"] = data.get("claimed_by")
        card["claimed_at"] = _iso(data.get("claimed_at"))
        claims.append(card)
    return {"claims": claims, "count": len(claims)}


class ApproveClaimBody(BaseModel):
    approved_by: str


@router.post("/admin/cases/{ticket_id}/approve-claim")
def approve_claim(ticket_id: str, body: ApproveClaimBody, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    ref = db.collection("tickets").document(ticket_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = snap.to_dict()
    claimed_by = data.get("claimed_by")
    if data.get("claim_status") != "pending" or not claimed_by:
        raise HTTPException(status_code=409, detail="No pending claim on this case.")

    ref.update({
        "claim_status": "approved",
        "attorney_status": _ACCEPTED_STATUS,
        "assigned_attorney_id": claimed_by,
        "assigned_at": SERVER_TIMESTAMP,
        "claim_reviewed_by": body.approved_by,
        "claim_reviewed_at": SERVER_TIMESTAMP,
        "last_modified_date": SERVER_TIMESTAMP,
    })
    _notify(db, claimed_by, "claim_approved",
            "Claim approved", f"Your claim on case {ticket_id} was approved.")
    logger.warning("[attorney_cases] claim APPROVED ticket=%s attorney=%s by=%s",
                   ticket_id, claimed_by, body.approved_by)
    return {"ok": True, "ticket_id": ticket_id, "assigned_attorney_id": claimed_by}


class RejectClaimBody(BaseModel):
    reason: str
    rejected_by: str


@router.post("/admin/cases/{ticket_id}/reject-claim")
def reject_claim(ticket_id: str, body: RejectClaimBody, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    ref = db.collection("tickets").document(ticket_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = snap.to_dict()
    claimed_by = data.get("claimed_by")
    if data.get("claim_status") != "pending":
        raise HTTPException(status_code=409, detail="No pending claim on this case.")

    ref.update({
        "claim_status": "rejected",
        "attorney_status": _AVAILABLE_STATUS,   # back to the pool
        "claimed_by": None,
        "claim_reviewed_by": body.rejected_by,
        "claim_reviewed_at": SERVER_TIMESTAMP,
        "claim_rejection_reason": body.reason,
        "last_modified_date": SERVER_TIMESTAMP,
    })
    if claimed_by:
        _notify(db, claimed_by, "claim_rejected", "Claim not approved",
                body.reason or f"Your claim on case {ticket_id} was not approved.")
    logger.warning("[attorney_cases] claim REJECTED ticket=%s by=%s", ticket_id, body.rejected_by)
    return {"ok": True, "ticket_id": ticket_id}


def _notify(db, attorney_uid: str, ntype: str, title: str, body: str) -> None:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    db.collection("attorney_notifications").add({
        "attorney_uid": attorney_uid,
        "type": ntype,
        "title": title,
        "body": body,
        "read": False,
        "created_at": SERVER_TIMESTAMP,
    })
