"""
Attorney network routes — lead management, outreach tracking, ticket matching.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_auth(x_api_key: Optional[str]):
    if x_api_key != os.getenv("API_KEY", "cdl-local-dev"):
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _db():
    from app.services.firebase_service import db
    return db


# ── Models ────────────────────────────────────────────────────────────────────

class OutreachUpdate(BaseModel):
    status: Optional[str] = None          # lead|contacted|pricing_received|onboarded|declined
    assigned_to: Optional[str] = None     # eniola|quest|justin
    outreach_notes: Optional[str] = None
    follow_up_at: Optional[str] = None    # ISO date string

class PricingUpdate(BaseModel):
    pricing_flat_rate: Optional[str] = None
    pricing_volume: Optional[str] = None
    pricing_per_type: Optional[dict] = None   # {traffic, cdl, dui, criminal, federal, accident}
    states_covered: Optional[list[str]] = None
    counties_covered: Optional[list[str]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/attorneys")
async def list_attorneys(
    state: Optional[str] = None,
    status: Optional[str] = None,
    cdl_specialist: Optional[bool] = None,
    assigned_to: Optional[str] = None,
    limit: int = 100,
    x_api_key: Optional[str] = Header(None),
):
    """List attorney leads with optional filters."""
    _check_auth(x_api_key)
    db = _db()
    query = db.collection("attorneys")

    if state:
        query = query.where("state", "==", state.upper())
    if status:
        query = query.where("status", "==", status)
    if cdl_specialist is not None:
        query = query.where("cdl_specialist", "==", cdl_specialist)
    if assigned_to:
        query = query.where("assigned_to", "==", assigned_to)

    docs = query.limit(limit).stream()
    results = []
    for doc in docs:
        d = doc.to_dict()
        d["attorney_id"] = doc.id
        results.append(d)

    return {"attorneys": results, "count": len(results)}


@router.get("/attorneys/match")
async def match_attorneys(
    state: str,
    county: Optional[str] = None,
    practice: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """
    Find onboarded attorneys for a given ticket's state/county.
    Used by the ticket engine to surface attorneys at intake.
    Falls back: county match → state match → CDL specialists in state.
    """
    _check_auth(x_api_key)
    db = _db()

    state = state.upper()
    results = []

    # Tier 1: onboarded attorneys covering this specific county
    if county:
        q = (db.collection("attorneys")
             .where("status", "==", "onboarded")
             .where("states_covered", "array_contains", state)
             .where("counties_covered", "array_contains", county)
             .limit(10))
        tier1 = [d.to_dict() | {"attorney_id": d.id, "match_tier": "county"} for d in q.stream()]
        results.extend(tier1)

    # Tier 2: onboarded in state (no county filter)
    if len(results) < 3:
        q = (db.collection("attorneys")
             .where("status", "==", "onboarded")
             .where("states_covered", "array_contains", state)
             .limit(10))
        tier2 = [d.to_dict() | {"attorney_id": d.id, "match_tier": "state"} for d in q.stream()
                 if not any(r["attorney_id"] == d.id for r in results)]
        results.extend(tier2)

    # Tier 3: leads (not yet onboarded) in state — signal to reach out
    if len(results) < 3:
        q = (db.collection("attorneys")
             .where("state", "==", state)
             .where("status", "in", ["lead", "contacted", "pricing_received"])
             .limit(5))
        tier3 = [d.to_dict() | {"attorney_id": d.id, "match_tier": "lead_in_state"} for d in q.stream()
                 if not any(r["attorney_id"] == d.id for r in results)]
        results.extend(tier3)

    # Sort by Google rating descending
    results.sort(key=lambda x: float(x.get("google_rating") or 0), reverse=True)

    return {
        "state": state,
        "county": county,
        "attorneys": results[:5],
        "onboarded_count": sum(1 for r in results if r.get("status") == "onboarded"),
        "needs_outreach": len(results) == 0 or all(r.get("status") != "onboarded" for r in results),
    }


@router.get("/attorneys/pipeline")
async def pipeline_summary(x_api_key: Optional[str] = Header(None)):
    """Dashboard summary — counts by status and state."""
    _check_auth(x_api_key)
    db = _db()

    docs = db.collection("attorneys").stream()
    by_status: dict[str, int] = {}
    by_state: dict[str, int] = {}
    cdl_count = 0
    total = 0

    for doc in docs:
        d = doc.to_dict()
        total += 1
        s = d.get("status", "lead")
        by_status[s] = by_status.get(s, 0) + 1
        st = d.get("state", "")
        if st:
            by_state[st] = by_state.get(st, 0) + 1
        if d.get("cdl_specialist"):
            cdl_count += 1

    return {
        "total": total,
        "cdl_specialists": cdl_count,
        "by_status": by_status,
        "by_state": dict(sorted(by_state.items(), key=lambda x: x[1], reverse=True)),
    }


@router.get("/attorneys/{attorney_id}")
async def get_attorney(attorney_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    doc = _db().collection("attorneys").document(attorney_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Attorney not found")
    return doc.to_dict() | {"attorney_id": doc.id}


@router.patch("/attorneys/{attorney_id}/outreach")
async def update_outreach(
    attorney_id: str,
    body: OutreachUpdate,
    x_api_key: Optional[str] = Header(None),
):
    """Update outreach status, assignment, notes."""
    _check_auth(x_api_key)
    db = _db()
    ref = db.collection("attorneys").document(attorney_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Attorney not found")

    update = {"updated_at": datetime.now(timezone.utc)}
    if body.status:
        update["status"] = body.status
        if body.status == "contacted":
            update["contacted_at"] = datetime.now(timezone.utc)
        elif body.status == "onboarded":
            update["onboarded_at"] = datetime.now(timezone.utc)
    if body.assigned_to is not None:
        update["assigned_to"] = body.assigned_to
    if body.outreach_notes is not None:
        update["outreach_notes"] = body.outreach_notes
    if body.follow_up_at is not None:
        update["follow_up_at"] = body.follow_up_at

    ref.update(update)
    return {"ok": True, "attorney_id": attorney_id, "updated": list(update.keys())}


@router.patch("/attorneys/{attorney_id}/pricing")
async def update_pricing(
    attorney_id: str,
    body: PricingUpdate,
    x_api_key: Optional[str] = Header(None),
):
    """Record pricing collected during outreach."""
    _check_auth(x_api_key)
    db = _db()
    ref = db.collection("attorneys").document(attorney_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Attorney not found")

    update = {"updated_at": datetime.now(timezone.utc)}
    if body.pricing_flat_rate is not None:
        update["pricing_flat_rate"] = body.pricing_flat_rate
    if body.pricing_volume is not None:
        update["pricing_volume"] = body.pricing_volume
    if body.pricing_per_type is not None:
        update["pricing_per_type"] = body.pricing_per_type
    if body.states_covered is not None:
        update["states_covered"] = [s.upper() for s in body.states_covered]
    if body.counties_covered is not None:
        update["counties_covered"] = body.counties_covered
    # Auto-advance status to pricing_received
    if any([body.pricing_flat_rate, body.pricing_volume, body.pricing_per_type]):
        update["status"] = "pricing_received"

    ref.update(update)
    return {"ok": True, "attorney_id": attorney_id}


@router.get("/attorneys/states/coverage")
async def state_coverage(x_api_key: Optional[str] = Header(None)):
    """
    Which states have scanned tickets vs which have onboarded attorneys.
    Drives outreach prioritization — shows gaps.
    """
    _check_auth(x_api_key)
    db = _db()

    # States with tickets
    ticket_states: dict[str, int] = {}
    for doc in db.collection("tickets").stream():
        st = doc.to_dict().get("ticket_state", "")
        if st:
            ticket_states[st.upper()] = ticket_states.get(st.upper(), 0) + 1

    # States with onboarded attorneys
    onboarded_states: set[str] = set()
    lead_states: dict[str, int] = {}
    for doc in db.collection("attorneys").stream():
        d = doc.to_dict()
        st = d.get("state", "").upper()
        if d.get("status") == "onboarded":
            onboarded_states.update(d.get("states_covered", [st]))
        if st:
            lead_states[st] = lead_states.get(st, 0) + 1

    coverage = []
    for state, ticket_count in sorted(ticket_states.items(), key=lambda x: x[1], reverse=True):
        coverage.append({
            "state": state,
            "ticket_count": ticket_count,
            "has_onboarded_attorney": state in onboarded_states,
            "total_leads": lead_states.get(state, 0),
            "priority": "HIGH" if state not in onboarded_states and ticket_count > 0 else "normal",
        })

    # States with leads but no tickets yet
    for state, lead_count in lead_states.items():
        if state not in ticket_states:
            coverage.append({
                "state": state,
                "ticket_count": 0,
                "has_onboarded_attorney": state in onboarded_states,
                "total_leads": lead_count,
                "priority": "normal",
            })

    return {"coverage": coverage}
