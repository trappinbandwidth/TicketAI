"""
Carrier self-serve portal — folded in from the standalone carrier backend (:8090)
so the platform exposes one API. All routes live under /api/v1/carrier/*.

  POST  /carrier/register                      Bootstrap carrier profile + role claim (verify_token only).
  GET   /carrier/me                            Own company profile.
  PATCH /carrier/me                            Update own company profile.
  GET   /carrier/drivers                       Roster list (?include_fired=true).
  POST  /carrier/drivers                       Add one driver.
  POST  /carrier/drivers/bulk                  Validate-then-commit bulk add (≤1000).
  PATCH /carrier/drivers/{id}                  Update driver fields.
  PATCH /carrier/drivers/{id}/toggle-active    Enable/disable (blocked for fired).
  POST  /carrier/drivers/{id}/fire             Soft-remove; history kept.
  GET   /carrier/drivers/{id}/profile          Driver + their tickets (shadow-compared).
  GET   /carrier/drivers/{id}/tickets          Tickets only.
  GET   /carrier/fmcsa/safety                  Cached FMCSA record for own DOT.
  GET   /carrier/subscription                  Status + active-driver count + estimate.
  GET   /carrier/notifications                 Latest 50 (?unread_only=true).
  POST  /carrier/notifications/{id}/read       Mark read.
  GET   /carrier/billing                       Billing profile fields (read-only).
  GET   /carrier/documents                     Company document list.
  POST  /carrier/documents                     Upload (≤20 MB) to Firebase Storage.
  GET   /carrier/documents/{id}/download       15-min signed URL.

Data model is unchanged from the standalone service: carriers/{uid} keyed by the
carrier's own Firebase uid, with drivers/notifications/documents subcollections.
(The staff CRM in carriers_crm.py tracks prospect carriers by DOT number in the
same collection — mixed keying is pre-existing and resolved by the canonical
records migration, not here.)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from firebase_admin import storage
from google.api_core.exceptions import AlreadyExists
from pydantic import BaseModel

from app.platform.service import (
    PlatformService,
    organization_id_for_profile,
    principal_id_for_uid,
)
from app.platform.shadow_service import shadow_authorization, shadow_enabled
from app.routes._common import get_db, iso, verify_token
from app.services.auth_rbac import require_carrier

router = APIRouter(prefix="/carrier", tags=["carrier-portal"])


def _rate_cents(data: dict) -> Optional[int]:
    value = data.get("per_driver_rate_cents")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _carrier(authorization: Optional[str]):
    decoded = require_carrier(verify_token(authorization))
    db = get_db()
    return decoded, db, db.collection("carriers").document(decoded["uid"])


def _bucket():
    name = os.getenv("FIREBASE_STORAGE_BUCKET") or (
        f'{os.getenv("FIREBASE_PROJECT_ID", "rigresolve")}.firebasestorage.app'
    )
    return storage.bucket(name)


# ── Company profile ───────────────────────────────────────────────────────────

class CarrierRegistration(BaseModel):
    company_name: str
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    phone: Optional[str] = None


class CarrierProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    billing_email: Optional[str] = None
    website: Optional[str] = None
    point_of_contact_name: Optional[str] = None
    point_of_contact_title: Optional[str] = None
    point_of_contact_email: Optional[str] = None
    point_of_contact_phone: Optional[str] = None
    main_admin_name: Optional[str] = None
    main_admin_email: Optional[str] = None
    main_admin_phone: Optional[str] = None
    dispatch_phone: Optional[str] = None
    safety_phone: Optional[str] = None
    total_driver_count: Optional[int] = None
    employee_driver_count: Optional[int] = None
    contractor_driver_count: Optional[int] = None
    owner_operator_count: Optional[int] = None
    fleet_locations: Optional[list[str]] = None
    billing_type: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_zip_code: Optional[str] = None


def _normalized_dot(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return None
    if len(digits) > 8:
        raise HTTPException(status_code=422, detail="Enter a valid USDOT number.")
    return digits


def _claim_dot_number(db, uid: str, dot_number: Optional[str]) -> str:
    """Atomically reserve a self-service USDOT claim without merging tenants."""
    if not dot_number:
        return "not_provided"
    claim_ref = db.collection("carrier_dot_claims").document(dot_number)
    try:
        claim_ref.create({
            "dot_number": dot_number,
            "claimant_carrier_id": uid,
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc),
        })
        return "pending_review"
    except AlreadyExists:
        existing = claim_ref.get()
        owner = (existing.to_dict() or {}).get("claimant_carrier_id") if existing.exists else None
        if owner == uid:
            return (existing.to_dict() or {}).get("status", "pending_review")
        if owner:
            db.collection("carriers").document(owner).set({
                "dot_claim_status": "duplicate_disputed",
                "tenant_status": "quarantined",
                "updated_at": datetime.now(timezone.utc),
            }, merge=True)
            db.collection("organizations").document(
                organization_id_for_profile("carrier", owner)
            ).set({
                "tenant_status": "quarantined",
                "updated_at": datetime.now(timezone.utc),
            }, merge=True)
        return "duplicate_disputed"


def _record_acquisition_event(db, principal_id: str, event_type: str) -> None:
    """Store one privacy-minimized, idempotent first-party funnel event."""
    event_id = f"{event_type}_{principal_id}"
    try:
        db.collection("acquisition_events").document(event_id).create({
            "event_id": event_id,
            "event_type": event_type,
            "principal_id": principal_id,
            "funnel": "carrier_self_service_pilot",
            "created_at": datetime.now(timezone.utc),
        })
    except AlreadyExists:
        pass


def _ensure_carrier_foundation(db, decoded: dict, profile: dict) -> tuple[str, str]:
    """Repair-safe canonical identity, organization, audit, funnel, and claims."""
    uid = decoded["uid"]
    principal_id = principal_id_for_uid(uid)
    organization_id = organization_id_for_profile("carrier", uid)
    claims = {**decoded, "role": "carrier"}
    platform = PlatformService(db)
    platform.bootstrap_principal(claims)
    platform.bootstrap_role_organization(claims)
    now = datetime.now(timezone.utc)
    tenant_status = profile.get("tenant_status", "pending")
    db.collection("organizations").document(organization_id).set({
        "verification_status": profile.get("verification_status", "unverified"),
        "tenant_status": tenant_status,
        "updated_at": now,
    }, merge=True)
    audit_id = f"audit_carrier_registration_{principal_id}"
    try:
        db.collection("audit_events").document(audit_id).create({
            "id": audit_id,
            "event_type": "carrier.self_service_registered",
            "actor_id": principal_id,
            "entity_type": "organization",
            "entity_id": organization_id,
            "payload": {
                "dot_claim_status": profile.get("dot_claim_status", "not_provided"),
                "tenant_status": tenant_status,
            },
            "version": "1.0",
            "created_at": now.isoformat(),
        })
    except AlreadyExists:
        pass
    _record_acquisition_event(db, principal_id, "account_created")
    _record_acquisition_event(db, principal_id, "email_verified")
    _record_acquisition_event(db, principal_id, "carrier_profile_completed")
    fb_auth.set_custom_user_claims(uid, {
        "role": "carrier",
        "carrier_id": uid,
        "organization_id": organization_id,
    })
    return principal_id, organization_id


@router.post("/register")
def register_carrier(body: CarrierRegistration, authorization: Optional[str] = Header(None)):
    """Create the caller's isolated Carrier tenant after verified email signup."""
    decoded = verify_token(authorization)
    uid = decoded["uid"]
    role = decoded.get("role")
    if role and role != "carrier":
        raise HTTPException(status_code=403, detail="This account already has a different portal role.")
    if not decoded.get("email") or decoded.get("email_verified") is not True:
        raise HTTPException(status_code=403, detail="Verify your email before creating a Carrier workspace.")

    db = get_db()
    ref = db.collection("carriers").document(uid)
    if ref.get().exists:
        existing = ref.get().to_dict() or {}
        _, organization_id = _ensure_carrier_foundation(db, decoded, existing)
        return {
            "ok": True,
            "carrier_id": uid,
            "organization_id": organization_id,
            "dot_claim_status": existing.get("dot_claim_status", "not_provided"),
            "tenant_status": existing.get("tenant_status", "pending"),
            "already_registered": True,
            "token_refresh_required": role != "carrier",
        }

    company_name = " ".join(body.company_name.split())
    if not company_name:
        raise HTTPException(status_code=422, detail="Company name is required.")
    dot_number = _normalized_dot(body.dot_number)
    organization_id = organization_id_for_profile("carrier", uid)
    principal_id = principal_id_for_uid(uid)
    dot_claim_status = _claim_dot_number(db, uid, dot_number)
    tenant_status = "quarantined" if dot_claim_status == "duplicate_disputed" else "pending"
    now = datetime.now(timezone.utc)
    ref.set({
        **body.model_dump(),
        "company_name": company_name,
        "dot_number": dot_number,
        "email": decoded.get("email"),
        "email_verified": True,
        "principal_id": principal_id,
        "organization_id": organization_id,
        "verification_status": "unverified",
        "dot_claim_status": dot_claim_status,
        "tenant_status": tenant_status,
        "subscription_status": "trial",
        "created_at": now,
        "updated_at": now,
    })
    _ensure_carrier_foundation(db, decoded, {
        "verification_status": "unverified",
        "dot_claim_status": dot_claim_status,
        "tenant_status": tenant_status,
    })
    return {
        "ok": True,
        "carrier_id": uid,
        "organization_id": organization_id,
        "dot_claim_status": dot_claim_status,
        "tenant_status": tenant_status,
        "already_registered": False,
        "token_refresh_required": True,
    }


@router.get("/me")
def get_my_carrier_profile(authorization: Optional[str] = Header(None)):
    decoded, _, ref = _carrier(authorization)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Carrier profile not found.")
    data = snap.to_dict()
    data["carrier_id"] = snap.id
    for k in ("created_at", "updated_at"):
        if k in data:
            data[k] = iso(data[k])
    return data


@router.patch("/me")
def update_my_carrier_profile(body: CarrierProfileUpdate, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    patch["updated_at"] = datetime.now(timezone.utc)
    ref.set(patch, merge=True)
    return {"ok": True, "updated": list(patch.keys())}


# ── Driver roster ─────────────────────────────────────────────────────────────

class DriverCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    cdl_number: Optional[str] = None
    cdl_state: Optional[str] = None
    dob: Optional[str] = None
    med_cert_expiration: Optional[str] = None
    employment_type: Optional[str] = None
    home_terminal: Optional[str] = None
    subscription_start_date: Optional[str] = None
    psp_status: Optional[str] = None
    mvr_status: Optional[str] = None


class DriverUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cdl_number: Optional[str] = None
    cdl_state: Optional[str] = None
    dob: Optional[str] = None
    med_cert_expiration: Optional[str] = None
    employment_type: Optional[str] = None
    home_terminal: Optional[str] = None
    subscription_start_date: Optional[str] = None
    psp_status: Optional[str] = None
    mvr_status: Optional[str] = None


class BulkDriverCreate(BaseModel):
    drivers: list[DriverCreate]


def _driver_out(doc) -> dict:
    d = doc.to_dict()
    d["driver_id"] = doc.id
    for k in ("created_at", "updated_at", "fired_at"):
        if d.get(k) is not None:
            d[k] = iso(d[k])
    return d


@router.get("/drivers")
def list_drivers(include_fired: bool = False, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    drivers = [_driver_out(d) for d in ref.collection("drivers").stream()]
    if not include_fired:
        drivers = [d for d in drivers if not d.get("fired_at")]
    return {"drivers": drivers, "count": len(drivers)}


@router.post("/drivers")
def create_driver(body: DriverCreate, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    now = datetime.now(timezone.utc)
    doc = ref.collection("drivers").document()
    doc.set({**body.model_dump(), "active": True, "fired_at": None,
             "created_at": now, "updated_at": now})
    return {"ok": True, "driver_id": doc.id}


@router.post("/drivers/bulk")
def bulk_create_drivers(body: BulkDriverCreate, authorization: Optional[str] = Header(None)):
    """Validate the complete payload before committing any row."""
    _, db, ref = _carrier(authorization)
    if not body.drivers or len(body.drivers) > 1000:
        raise HTTPException(status_code=400, detail="Upload between 1 and 1,000 drivers at a time.")
    seen: set[tuple[str, str]] = set()
    errors = []
    for row, driver in enumerate(body.drivers, start=2):
        key = ((driver.cdl_state or "").strip().upper(), (driver.cdl_number or "").strip().upper())
        if not driver.first_name.strip() or not driver.last_name.strip():
            errors.append({"row": row, "message": "First and last name are required."})
        if key[1] and key in seen:
            errors.append({"row": row, "message": "Duplicate CDL number in this file."})
        seen.add(key)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "No drivers were imported.", "errors": errors})
    roster = ref.collection("drivers")
    now = datetime.now(timezone.utc)
    batch = db.batch()
    ids = []
    for driver in body.drivers:
        doc = roster.document()
        data = driver.model_dump()
        data["cdl_state"] = (data.get("cdl_state") or "").upper() or None
        batch.set(doc, {**data, "active": True, "fired_at": None, "created_at": now, "updated_at": now})
        ids.append(doc.id)
    batch.commit()
    return {"ok": True, "created": len(ids), "driver_ids": ids}


@router.patch("/drivers/{driver_id}")
def update_driver(driver_id: str, body: DriverUpdate, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    doc = ref.collection("drivers").document(driver_id)
    if not doc.get().exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    patch["updated_at"] = datetime.now(timezone.utc)
    doc.set(patch, merge=True)
    return {"ok": True, "updated": list(patch.keys())}


@router.patch("/drivers/{driver_id}/toggle-active")
def toggle_driver_active(driver_id: str, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    doc = ref.collection("drivers").document(driver_id)
    snap = doc.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    if snap.to_dict().get("fired_at"):
        raise HTTPException(status_code=400, detail="Cannot toggle a fired driver — re-add them instead.")
    new_active = not snap.to_dict().get("active", True)
    doc.update({"active": new_active, "updated_at": datetime.now(timezone.utc)})
    return {"ok": True, "active": new_active}


@router.post("/drivers/{driver_id}/fire")
def fire_driver(driver_id: str, authorization: Optional[str] = Header(None)):
    """Soft-remove — keeps the record (and ticket/MVR history) intact."""
    _, _, ref = _carrier(authorization)
    doc = ref.collection("drivers").document(driver_id)
    if not doc.get().exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    now = datetime.now(timezone.utc)
    doc.update({"active": False, "fired_at": now, "updated_at": now})
    return {"ok": True, "fired_at": iso(now)}


@router.get("/drivers/{driver_id}/profile")
def driver_profile(driver_id: str, authorization: Optional[str] = Header(None)):
    decoded, db, ref = _carrier(authorization)
    snap = ref.collection("drivers").document(driver_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    driver = snap.to_dict()
    driver["driver_id"] = snap.id
    if shadow_enabled():
        carrier_doc = ref.get().to_dict() or {}
        shadow_authorization(
            db, decoded,
            legacy_allowed=True,
            legacy_reason="carrier_roster_ownership",
            action="read",
            resource_type="driver_profile",
            resource_id=driver_id,
            tenant_id=carrier_doc.get("organization_id"),
            purpose="safety_compliance",
            record_category="driver_profile",
            subject_principal_id=driver.get("principal_id"),
        )
    tickets = [dict(t.to_dict(), ticket_id=t.id)
               for t in db.collection("tickets").where("driver_id", "==", driver_id).stream()]
    return {"driver": driver, "tickets": tickets, "ticket_count": len(tickets),
            "open_ticket_count": sum(1 for t in tickets
                                     if t.get("attorney_status") not in ("Ticket Closed", "Rejected"))}


@router.get("/drivers/{driver_id}/tickets")
def driver_tickets(driver_id: str, authorization: Optional[str] = Header(None)):
    profile = driver_profile(driver_id, authorization)
    return {"driver_id": driver_id, "tickets": profile["tickets"], "count": profile["ticket_count"]}


# ── FMCSA / subscription / notifications / billing ──────────────────────────

@router.get("/fmcsa/safety")
def fmcsa_safety(authorization: Optional[str] = Header(None)):
    decoded, db, ref = _carrier(authorization)
    profile = ref.get().to_dict() or {}
    dot = str(profile.get("dot_number") or "").strip()
    if not dot:
        return {"status": "missing_dot", "message": "Add a USDOT number to your carrier profile."}
    snap = db.collection("carriers").document(dot).get()
    if not snap.exists:
        matches = list(db.collection("carriers").where("dot_number", "==", dot).limit(2).stream())
        snap = next((item for item in matches if item.id != decoded["uid"]), None)
    if not snap or not snap.exists:
        return {"status": "not_found", "dot_number": dot,
                "message": "No cached FMCSA record was found for this USDOT number."}
    raw = snap.to_dict() or {}
    updated = raw.get("fmcsa_updated_at") or raw.get("updated_at") or raw.get("last_modified")
    return {"status": "ready", "source": "FMCSA cached database", "dot_number": dot,
            "last_updated": iso(updated) if updated else None,
            "carrier": {k: raw.get(k) for k in (
                "legal_name", "dba_name", "operating_status", "power_units", "driver_count",
                "inspection_count", "violation_count", "crash_count", "oos_status", "oos_date", "oos_reason")},
            "basics": raw.get("basics") or raw.get("sms_basics") or [],
            "inspections": raw.get("inspections") or []}


@router.get("/subscription")
def subscription(authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    data = ref.get().to_dict() or {}
    count = sum(1 for d in ref.collection("drivers").stream()
                if d.to_dict().get("active", True) and not d.to_dict().get("fired_at"))
    rate_cents = _rate_cents(data)
    return {"status": data.get("subscription_status", "trial"), "active_drivers": count,
            "per_driver_rate_cents": rate_cents,
            "estimated_monthly_cents": rate_cents * count if rate_cents is not None else None,
            "pricing_data_status": (
                "ready" if rate_cents is not None
                else "legacy_unit_unresolved" if data.get("per_driver_rate") is not None
                else "pending"
            ),
            "self_serve_eligible": count <= 50, "special_pricing_required": count >= 51}


@router.get("/notifications")
def notifications(unread_only: bool = False, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    items = []
    for snap in ref.collection("notifications").stream():
        data = snap.to_dict()
        data["notification_id"] = snap.id
        if data.get("created_at"):
            data["created_at"] = iso(data["created_at"])
        if not unread_only or not data.get("read", False):
            items.append(data)
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return {"notifications": items[:50],
            "unread_count": sum(1 for item in items if not item.get("read", False))}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    note = ref.collection("notifications").document(notification_id)
    if not note.get().exists:
        raise HTTPException(status_code=404, detail="Notification not found.")
    note.set({"read": True, "read_at": datetime.now(timezone.utc)}, merge=True)
    return {"ok": True}


@router.get("/billing")
def billing(authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    data = ref.get().to_dict() or {}
    allowed = ("billing_type", "billing_contact_name", "billing_email", "billing_phone",
               "billing_address", "billing_city", "billing_state", "billing_zip_code",
               "payment_method_brand", "payment_method_last4", "payment_method_status",
               "per_driver_rate_cents", "subscription_status")
    return {key: data.get(key) for key in allowed}


# ── Company documents ─────────────────────────────────────────────────────────

@router.get("/documents")
def list_documents(authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    docs = []
    for snap in ref.collection("documents").stream():
        data = snap.to_dict()
        data["document_id"] = snap.id
        if data.get("created_at"):
            data["created_at"] = iso(data["created_at"])
        docs.append(data)
    docs.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    return {"documents": docs, "count": len(docs)}


@router.post("/documents")
async def upload_document(file: UploadFile = File(...), category: str = Form(...),
                          name: str = Form(...), authorization: Optional[str] = Header(None)):
    decoded, _, ref = _carrier(authorization)
    content = await file.read()
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Files must be between 1 byte and 20 MB.")
    path = f"carriers/{decoded['uid']}/documents/{uuid4().hex}_{file.filename or 'document'}"
    _bucket().blob(path).upload_from_string(content, content_type=file.content_type)
    now = datetime.now(timezone.utc)
    doc = ref.collection("documents").document()
    doc.set({"name": name.strip(), "category": category, "file_name": file.filename,
             "storage_path": path, "content_type": file.content_type,
             "size_bytes": len(content), "created_at": now, "uploaded_by": decoded["uid"]})
    return {"ok": True, "document_id": doc.id, "created_at": iso(now)}


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    snap = ref.collection("documents").document(document_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Document not found.")
    url = _bucket().blob(snap.to_dict()["storage_path"]).generate_signed_url(
        version="v4", expiration=900, method="GET")
    return {"url": url, "expires_in": 900}
