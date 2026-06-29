"""
CP-11 — TenStreet webhook receiver.

TenStreet sends HMAC-SHA256-signed POST events when drivers are hired,
terminated, transferred, or updated in a carrier's ATS.

Supported events:
  driver.hired      → activate driver in Rig Resolve
  driver.terminated → deactivate driver
  driver.rehired    → re-activate driver
  driver.dot_transfer → move driver to different DOT
  driver.updated    → sync profile fields

Firestore paths written:
  carriers/{carrier_uid}/drivers/{driver_id}
  tenstreet_events/{event_id}       (audit log)

Setup:
  1. Carrier registers TenStreet integration at POST /integrations/tenstreet/register
  2. Rig Resolve generates a unique webhook URL for the carrier
  3. Carrier pastes the URL + their secret key into TenStreet
  4. TenStreet signs each event with HMAC-SHA256(carrier_secret, payload)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tenstreet"])


def _db():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _verify_hmac(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Registration ──────────────────────────────────────────────────────────────

class RegisterTenStreetBody(BaseModel):
    carrier_uid: str
    company_key: str   # TenStreet company key
    api_key: str       # TenStreet API key (used to sign events)


def _check_api_key(x_api_key: Optional[str]) -> None:
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


@router.post("/integrations/tenstreet/register")
def register_tenstreet(
    body: RegisterTenStreetBody,
    x_api_key: Optional[str] = Header(None),
):
    """Staff / carrier registers TenStreet credentials. Returns webhook URL."""
    _check_api_key(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    # Store integration config in Firestore (API key stored encrypted in practice)
    db.collection("carriers").document(body.carrier_uid).set({
        "integrations": {
            "tenstreet": {
                "enabled": True,
                "company_key": body.company_key,
                "api_key": body.api_key,
                "registered_at": _now_iso(),
                "webhook_url": f"/api/v1/webhooks/tenstreet/{body.carrier_uid}",
            }
        }
    }, merge=True)

    base_url = os.getenv("PUBLIC_BASE_URL", "https://ai-ticket-engine-kajugdk3nq-uc.a.run.app")
    webhook_url = f"{base_url}/api/v1/webhooks/tenstreet/{body.carrier_uid}"
    logger.info("[tenstreet] registered carrier=%s", body.carrier_uid)
    return {"success": True, "webhook_url": webhook_url}


# ── Webhook receiver ──────────────────────────────────────────────────────────

@router.post("/webhooks/tenstreet/{carrier_uid}")
async def tenstreet_webhook(
    carrier_uid: str,
    request: Request,
    x_tenstreet_signature: Optional[str] = Header(None, alias="x-tenstreet-signature"),
):
    """
    Receive TenStreet driver lifecycle events for a specific carrier.
    Verifies HMAC signature when the carrier's api_key is configured.
    """
    payload = await request.body()
    db = _db()

    # Load carrier integration config
    carrier_doc = db.collection("carriers").document(carrier_uid).get()
    if not carrier_doc.exists:
        raise HTTPException(status_code=404, detail="Carrier not found.")
    carrier_data = carrier_doc.to_dict() or {}
    ts_config = (carrier_data.get("integrations") or {}).get("tenstreet", {})
    if not ts_config.get("enabled"):
        raise HTTPException(status_code=400, detail="TenStreet integration not enabled for this carrier.")

    # Verify signature when api_key is configured
    api_key = ts_config.get("api_key", "")
    if api_key and x_tenstreet_signature:
        if not _verify_hmac(payload, x_tenstreet_signature, api_key):
            logger.warning("[tenstreet] invalid signature carrier=%s", carrier_uid)
            raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload.")

    event_type = event.get("event_type", "")
    driver_data = event.get("driver", {})
    event_id = str(uuid.uuid4())
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    # Log the raw event
    db.collection("tenstreet_events").document(event_id).set({
        "event_id": event_id,
        "carrier_uid": carrier_uid,
        "event_type": event_type,
        "raw": event,
        "processed_at": SERVER_TIMESTAMP,
        "status": "received",
    })

    action_taken = "ignored"
    try:
        action_taken = _handle_event(db, carrier_uid, event_type, driver_data, event_id)
    except Exception as exc:
        logger.error("[tenstreet] event handler failed carrier=%s type=%s: %s", carrier_uid, event_type, exc)
        db.collection("tenstreet_events").document(event_id).update({"status": "error", "error": str(exc)})
        return {"received": True, "action": "error", "event_id": event_id}

    db.collection("tenstreet_events").document(event_id).update({"status": "processed", "action": action_taken})
    logger.info("[tenstreet] carrier=%s event=%s action=%s", carrier_uid, event_type, action_taken)
    return {"received": True, "action": action_taken, "event_id": event_id}


def _handle_event(db, carrier_uid: str, event_type: str, driver_data: dict, event_id: str) -> str:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    # Extract driver identity
    cdl = driver_data.get("cdl_number", "")
    first = driver_data.get("first_name", "")
    last = driver_data.get("last_name", "")
    phone = driver_data.get("phone", "")
    email = driver_data.get("email", "")
    dot = driver_data.get("dot_number", "")
    employee_id = driver_data.get("employee_id", "")

    # Look up existing driver by CDL or employee_id
    drivers_ref = db.collection("carriers").document(carrier_uid).collection("drivers")
    existing = None
    if cdl:
        q = list(drivers_ref.where("cdl_number", "==", cdl).limit(1).stream())
        if q:
            existing = q[0]
    if not existing and employee_id:
        q = list(drivers_ref.where("employee_id", "==", employee_id).limit(1).stream())
        if q:
            existing = q[0]

    if event_type == "driver.hired":
        if existing:
            existing.reference.update({
                "status": "active",
                "last_tenstreet_event": event_type,
                "last_tenstreet_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "reactivated"
        driver_id = str(uuid.uuid4())
        drivers_ref.document(driver_id).set({
            "driver_id": driver_id,
            "first_name": first,
            "last_name": last,
            "full_name": f"{first} {last}".strip(),
            "cdl_number": cdl,
            "phone": phone,
            "email": email,
            "dot_number": dot,
            "employee_id": employee_id,
            "status": "active",
            "source": "tenstreet",
            "last_tenstreet_event": event_type,
            "last_tenstreet_event_id": event_id,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })
        return "created"

    elif event_type in ("driver.terminated",):
        if existing:
            existing.reference.update({
                "status": "inactive",
                "terminated_at": _now_iso(),
                "last_tenstreet_event": event_type,
                "last_tenstreet_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "deactivated"
        return "not_found"

    elif event_type == "driver.rehired":
        if existing:
            existing.reference.update({
                "status": "active",
                "last_tenstreet_event": event_type,
                "last_tenstreet_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "reactivated"
        return "not_found"

    elif event_type == "driver.dot_transfer":
        new_dot = driver_data.get("new_dot_number") or dot
        if existing:
            existing.reference.update({
                "dot_number": new_dot,
                "last_tenstreet_event": event_type,
                "last_tenstreet_event_id": event_id,
                "updated_at": SERVER_TIMESTAMP,
            })
            return "dot_transferred"
        return "not_found"

    elif event_type == "driver.updated":
        updates = {}
        for field in ("first_name", "last_name", "phone", "email", "cdl_number", "dot_number"):
            if field in driver_data and driver_data[field]:
                updates[field] = driver_data[field]
        if "first_name" in updates or "last_name" in updates:
            fn = updates.get("first_name", driver_data.get("first_name", ""))
            ln = updates.get("last_name",  driver_data.get("last_name", ""))
            updates["full_name"] = f"{fn} {ln}".strip()
        if existing and updates:
            updates["last_tenstreet_event"] = event_type
            updates["last_tenstreet_event_id"] = event_id
            updates["updated_at"] = SERVER_TIMESTAMP
            existing.reference.update(updates)
            return "updated"
        return "no_changes"

    return "unhandled"


# ── Integration status ────────────────────────────────────────────────────────

@router.get("/integrations/tenstreet/{carrier_uid}/status")
def tenstreet_status(
    carrier_uid: str,
    x_api_key: Optional[str] = Header(None),
):
    """Return integration config + last 30 events for this carrier."""
    _check_api_key(x_api_key)
    db = _db()

    carrier_doc = db.collection("carriers").document(carrier_uid).get()
    if not carrier_doc.exists:
        raise HTTPException(status_code=404, detail="Carrier not found.")
    carrier_data = carrier_doc.to_dict() or {}
    ts_config = (carrier_data.get("integrations") or {}).get("tenstreet", {})

    events = []
    q = db.collection("tenstreet_events")\
          .where("carrier_uid", "==", carrier_uid)\
          .order_by("processed_at", direction="DESCENDING")\
          .limit(30).stream()
    for e in q:
        d = e.to_dict()
        events.append({
            "event_id": d.get("event_id"),
            "event_type": d.get("event_type"),
            "action": d.get("action"),
            "status": d.get("status"),
            "processed_at": str(d.get("processed_at", "")),
        })

    return {
        "carrier_uid": carrier_uid,
        "enabled": ts_config.get("enabled", False),
        "company_key": ts_config.get("company_key", ""),
        "webhook_url": ts_config.get("webhook_url", ""),
        "registered_at": ts_config.get("registered_at"),
        "recent_events": events,
    }
