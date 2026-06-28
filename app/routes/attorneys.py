"""
Attorney network routes — lead management, outreach tracking, ticket matching.
"""
from __future__ import annotations
import logging
import os
import requests as _requests
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
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


@router.get("/attorneys/jobs/history")
async def job_history(limit: int = 10, x_api_key: Optional[str] = Header(None)):
    """Recent attorney discovery job runs — for monitoring in the Network tab."""
    _check_auth(x_api_key)
    db = _db()
    docs = (db.collection("job_runs")
              .where("job", "==", "attorney_discovery")
              .order_by("run_at", direction="DESCENDING")
              .limit(limit)
              .stream())
    runs = []
    for doc in docs:
        d = doc.to_dict()
        d["run_id"] = doc.id
        # Convert Firestore timestamp to ISO string
        if hasattr(d.get("run_at"), "isoformat"):
            d["run_at"] = d["run_at"].isoformat()
        runs.append(d)
    return {"runs": runs}


# ── On-demand discovery ────────────────────────────────────────────────────────

def _trigger_discovery_job(state: str, ticket_id: str = ""):
    """
    Fire the attorney-discovery Cloud Run Job for a specific state.
    Uses ADC — no service account key needed.
    Logs result to Firestore job_runs/ for monitoring.
    """
    project = os.getenv("FIREBASE_PROJECT_ID", "rigresolve")
    region  = os.getenv("CLOUD_RUN_REGION", "us-central1")
    job     = os.getenv("DISCOVERY_JOB_NAME", "attorney-discovery")

    try:
        import google.auth
        import google.auth.transport.requests
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        token = creds.token
    except Exception as e:
        logger.error("[discovery] Failed to get ADC token: %s", e)
        return

    url = (
        f"https://run.googleapis.com/v2/projects/{project}/locations/{region}"
        f"/jobs/{job}:run"
    )
    payload = {
        "overrides": {
            "containerOverrides": [{
                "env": [{"name": "SINGLE_STATE", "value": state.upper()}]
            }]
        }
    }
    try:
        resp = _requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        resp.raise_for_status()
        logger.warning("[discovery] Triggered job for state=%s ticket=%s", state, ticket_id)
    except Exception as e:
        logger.error("[discovery] Job trigger failed state=%s: %s", state, e)


def _write_outreach_alert(db, state: str, ticket_id: str, ticket_county: str = ""):
    """Write an alert to Firestore so the Network tab and Eniola can see it."""
    db.collection("outreach_alerts").add({
        "state": state,
        "county": ticket_county,
        "ticket_id": ticket_id,
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "message": f"New ticket in {state} ({ticket_county}) — no onboarded attorney. Discovery job triggered.",
    })


def trigger_discovery_for_ticket(ticket_id: str, state: str, county: str = ""):
    """
    Called as a background task after ticket approval when no attorney is available.
    Fires the Cloud Run Job and writes an alert.
    """
    db = _db()
    if db is None:
        return
    _write_outreach_alert(db, state, ticket_id, county)
    _trigger_discovery_job(state, ticket_id)


@router.post("/attorneys/discover")
async def trigger_discovery(
    state: str,
    background_tasks: BackgroundTasks,
    ticket_id: str = "",
    x_api_key: Optional[str] = Header(None),
):
    """
    Manually trigger an on-demand attorney discovery scrape for a specific state.
    Also called automatically when a ticket is approved with no onboarded attorney.
    """
    _check_auth(x_api_key)
    if not state or len(state) != 2:
        raise HTTPException(status_code=400, detail="state must be a 2-letter code (e.g. TX)")

    background_tasks.add_task(_trigger_discovery_job, state.upper(), ticket_id)
    logger.warning("[discovery] Queued on-demand scrape state=%s", state.upper())
    return {"ok": True, "state": state.upper(), "message": "Discovery job queued"}


@router.get("/attorneys/alerts")
async def get_alerts(status: str = "open", limit: int = 20, x_api_key: Optional[str] = Header(None)):
    """Outreach alerts — states with tickets but no onboarded attorney."""
    _check_auth(x_api_key)
    db = _db()
    docs = (db.collection("outreach_alerts")
              .where("status", "==", status)
              .order_by("created_at", direction="DESCENDING")
              .limit(limit)
              .stream())
    alerts = []
    for doc in docs:
        d = doc.to_dict()
        d["alert_id"] = doc.id
        if hasattr(d.get("created_at"), "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        alerts.append(d)
    return {"alerts": alerts, "count": len(alerts)}
