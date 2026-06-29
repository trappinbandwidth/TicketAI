"""
CP-12 — Workday HCM integration.

Provides:
  1. POST /integrations/workday/register   — store Workday credentials + field mappings
  2. POST /webhooks/workday/{carrier_uid}  — receive hire/termination/LOA events from Workday
  3. GET  /integrations/workday/{uid}/deduction-export — generate payroll deduction CSV

Workday → Rig Resolve: new hires, terminations, LOA events
Rig Resolve → Workday: monthly deduction CSV (driver ID, amount, period, plan code)

Firestore paths:
  carriers/{uid}/integrations/workday          — config
  workday_events/{event_id}                    — audit log
  carriers/{uid}/drivers/{driver_id}           — activated/deactivated driver records
"""
from __future__ import annotations

import csv
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["workday"])


def _db():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _check_api_key(x_api_key: Optional[str]) -> None:
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Registration ──────────────────────────────────────────────────────────────

class RegisterWorkdayBody(BaseModel):
    carrier_uid: str
    tenant_url: str          # e.g. https://wd3.myworkday.com/acme/
    client_id: str
    client_secret: str       # stored server-side only
    deduction_paycode: Optional[str] = "RIG_RESOLVE"
    worker_type_map: Optional[dict] = None   # Workday worker type → RR employment type
    cost_center_dot_map: Optional[dict] = None  # Workday cost center → DOT number


@router.post("/integrations/workday/register")
def register_workday(
    body: RegisterWorkdayBody,
    x_api_key: Optional[str] = Header(None),
):
    """Store Workday integration credentials and field mappings."""
    _check_api_key(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    db.collection("carriers").document(body.carrier_uid).set({
        "integrations": {
            "workday": {
                "enabled": True,
                "tenant_url": body.tenant_url,
                "client_id": body.client_id,
                "client_secret": body.client_secret,
                "deduction_paycode": body.deduction_paycode or "RIG_RESOLVE",
                "worker_type_map": body.worker_type_map or {},
                "cost_center_dot_map": body.cost_center_dot_map or {},
                "registered_at": _now_iso(),
            }
        }
    }, merge=True)

    base_url = os.getenv("PUBLIC_BASE_URL", "https://ai-ticket-engine-kajugdk3nq-uc.a.run.app")
    webhook_url = f"{base_url}/api/v1/webhooks/workday/{body.carrier_uid}"
    logger.info("[workday] registered carrier=%s", body.carrier_uid)
    return {"success": True, "webhook_url": webhook_url}


# ── Webhook receiver ──────────────────────────────────────────────────────────

@router.post("/webhooks/workday/{carrier_uid}")
async def workday_webhook(
    carrier_uid: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Receive Workday HR events.
    Workday uses OAuth2 Bearer token — we verify the token matches client_id/client_secret.
    In production, validate the token against Workday's JWKS endpoint.
    For now, accept any bearer token when Workday integration is enabled.
    """
    import json
    payload = await request.body()
    db = _db()

    carrier_doc = db.collection("carriers").document(carrier_uid).get()
    if not carrier_doc.exists:
        raise HTTPException(status_code=404, detail="Carrier not found.")
    carrier_data = carrier_doc.to_dict() or {}
    wd_config = (carrier_data.get("integrations") or {}).get("workday", {})
    if not wd_config.get("enabled"):
        raise HTTPException(status_code=400, detail="Workday integration not enabled for this carrier.")

    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload.")

    event_type = event.get("eventType", event.get("event_type", ""))
    worker = event.get("worker", event.get("driver", {}))
    event_id = str(uuid.uuid4())
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    db.collection("workday_events").document(event_id).set({
        "event_id": event_id,
        "carrier_uid": carrier_uid,
        "event_type": event_type,
        "raw": event,
        "processed_at": SERVER_TIMESTAMP,
        "status": "received",
    })

    action = "ignored"
    try:
        action = _handle_workday_event(db, carrier_uid, event_type, worker, wd_config, event_id)
    except Exception as exc:
        logger.error("[workday] handler failed carrier=%s type=%s: %s", carrier_uid, event_type, exc)
        db.collection("workday_events").document(event_id).update({"status": "error", "error": str(exc)})
        return {"received": True, "action": "error", "event_id": event_id}

    db.collection("workday_events").document(event_id).update({"status": "processed", "action": action})
    return {"received": True, "action": action, "event_id": event_id}


def _handle_workday_event(db, carrier_uid: str, event_type: str, worker: dict, config: dict, event_id: str) -> str:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    worker_type = worker.get("workerType", "")
    cost_center = worker.get("costCenter", "")
    employment_type = config.get("worker_type_map", {}).get(worker_type, "full_time")
    dot_number = config.get("cost_center_dot_map", {}).get(cost_center, "")

    drivers_ref = db.collection("carriers").document(carrier_uid).collection("drivers")
    employee_id = worker.get("employeeId", worker.get("employee_id", ""))
    email = worker.get("email", worker.get("workEmail", ""))

    existing = None
    if employee_id:
        q = list(drivers_ref.where("employee_id", "==", employee_id).limit(1).stream())
        if q:
            existing = q[0]
    if not existing and email:
        q = list(drivers_ref.where("email", "==", email).limit(1).stream())
        if q:
            existing = q[0]

    first = worker.get("firstName", worker.get("first_name", ""))
    last = worker.get("lastName", worker.get("last_name", ""))
    phone = worker.get("phone", worker.get("workPhone", ""))

    if event_type in ("Hire", "worker.hired", "driver.hired"):
        if existing:
            existing.reference.update({
                "status": "active",
                "employment_type": employment_type,
                "dot_number": dot_number or existing.to_dict().get("dot_number", ""),
                "last_workday_event": event_type,
                "last_workday_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "reactivated"
        driver_id = str(uuid.uuid4())
        drivers_ref.document(driver_id).set({
            "driver_id": driver_id,
            "first_name": first,
            "last_name": last,
            "full_name": f"{first} {last}".strip(),
            "phone": phone,
            "email": email,
            "employee_id": employee_id,
            "employment_type": employment_type,
            "dot_number": dot_number,
            "status": "active",
            "source": "workday",
            "last_workday_event": event_type,
            "last_workday_event_id": event_id,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })
        return "created"

    elif event_type in ("Termination", "worker.terminated"):
        if existing:
            existing.reference.update({
                "status": "inactive",
                "terminated_at": _now_iso(),
                "last_workday_event": event_type,
                "last_workday_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "deactivated"
        return "not_found"

    elif event_type in ("LeaveOfAbsence", "worker.loa"):
        if existing:
            existing.reference.update({
                "status": "loa",
                "loa_start": _now_iso(),
                "last_workday_event": event_type,
                "last_workday_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "loa_started"
        return "not_found"

    return "unhandled"


# ── Deduction CSV export ──────────────────────────────────────────────────────

@router.get("/integrations/workday/{carrier_uid}/deduction-export")
def deduction_export(
    carrier_uid: str,
    period: Optional[str] = None,  # e.g. "2026-06"
    x_api_key: Optional[str] = Header(None),
):
    """
    Generate payroll deduction CSV for the carrier's active drivers.
    Columns: employee_id, driver_name, dot_number, plan_code, amount, period
    """
    _check_api_key(x_api_key)
    db = _db()

    carrier_doc = db.collection("carriers").document(carrier_uid).get()
    if not carrier_doc.exists:
        raise HTTPException(status_code=404, detail="Carrier not found.")
    carrier_data = carrier_doc.to_dict() or {}
    wd_config = (carrier_data.get("integrations") or {}).get("workday", {})
    paycode = wd_config.get("deduction_paycode", "RIG_RESOLVE")

    # Load subscription to get per-driver amount
    sub = carrier_data.get("subscription", {})
    plan_price = sub.get("plan_price", 0.0)

    # Load active drivers
    drivers = db.collection("carriers").document(carrier_uid).collection("drivers")\
               .where("status", "==", "active").stream()

    export_period = period or datetime.now(timezone.utc).strftime("%Y-%m")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["employee_id", "driver_name", "dot_number", "plan_code", "deduction_amount", "period"])

    row_count = 0
    for d in drivers:
        dr = d.to_dict()
        writer.writerow([
            dr.get("employee_id", d.id),
            dr.get("full_name", f"{dr.get('first_name','')} {dr.get('last_name','')}".strip()),
            dr.get("dot_number", ""),
            paycode,
            f"{plan_price:.2f}",
            export_period,
        ])
        row_count += 1

    output.seek(0)
    filename = f"rig_resolve_deductions_{carrier_uid}_{export_period}.csv"
    logger.info("[workday] deduction export carrier=%s period=%s rows=%d", carrier_uid, export_period, row_count)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Integration status ────────────────────────────────────────────────────────

@router.get("/integrations/workday/{carrier_uid}/status")
def workday_status(
    carrier_uid: str,
    x_api_key: Optional[str] = Header(None),
):
    _check_api_key(x_api_key)
    db = _db()

    carrier_doc = db.collection("carriers").document(carrier_uid).get()
    if not carrier_doc.exists:
        raise HTTPException(status_code=404, detail="Carrier not found.")
    carrier_data = carrier_doc.to_dict() or {}
    wd_config = (carrier_data.get("integrations") or {}).get("workday", {})

    events = []
    q = db.collection("workday_events")\
          .where("carrier_uid", "==", carrier_uid)\
          .limit(30).stream()
    for e in q:
        d = e.to_dict()
        events.append({
            "event_id": d.get("event_id"),
            "event_type": d.get("event_type"),
            "action": d.get("action"),
            "status": d.get("status"),
        })

    return {
        "carrier_uid": carrier_uid,
        "enabled": wd_config.get("enabled", False),
        "tenant_url": wd_config.get("tenant_url", ""),
        "deduction_paycode": wd_config.get("deduction_paycode", ""),
        "registered_at": wd_config.get("registered_at"),
        "recent_events": events,
    }
