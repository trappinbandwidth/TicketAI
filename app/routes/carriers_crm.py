"""
Carrier CRM routes — prospect management, outreach tracking, coverage.

Mirrors attorneys.py pattern:
  GET  /carriers                    list + filter
  GET  /carriers/{dot}              single record
  GET  /carriers/pipeline           counts by status
  GET  /carriers/coverage           states by carrier density vs driver enrollment
  PATCH /carriers/{dot}/outreach    update status/notes/assignment
  PATCH /carriers/{dot}/enrollment  record enrollment details
  GET  /carriers/jobs/history       FMCSA job run log
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from app.routes._common import require_staff
from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter()

CARRIER_STATUSES = ["lead", "contacted", "demo_scheduled", "enrolled", "declined"]



def _db():
    from app.services.firebase_service import db
    return db


# ── Models ─────────────────────────────────────────────────────────────────────

class OutreachUpdate(BaseModel):
    status: Optional[str] = None       # lead|contacted|demo_scheduled|enrolled|declined
    assigned_to: Optional[str] = None  # eniola|quest|justin
    outreach_notes: Optional[str] = None
    follow_up_at: Optional[str] = None

class EnrollmentUpdate(BaseModel):
    monthly_rate: Optional[str] = None          # "$12/driver/month"
    driver_count_enrolled: Optional[int] = None
    billing_contact: Optional[str] = None
    billing_email: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/carriers")
async def list_carriers(
    state: Optional[str] = None,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    min_drivers: Optional[int] = None,
    oos_only: bool = False,
    limit: int = 100,
    authorization: Optional[str] = Header(None),
):
    """List carrier prospects with optional filters."""
    require_staff(authorization)
    db = _db()
    query = db.collection("carriers")

    if state:
        query = query.where("state", "==", state.upper())
    if status:
        query = query.where("status", "==", status)
    if assigned_to:
        query = query.where("assigned_to", "==", assigned_to)
    if oos_only:
        query = query.where("oos_active", "==", True)

    docs = query.limit(limit).stream()
    results = []
    for doc in docs:
        d = doc.to_dict()
        d["dot_number"] = doc.id
        if min_drivers and int(d.get("driver_total") or 0) < min_drivers:
            continue
        # Serialize Firestore timestamps
        for ts_field in ["created_at", "updated_at", "contacted_at", "enrolled_at"]:
            if hasattr(d.get(ts_field), "isoformat"):
                d[ts_field] = d[ts_field].isoformat()
        results.append(d)

    return {"carriers": results, "count": len(results)}


@router.get("/carriers/pipeline")
async def pipeline_summary(authorization: Optional[str] = Header(None)):
    """Dashboard counts — by status, by state, OOS flags."""
    require_staff(authorization)
    db = _db()

    by_status: dict[str, int] = {}
    by_state: dict[str, int] = {}
    total_drivers = 0
    enrolled_drivers = 0
    oos_count = 0
    total = 0

    for doc in db.collection("carriers").stream():
        d = doc.to_dict()
        total += 1
        s = d.get("status", "lead")
        by_status[s] = by_status.get(s, 0) + 1
        st = d.get("state", "")
        if st:
            by_state[st] = by_state.get(st, 0) + 1
        try:
            total_drivers += int(d.get("driver_total") or 0)
        except (ValueError, TypeError):
            pass
        if s == "enrolled":
            try:
                enrolled_drivers += int(d.get("driver_count_enrolled") or 0)
            except (ValueError, TypeError):
                pass
        if d.get("oos_active"):
            oos_count += 1

    return {
        "total": total,
        "oos_flagged": oos_count,
        "total_driver_pool": total_drivers,
        "enrolled_drivers": enrolled_drivers,
        "by_status": by_status,
        "by_state": dict(sorted(by_state.items(), key=lambda x: x[1], reverse=True)),
    }


@router.get("/carriers/coverage")
async def state_coverage(authorization: Optional[str] = Header(None)):
    """
    Which states have the most uncontacted carrier prospects.
    Drives outreach prioritization — sorts by lead density.
    """
    require_staff(authorization)
    db = _db()

    by_state: dict[str, dict] = {}
    for doc in db.collection("carriers").stream():
        d = doc.to_dict()
        st = (d.get("state") or "").upper()
        if not st:
            continue
        if st not in by_state:
            by_state[st] = {"total": 0, "leads": 0, "enrolled": 0, "driver_pool": 0}
        by_state[st]["total"] += 1
        status = d.get("status", "lead")
        if status == "lead":
            by_state[st]["leads"] += 1
        if status == "enrolled":
            by_state[st]["enrolled"] += 1
        try:
            by_state[st]["driver_pool"] += int(d.get("driver_total") or 0)
        except (ValueError, TypeError):
            pass

    coverage = [
        {"state": st, **counts} for st, counts in
        sorted(by_state.items(), key=lambda x: x[1]["leads"], reverse=True)
    ]
    return {"coverage": coverage}


@router.get("/carriers/{dot_number}")
async def get_carrier(dot_number: str, authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    doc = _db().collection("carriers").document(dot_number).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Carrier not found")
    d = doc.to_dict()
    d["dot_number"] = doc.id
    for ts_field in ["created_at", "updated_at", "contacted_at", "enrolled_at"]:
        if hasattr(d.get(ts_field), "isoformat"):
            d[ts_field] = d[ts_field].isoformat()
    return d


@router.patch("/carriers/{dot_number}/outreach")
async def update_outreach(
    dot_number: str,
    body: OutreachUpdate,
    authorization: Optional[str] = Header(None),
):
    """Update outreach status, assignment, notes."""
    require_staff(authorization)
    db = _db()
    ref = db.collection("carriers").document(dot_number)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Carrier not found")

    update: dict = {"updated_at": datetime.now(timezone.utc)}
    if body.status:
        if body.status not in CARRIER_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Use: {CARRIER_STATUSES}")
        update["status"] = body.status
        if body.status == "contacted":
            update["contacted_at"] = datetime.now(timezone.utc)
        elif body.status == "enrolled":
            update["enrolled_at"] = datetime.now(timezone.utc)
    if body.assigned_to is not None:
        update["assigned_to"] = body.assigned_to
    if body.outreach_notes is not None:
        update["outreach_notes"] = body.outreach_notes
    if body.follow_up_at is not None:
        update["follow_up_at"] = body.follow_up_at

    ref.update(update)
    return {"ok": True, "dot_number": dot_number, "updated": list(update.keys())}


@router.patch("/carriers/{dot_number}/enrollment")
async def update_enrollment(
    dot_number: str,
    body: EnrollmentUpdate,
    authorization: Optional[str] = Header(None),
):
    """Record enrollment details after a carrier signs up."""
    require_staff(authorization)
    db = _db()
    ref = db.collection("carriers").document(dot_number)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Carrier not found")

    update: dict = {
        "status": "enrolled",
        "enrolled_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    if body.monthly_rate is not None:
        update["monthly_rate"] = body.monthly_rate
    if body.driver_count_enrolled is not None:
        update["driver_count_enrolled"] = body.driver_count_enrolled
    if body.billing_contact is not None:
        update["billing_contact"] = body.billing_contact
    if body.billing_email is not None:
        update["billing_email"] = body.billing_email

    ref.update(update)
    return {"ok": True, "dot_number": dot_number}


@router.get("/carriers/jobs/history")
async def job_history(limit: int = 10, authorization: Optional[str] = Header(None)):
    """Recent FMCSA job runs — for monitoring in the Carriers tab."""
    require_staff(authorization)
    db = _db()
    docs = (db.collection("job_runs")
              .where("job", "in", ["fmcsa_carrier_full", "fmcsa_oos_delta"])
              .order_by("run_at", direction="DESCENDING")
              .limit(limit)
              .stream())
    runs = []
    for doc in docs:
        d = doc.to_dict()
        d["run_id"] = doc.id
        if hasattr(d.get("run_at"), "isoformat"):
            d["run_at"] = d["run_at"].isoformat()
        runs.append(d)
    return {"runs": runs}
