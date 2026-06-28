"""
Users Admin routes — manage drivers, attorneys, carriers, and case financials.
All endpoints require x-api-key header.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
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
    return {k: (_ts(v) if (hasattr(v, "isoformat") or (v is not None and hasattr(v, "tzinfo"))) else v)
            for k, v in data.items()}


# ── KPI Dashboard ──────────────────────────────────────────────────────────────

@router.get("/admin/kpi")
def get_kpi(x_api_key: Optional[str] = Header(None)):
    """Business KPI summary for the control panel dashboard."""
    _check_auth(x_api_key)
    db = _db()
    try:
        drivers     = list(db.collection("drivers").stream())
        carriers    = list(db.collection("carriers").stream())
        attorneys   = list(db.collection("attorneys").stream())
        tickets     = list(db.collection("tickets").stream())
        cases       = list(db.collection("cases").stream())

        ticket_statuses: dict = {}
        for t in tickets:
            s = t.to_dict().get("attorney_status", "Unknown")
            ticket_statuses[s] = ticket_statuses.get(s, 0) + 1

        case_statuses: dict = {}
        pending_payouts = 0
        for c in cases:
            d = c.to_dict()
            s = d.get("status", "Unknown")
            case_statuses[s] = case_statuses.get(s, 0) + 1
            if d.get("status") == "outcome_logged" and not d.get("payout_sent"):
                pending_payouts += 1

        return {
            "drivers": {
                "total": len(drivers),
                "active_memberships": sum(
                    1 for d in drivers if d.to_dict().get("subscription_status") == "active"
                ),
            },
            "carriers": {
                "total": len(carriers),
                "active": sum(1 for c in carriers if c.to_dict().get("status") == "active"),
            },
            "attorneys": {
                "total": len(attorneys),
                "active": sum(1 for a in attorneys if a.to_dict().get("status") == "active"),
                "pending_approval": sum(1 for a in attorneys if a.to_dict().get("status") == "pending"),
            },
            "tickets": {"total": len(tickets), "by_status": ticket_statuses},
            "cases": {
                "total": len(cases),
                "by_status": case_statuses,
                "pending_payouts": pending_payouts,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Drivers ────────────────────────────────────────────────────────────────────

@router.get("/admin/drivers")
def list_drivers(x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        docs = list(db.collection("drivers").stream())
        drivers = [{"driver_id": d.id, **_serialize(d.to_dict())} for d in docs]
        drivers.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"drivers": drivers, "total": len(drivers)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/admin/drivers/{driver_id}")
def get_driver(driver_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        ref = db.collection("drivers").document(driver_id)
        doc = ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found.")
        data = _serialize(doc.to_dict())

        sub_tickets = [
            {"ticket_id": t.id, **_serialize(t.to_dict())}
            for t in ref.collection("tickets").stream()
        ]
        top_tickets = [
            {"ticket_id": t.id, **_serialize(t.to_dict())}
            for t in db.collection("tickets").where("driver_id", "==", driver_id).stream()
        ]
        top_tickets.sort(key=lambda x: x.get("created_at") or "", reverse=True)

        return {"driver_id": driver_id, **data, "tickets": sub_tickets, "all_tickets": top_tickets}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class CreateDriverBody(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    cdl_number: Optional[str] = None
    cdl_class: Optional[str] = None
    dob: Optional[str] = None
    state: Optional[str] = None
    carrier_id: Optional[str] = None
    membership_tier: str = "silver"
    subscription_status: str = "active"
    notes: Optional[str] = None


@router.post("/admin/drivers")
def create_driver(body: CreateDriverBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        driver_id = str(uuid.uuid4())
        db.collection("drivers").document(driver_id).set({
            **body.model_dump(),
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })
        logger.warning("[users_admin] created driver=%s name=%s", driver_id, body.full_name)
        return {"success": True, "driver_id": driver_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class UpdateDriverBody(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cdl_number: Optional[str] = None
    cdl_class: Optional[str] = None
    dob: Optional[str] = None
    state: Optional[str] = None
    carrier_id: Optional[str] = None
    membership_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    notes: Optional[str] = None


@router.put("/admin/drivers/{driver_id}")
def update_driver(driver_id: str, body: UpdateDriverBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        ref = db.collection("drivers").document(driver_id)
        if not ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found.")
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
        updates["updated_at"] = SERVER_TIMESTAMP
        ref.update(updates)
        return {"success": True, "driver_id": driver_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Attorneys Management ───────────────────────────────────────────────────────

@router.get("/admin/attorneys-mgmt")
def list_attorneys_mgmt(x_api_key: Optional[str] = Header(None)):
    """List all attorneys (any status) for admin management."""
    _check_auth(x_api_key)
    db = _db()
    try:
        docs = list(db.collection("attorneys").stream())
        attorneys = [{"attorney_id": d.id, **_serialize(d.to_dict())} for d in docs]
        status_order = {"pending": 0, "active": 1, "inactive": 2, "removed": 3}
        attorneys.sort(key=lambda a: (status_order.get(a.get("status", ""), 9), a.get("full_name", "")))
        return {"attorneys": attorneys, "total": len(attorneys)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class CreateAttorneyBody(BaseModel):
    full_name: str
    firm_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    states_licensed: List[str] = []
    counties_covered: List[str] = []
    max_active_cases: int = 10
    preferred_contact_method: str = "phone"
    tier: Optional[str] = None
    fee_structure: Optional[str] = None
    notes: Optional[str] = None
    status: str = "pending"


@router.post("/admin/attorneys-mgmt")
def create_attorney(body: CreateAttorneyBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        attorney_id = str(uuid.uuid4())
        db.collection("attorneys").document(attorney_id).set({
            **body.model_dump(),
            "win_rate": None,
            "cases_active": 0,
            "cases_total": 0,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })
        return {"success": True, "attorney_id": attorney_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class UpdateAttorneyBody(BaseModel):
    full_name: Optional[str] = None
    firm_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    states_licensed: Optional[List[str]] = None
    counties_covered: Optional[List[str]] = None
    max_active_cases: Optional[int] = None
    preferred_contact_method: Optional[str] = None
    tier: Optional[str] = None
    fee_structure: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


@router.put("/admin/attorneys-mgmt/{attorney_id}")
def update_attorney(attorney_id: str, body: UpdateAttorneyBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        ref = db.collection("attorneys").document(attorney_id)
        if not ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Attorney {attorney_id} not found.")
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
        updates["updated_at"] = SERVER_TIMESTAMP
        ref.update(updates)
        return {"success": True, "attorney_id": attorney_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/admin/attorneys-mgmt/{attorney_id}")
def remove_attorney(attorney_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        ref = db.collection("attorneys").document(attorney_id)
        if not ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Attorney {attorney_id} not found.")
        ref.update({
            "status": "removed",
            "removed_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Carriers ───────────────────────────────────────────────────────────────────

@router.get("/admin/carriers")
def list_carriers(x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        docs = list(db.collection("carriers").stream())
        carriers = [{"carrier_id": d.id, **_serialize(d.to_dict())} for d in docs]
        status_order = {"pending": 0, "active": 1, "inactive": 2, "removed": 3}
        carriers.sort(key=lambda c: (status_order.get(c.get("status", ""), 9), c.get("company_name", "")))
        return {"carriers": carriers, "total": len(carriers)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class CreateCarrierBody(BaseModel):
    company_name: str
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    contact_name: str
    contact_email: str
    contact_phone: Optional[str] = None
    state: Optional[str] = None
    driver_count: int = 0
    notes: Optional[str] = None
    status: str = "pending"


@router.post("/admin/carriers")
def create_carrier(body: CreateCarrierBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        carrier_id = str(uuid.uuid4())
        db.collection("carriers").document(carrier_id).set({
            **body.model_dump(),
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })
        return {"success": True, "carrier_id": carrier_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class UpdateCarrierBody(BaseModel):
    company_name: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    state: Optional[str] = None
    driver_count: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None


@router.put("/admin/carriers/{carrier_id}")
def update_carrier(carrier_id: str, body: UpdateCarrierBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        ref = db.collection("carriers").document(carrier_id)
        if not ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Carrier {carrier_id} not found.")
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
        updates["updated_at"] = SERVER_TIMESTAMP
        ref.update(updates)
        return {"success": True, "carrier_id": carrier_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/admin/carriers/{carrier_id}")
def remove_carrier(carrier_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    try:
        ref = db.collection("carriers").document(carrier_id)
        if not ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Carrier {carrier_id} not found.")
        ref.update({
            "status": "removed",
            "removed_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Case Fees & Payouts ────────────────────────────────────────────────────────

class UpdateFeesBody(BaseModel):
    attorney_fee_amount: Optional[float] = None
    fee_notes: Optional[str] = None
    updated_by: str


@router.put("/admin/cases/{case_id}/fees")
def update_case_fees(case_id: str, body: UpdateFeesBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        ref = db.collection("cases").document(case_id)
        if not ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
        updates: dict = {"last_updated_by": body.updated_by, "last_updated_at": SERVER_TIMESTAMP}
        if body.attorney_fee_amount is not None:
            updates["attorney_fee_amount"] = body.attorney_fee_amount
        if body.fee_notes is not None:
            updates["fee_notes"] = body.fee_notes
        ref.update(updates)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class PayoutBody(BaseModel):
    payout_amount: float
    payout_method: Optional[str] = "bank_transfer"
    payout_notes: Optional[str] = None
    paid_by: str


@router.post("/admin/cases/{case_id}/payout")
def record_payout(case_id: str, body: PayoutBody, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    try:
        ref = db.collection("cases").document(case_id)
        case_doc = ref.get()
        if not case_doc.exists:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
        old_status = case_doc.to_dict().get("status", "")
        ref.update({
            "status": "payout_sent",
            "payout_sent": True,
            "payout_amount": body.payout_amount,
            "payout_method": body.payout_method,
            "payout_notes": body.payout_notes,
            "payout_sent_at": SERVER_TIMESTAMP,
            "payout_sent_by": body.paid_by,
            "last_updated_by": body.paid_by,
            "last_updated_at": SERVER_TIMESTAMP,
        })
        activity_id = str(uuid.uuid4())
        ref.collection("activity").document(activity_id).set({
            "type": "payout_created",
            "note": f"Payout of ${body.payout_amount:.2f} sent via {body.payout_method}. {body.payout_notes or ''}".strip(),
            "old_status": old_status,
            "new_status": "payout_sent",
            "created_by": body.paid_by,
            "created_by_name": body.paid_by,
            "created_at": SERVER_TIMESTAMP,
        })
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
