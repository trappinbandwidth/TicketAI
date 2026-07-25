"""
Carrier self-serve portal — folded in from the standalone carrier backend (:8090)
so the platform exposes one API. All routes live under /api/v1/carrier/*.

  POST  /carrier/register                      Bootstrap carrier profile + role claim (verify_token only).
  GET   /carrier/me                            Own company profile.
  PATCH /carrier/me                            Update own company profile.
  GET   /carrier/drivers                       Roster list (?include_fired=true).
  POST  /carrier/drivers                       Add one driver.
  POST  /carrier/drivers/bulk                  Validate-then-commit bulk add (≤100).
  PATCH /carrier/drivers/{id}                  Update driver fields.
  PATCH /carrier/drivers/{id}/toggle-active    Enable/disable (blocked for fired).
  POST  /carrier/drivers/{id}/fire             Soft-remove; history kept.
  GET   /carrier/drivers/{id}/profile          Roster or consent-limited safety summary.
  GET   /carrier/drivers/{id}/tickets          Denied: safety consent excludes legal cases.
  GET   /carrier/relationships                 Consented Driver relationship list.
  POST  /carrier/relationships/connect         Consume Driver one-time connection code.
  POST  /carrier/relationships/{id}/end        End relationship; access stops immediately.
  GET   /carrier/fmcsa/safety                  Cached FMCSA record for own DOT.
  GET   /carrier/subscription                  Status + active-driver count + estimate.
  GET   /carrier/notifications                 Latest 50 (?unread_only=true).
  POST  /carrier/notifications/{id}/read       Mark read.
  GET   /carrier/billing                       Billing profile fields (read-only).
  GET   /carrier/documents                     Company document list.
  POST  /carrier/documents                     Upload (≤20 MB) to Firebase Storage.
  GET   /carrier/documents/{id}/download       15-min signed URL.

Legacy Carrier data remains under carriers/{uid}, with drivers, notifications,
and documents subcollections. New cross-role relationship notifications use
principal_notifications with recipient-principal ownership. (The staff CRM in
carriers_crm.py tracks prospect carriers by DOT number in the same collection —
mixed keying is pre-existing and resolved by the canonical records migration,
not here.)
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from firebase_admin import storage
from google.api_core.exceptions import Aborted, AlreadyExists, FailedPrecondition
from google.cloud.firestore_v1 import LastUpdateOption
from pydantic import BaseModel, Field, model_validator

from app.platform.service import (
    PlatformService,
    organization_id_for_profile,
    principal_id_for_uid,
)
from app.platform.models import DriverCarrierRelationshipCreate
from app.platform.documents import validate_upload
from app.routes._common import get_db, iso, verify_token
from app.services.auth_rbac import require_carrier
from app.services.carrier_resolve import CarrierResolveService
from app.services.carrier_lookup import (
    carrier_discovery_detail,
    search_carriers,
)

router = APIRouter(prefix="/carrier", tags=["carrier-portal"])

# Pre-signup funnel events are anonymous (no principal exists yet), so they are
# keyed by a salted hash of a client-generated visit id — never a raw client
# identifier, IP, or PII. Only these two pre-account steps are accepted from the
# open endpoint; the authenticated steps are recorded from their own verified
# server actions so an unauthenticated caller cannot inflate them.
_ACQUISITION_SALT = os.getenv("CARRIER_ACQUISITION_SALT", "tip-os-carrier-pilot")
_ANONYMOUS_FUNNEL_EVENTS = frozenset({"signup_viewed", "signup_started"})


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
        f'{os.getenv("FIREBASE_PROJECT_ID", "rigresolve")}.appspot.com'
    )
    return storage.bucket(name)


# ── Company profile ───────────────────────────────────────────────────────────

class CarrierRegistration(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    dot_number: Optional[str] = Field(default=None, max_length=24)
    mc_number: Optional[str] = Field(default=None, max_length=40)
    phone: Optional[str] = Field(default=None, max_length=32)
    selected_fmcsa_dot_number: Optional[str] = Field(default=None, max_length=24)
    fmcsa_record_confirmed: bool = False


class CarrierProfileUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, max_length=200)
    dot_number: Optional[str] = Field(default=None, max_length=24)
    mc_number: Optional[str] = Field(default=None, max_length=40)
    phone: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    zip_code: Optional[str] = Field(default=None, pattern=r"^\d{5}(?:-\d{4})?$")
    billing_email: Optional[str] = Field(
        default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    website: Optional[str] = Field(default=None, max_length=500)
    point_of_contact_name: Optional[str] = Field(default=None, max_length=160)
    point_of_contact_title: Optional[str] = Field(default=None, max_length=120)
    point_of_contact_email: Optional[str] = Field(
        default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    point_of_contact_phone: Optional[str] = Field(default=None, max_length=32)
    main_admin_name: Optional[str] = Field(default=None, max_length=160)
    main_admin_email: Optional[str] = Field(
        default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    main_admin_phone: Optional[str] = Field(default=None, max_length=32)
    dispatch_phone: Optional[str] = Field(default=None, max_length=32)
    safety_phone: Optional[str] = Field(default=None, max_length=32)
    total_driver_count: Optional[int] = Field(default=None, ge=0, le=100_000)
    employee_driver_count: Optional[int] = Field(default=None, ge=0, le=100_000)
    contractor_driver_count: Optional[int] = Field(default=None, ge=0, le=100_000)
    owner_operator_count: Optional[int] = Field(default=None, ge=0, le=100_000)
    fleet_locations: Optional[list[str]] = Field(default=None, max_length=100)
    billing_type: Optional[str] = Field(default=None, max_length=80)
    billing_contact_name: Optional[str] = Field(default=None, max_length=160)
    billing_phone: Optional[str] = Field(default=None, max_length=32)
    billing_address: Optional[str] = Field(default=None, max_length=200)
    billing_city: Optional[str] = Field(default=None, max_length=100)
    billing_state: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    billing_zip_code: Optional[str] = Field(
        default=None, pattern=r"^\d{5}(?:-\d{4})?$"
    )


class AuthorityEvidenceMethod(str, Enum):
    MCS150 = "mcs150"
    OPERATING_AUTHORITY = "operating_authority"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    EIN_LETTER = "ein_letter"
    STATE_REGISTRATION = "state_registration"
    AUTHORIZATION_LETTER = "authorization_letter"
    OTHER = "other"


def _normalized_dot(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return None
    if len(digits) > 8:
        raise HTTPException(status_code=422, detail="Enter a valid USDOT number.")
    return digits


@router.get("/discovery/search")
def discover_carriers(
    q: str = Query(min_length=2, max_length=160),
    state: Optional[str] = Query(default=None, pattern=r"^[A-Za-z]{2}$"),
    limit: int = Query(default=10, ge=1, le=20),
):
    """Search the bounded local public FMCSA Carrier index before signup."""
    return {
        "carriers": search_carriers(q, state=state, limit=limit),
        "source": "FMCSA public motor-carrier authority data",
        "account_authority_proven": False,
    }


@router.get("/discovery/{dot_number}")
def discover_carrier(dot_number: str):
    """Review one public source record; selection grants no TIP access."""
    normalized = _normalized_dot(dot_number)
    record = carrier_discovery_detail(normalized or "")
    if record is None:
        raise HTTPException(status_code=404, detail="FMCSA Carrier record not found.")
    return {
        "carrier": record,
        "account_authority_proven": False,
        "claim_note": (
            "Selecting this public record does not prove authority over the Carrier "
            "or grant access to an existing TIP workspace."
        ),
    }


class AcquisitionFunnelEvent(BaseModel):
    """A pre-signup, first-party funnel event from an anonymous visitor."""

    event_type: str = Field(min_length=1, max_length=40)
    visit_id: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _only_pre_signup_events(self) -> "AcquisitionFunnelEvent":
        if self.event_type not in _ANONYMOUS_FUNNEL_EVENTS:
            raise ValueError("Only pre-signup funnel events are accepted here.")
        return self


@router.post("/acquisition/funnel", status_code=202)
def record_acquisition_funnel_event(body: AcquisitionFunnelEvent):
    """Record a privacy-minimized pre-signup funnel event (viewed / started).

    Open by design: these steps happen before an account exists, so ADR-010's
    "discover, start, and complete signup" measurement needs an unauthenticated
    entry point. It stores only a salted visitor hash, is idempotent per
    visitor+step, and rejects authenticated steps so it cannot inflate them.
    """
    visit_hash = hashlib.sha256(
        f"{_ACQUISITION_SALT}:{body.visit_id}".encode("utf-8")
    ).hexdigest()[:32]
    _record_anonymous_acquisition_event(get_db(), body.event_type, visit_hash)
    return {"ok": True}


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
            disputed_at = datetime.now(timezone.utc)
            claim_ref.set({
                "status": "duplicate_disputed",
                "updated_at": disputed_at,
            }, merge=True)
            db.collection("carriers").document(owner).set({
                "dot_claim_status": "duplicate_disputed",
                "tenant_status": "quarantined",
                "updated_at": disputed_at,
            }, merge=True)
            db.collection("organizations").document(
                organization_id_for_profile("carrier", owner)
            ).set({
                "tenant_status": "quarantined",
                "updated_at": disputed_at,
            }, merge=True)
            owner_authority_id = _authority_claim_id(owner, dot_number)
            owner_authority = (
                db.collection("carrier_authority_claims")
                .document(owner_authority_id)
            )
            if owner_authority.get().exists:
                owner_authority.set({
                    "status": "duplicate_disputed",
                    "dot_claim_status": "duplicate_disputed",
                    "updated_at": disputed_at,
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


def _record_anonymous_acquisition_event(db, event_type: str, visit_hash: str) -> None:
    """Idempotently store one pre-signup funnel event keyed by an anonymous
    visitor hash. No raw client identifier, IP, or PII is retained."""
    event_id = f"{event_type}_{visit_hash}"
    try:
        db.collection("acquisition_events").document(event_id).create({
            "event_id": event_id,
            "event_type": event_type,
            "principal_id": None,
            "visit_hash": visit_hash,
            "funnel": "carrier_self_service_pilot",
            "created_at": datetime.now(timezone.utc),
        })
    except AlreadyExists:
        pass


def _authority_claim_id(uid: str, dot_number: str) -> str:
    digest = hashlib.sha256(f"{uid}:{dot_number}".encode("utf-8")).hexdigest()[:32]
    return f"carrier_authority_{digest}"


def _ensure_authority_claim(
    db,
    uid: str,
    organization_id: str,
    dot_number: Optional[str],
    fmcsa_snapshot_id: Optional[str],
    dot_claim_status: str,
) -> Optional[str]:
    """Create the private verification queue item without implying authority."""
    if not dot_number:
        return None
    claim_id = _authority_claim_id(uid, dot_number)
    ref = db.collection("carrier_authority_claims").document(claim_id)
    now = datetime.now(timezone.utc)
    existing = ref.get()
    if existing.exists:
        current = existing.to_dict() or {}
        ref.set({
            "organization_id": organization_id,
            "fmcsa_snapshot_id": fmcsa_snapshot_id or current.get("fmcsa_snapshot_id"),
            "dot_claim_status": dot_claim_status,
            "updated_at": now,
        }, merge=True)
        return claim_id
    ref.create({
        "id": claim_id,
        "carrier_profile_id": uid,
        "organization_id": organization_id,
        "dot_number": dot_number,
        "fmcsa_snapshot_id": fmcsa_snapshot_id,
        "dot_claim_status": dot_claim_status,
        "status": (
            "duplicate_disputed"
            if dot_claim_status == "duplicate_disputed"
            else "pending_evidence"
        ),
        "evidence_ids": [],
        "created_at": now,
        "updated_at": now,
    })
    return claim_id


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
    _ensure_authority_claim(
        db,
        uid,
        organization_id,
        _normalized_dot(profile.get("dot_number")),
        profile.get("fmcsa_snapshot_id"),
        profile.get("dot_claim_status", "not_provided"),
    )
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
            "fmcsa_snapshot_id": existing.get("fmcsa_snapshot_id"),
            "account_authority_status": existing.get(
                "account_authority_status", "pending_verification"
            ),
            "already_registered": True,
            "token_refresh_required": role != "carrier",
        }

    company_name = " ".join(body.company_name.split())
    if not company_name:
        raise HTTPException(status_code=422, detail="Company name is required.")
    dot_number = _normalized_dot(body.dot_number)
    selected_dot = _normalized_dot(body.selected_fmcsa_dot_number)
    fmcsa_snapshot = None
    if selected_dot:
        if dot_number and dot_number != selected_dot:
            raise HTTPException(
                status_code=422,
                detail="The selected FMCSA record does not match the submitted USDOT number.",
            )
        if not body.fmcsa_record_confirmed:
            raise HTTPException(
                status_code=422,
                detail="Confirm that you reviewed the selected FMCSA record.",
            )
        fmcsa_snapshot = carrier_discovery_detail(selected_dot)
        if fmcsa_snapshot is None:
            raise HTTPException(
                status_code=409,
                detail="The selected FMCSA record is no longer available. Search again.",
            )
        dot_number = selected_dot
    organization_id = organization_id_for_profile("carrier", uid)
    principal_id = principal_id_for_uid(uid)
    dot_claim_status = _claim_dot_number(db, uid, dot_number)
    tenant_status = "quarantined" if dot_claim_status == "duplicate_disputed" else "pending"
    now = datetime.now(timezone.utc)
    snapshot_id = None
    if fmcsa_snapshot:
        snapshot_id = "fmcsa_" + hashlib.sha256(
            f"{uid}:{dot_number}".encode("utf-8")
        ).hexdigest()[:32]
        try:
            db.collection("carrier_fmcsa_snapshots").document(snapshot_id).create({
                "id": snapshot_id,
                "carrier_profile_id": uid,
                "organization_id": organization_id,
                "dot_number": dot_number,
                "record": fmcsa_snapshot,
                "selection_confirmation": "applicant_confirmed_record_match",
                "account_authority_proven": False,
                "captured_at": now,
            })
        except AlreadyExists:
            # A concurrent registration retry keeps the first source snapshot.
            pass
    ref.set({
        **body.model_dump(exclude={
            "selected_fmcsa_dot_number", "fmcsa_record_confirmed"
        }),
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
        "fmcsa_snapshot_id": snapshot_id,
        "fmcsa_match_status": (
            "applicant_confirmed_record_match" if snapshot_id else "not_selected"
        ),
        "account_authority_status": "pending_verification",
        "created_at": now,
        "updated_at": now,
    })
    _ensure_carrier_foundation(db, decoded, {
        "verification_status": "unverified",
        "dot_claim_status": dot_claim_status,
        "tenant_status": tenant_status,
        "dot_number": dot_number,
        "fmcsa_snapshot_id": snapshot_id,
    })
    return {
        "ok": True,
        "carrier_id": uid,
        "organization_id": organization_id,
        "dot_claim_status": dot_claim_status,
        "tenant_status": tenant_status,
        "fmcsa_snapshot_id": snapshot_id,
        "account_authority_status": "pending_verification",
        "already_registered": False,
        "token_refresh_required": True,
    }


def _authority_claim_for_carrier(db, uid: str) -> tuple[object, dict]:
    profile = db.collection("carriers").document(uid).get()
    if not profile.exists:
        raise HTTPException(status_code=404, detail="Carrier profile not found.")
    carrier = profile.to_dict() or {}
    dot_number = _normalized_dot(carrier.get("dot_number"))
    if not dot_number:
        raise HTTPException(
            status_code=409,
            detail="Add a USDOT number before submitting authority evidence.",
        )
    claim_id = _ensure_authority_claim(
        db,
        uid,
        carrier.get("organization_id")
        or organization_id_for_profile("carrier", uid),
        dot_number,
        carrier.get("fmcsa_snapshot_id"),
        carrier.get("dot_claim_status", "pending_review"),
    )
    ref = db.collection("carrier_authority_claims").document(claim_id)
    return ref, ref.get().to_dict() or {}


def _authority_evidence_metadata(db, claim_id: str) -> list[dict]:
    rows = []
    query = db.collection("carrier_authority_evidence").where(
        "claim_id",
        "==",
        claim_id,
    )
    for snap in query.stream():
        data = snap.to_dict() or {}
        rows.append({
            "id": data.get("id") or snap.id,
            "evidence_method": data.get("evidence_method"),
            "file_name": data.get("file_name"),
            "content_type": data.get("content_type"),
            "size_bytes": data.get("size_bytes"),
            "status": data.get("status"),
            "created_at": iso(data.get("created_at")),
        })
    rows.sort(key=lambda item: item.get("created_at") or "")
    return rows


@router.get("/authority-verification")
def get_authority_verification(authorization: Optional[str] = Header(None)):
    decoded, db, _ = _carrier(authorization)
    ref, claim = _authority_claim_for_carrier(db, decoded["uid"])
    return {
        "claim": {
            "id": ref.id,
            "dot_number": claim.get("dot_number"),
            "status": claim.get("status"),
            "dot_claim_status": claim.get("dot_claim_status"),
            "decision_reason": claim.get("decision_reason"),
            "updated_at": iso(claim.get("updated_at")),
        },
        "evidence": _authority_evidence_metadata(db, ref.id),
    }


@router.post("/authority-verification/evidence")
async def upload_authority_evidence(
    file: UploadFile = File(...),
    evidence_method: AuthorityEvidenceMethod = Form(...),
    authorization: Optional[str] = Header(None),
):
    decoded, db, _ = _carrier(authorization)
    claim_ref, claim = _authority_claim_for_carrier(db, decoded["uid"])
    if claim.get("status") == "verified":
        raise HTTPException(
            status_code=409,
            detail="This Carrier authority claim is already verified.",
        )
    if claim.get("status") == "duplicate_disputed":
        raise HTTPException(
            status_code=409,
            detail="Duplicate or disputed USDOT claims require Captain review.",
        )
    content = await file.read()
    try:
        safe_name, digest = validate_upload(
            file.filename or "authority-evidence",
            file.content_type or "",
            content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    method = evidence_method.value
    identity = f"{decoded['uid']}:{method}:{digest}".encode("utf-8")
    evidence_id = f"authority_evidence_{hashlib.sha256(identity).hexdigest()[:32]}"
    evidence_ref = db.collection("carrier_authority_evidence").document(evidence_id)
    existing = evidence_ref.get()
    if existing.exists:
        return {
            "ok": True,
            "evidence_id": evidence_id,
            "claim_id": claim_ref.id,
            "duplicate": True,
        }
    path = (
        f"carriers/{decoded['uid']}/authority-verification/"
        f"{evidence_id}_{safe_name}"
    )
    try:
        _bucket().blob(path).upload_from_string(
            content,
            content_type=file.content_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Authority evidence storage is unavailable.",
        ) from exc
    now = datetime.now(timezone.utc)
    evidence_ref.set({
        "id": evidence_id,
        "claim_id": claim_ref.id,
        "carrier_profile_id": decoded["uid"],
        "organization_id": claim.get("organization_id"),
        "dot_number": claim.get("dot_number"),
        "evidence_method": method,
        "file_name": safe_name,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "sha256": digest,
        "storage_path": path,
        "status": "received",
        "created_at": now,
        "uploaded_by": decoded["uid"],
    })
    evidence_ids = list(dict.fromkeys([
        *(claim.get("evidence_ids") or []),
        evidence_id,
    ]))
    claim_ref.set({
        "status": "pending_review",
        "evidence_ids": evidence_ids,
        "updated_at": now,
        "decision": None,
        "decision_reason": None,
    }, merge=True)
    return {
        "ok": True,
        "evidence_id": evidence_id,
        "claim_id": claim_ref.id,
        "duplicate": False,
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
    decoded, db, ref = _carrier(authorization)
    existing = ref.get().to_dict() or {}
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "company_name" in patch:
        patch["company_name"] = " ".join(str(patch["company_name"]).split())
        if not patch["company_name"]:
            raise HTTPException(status_code=422, detail="Company name is required.")
    email_fields = {"billing_email", "point_of_contact_email", "main_admin_email"}
    state_fields = {"state", "billing_state"}
    for key, value in tuple(patch.items()):
        if not isinstance(value, str) or key == "company_name":
            continue
        normalized = value.strip()
        if key in email_fields:
            normalized = normalized.lower()
        elif key in state_fields:
            normalized = normalized.upper()
        patch[key] = normalized or None
    if "dot_number" in patch:
        next_dot = _normalized_dot(str(patch["dot_number"]))
        if not next_dot:
            raise HTTPException(status_code=422, detail="Enter a valid USDOT number.")
        current_dot = _normalized_dot(existing.get("dot_number"))
        if current_dot and next_dot != current_dot:
            raise HTTPException(
                status_code=409,
                detail="USDOT changes require Captain review so Carrier identities are not merged.",
            )
        if not current_dot:
            dot_claim_status = _claim_dot_number(db, decoded["uid"], next_dot)
            patch.update({
                "dot_number": next_dot,
                "dot_claim_status": dot_claim_status,
                "tenant_status": (
                    "quarantined" if dot_claim_status == "duplicate_disputed" else "pending"
                ),
                "verification_status": "unverified",
            })
    now = datetime.now(timezone.utc)
    patch["updated_at"] = now
    ref.set(patch, merge=True)
    service, principal_id, organization_id = _carrier_platform(decoded, db, ref)
    organization_patch = {"updated_at": now}
    if "company_name" in patch:
        organization_patch.update({
            "legal_name": patch["company_name"],
            "display_name": patch["company_name"],
        })
    if "dot_number" in patch:
        organization_patch.update({
            "external_identifiers": {
                **(service.get_organization(organization_id).external_identifiers or {}),
                "dot_number": patch["dot_number"],
            },
            "verification_status": patch["verification_status"],
            "tenant_status": patch["tenant_status"],
        })
    db.collection("organizations").document(organization_id).set(organization_patch, merge=True)
    service._audit(
        "carrier.profile_updated",
        principal_id,
        "organization",
        organization_id,
        {"fields": sorted(key for key in patch if key != "updated_at")},
    )
    return {"ok": True, "updated": list(patch.keys())}


# ── Driver roster ─────────────────────────────────────────────────────────────

class DriverCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: Optional[str] = Field(default=None, max_length=254)
    phone: Optional[str] = Field(default=None, max_length=32)
    cdl_number: Optional[str] = Field(default=None, max_length=40)
    cdl_state: Optional[str] = Field(default=None, max_length=2)
    dob: Optional[str] = None
    med_cert_expiration: Optional[str] = None
    employment_type: Optional[str] = None
    home_terminal: Optional[str] = None
    subscription_start_date: Optional[str] = None
    psp_status: Optional[str] = None
    mvr_status: Optional[str] = None

    @model_validator(mode="after")
    def require_roster_identity(self):
        if self.cdl_number and not self.cdl_state:
            raise ValueError("cdl_state is required when cdl_number is provided.")
        if not any((self.cdl_number, self.email, self.phone)):
            raise ValueError("A CDL number, email, or phone is required to prevent duplicate roster records.")
        return self


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


class DriverConnectionRequest(BaseModel):
    code: str = Field(min_length=12, max_length=20)
    relationship_type: str = Field(
        default="employee",
        pattern="^(employee|contractor|lease_operator|owner_operator)$",
    )


class EndDriverRelationshipRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class DriverActiveRequest(BaseModel):
    active: bool


def _driver_out(doc) -> dict:
    d = doc.to_dict()
    d["driver_id"] = doc.id
    for k in ("created_at", "updated_at", "fired_at"):
        if d.get(k) is not None:
            d[k] = iso(d[k])
    return d


def _normalized_driver_data(data: dict) -> dict:
    normalized = dict(data)
    normalized["first_name"] = " ".join(str(normalized.get("first_name") or "").split())
    normalized["last_name"] = " ".join(str(normalized.get("last_name") or "").split())
    if normalized.get("email"):
        normalized["email"] = str(normalized["email"]).strip().lower()
    if normalized.get("phone"):
        digits = "".join(character for character in str(normalized["phone"]) if character.isdigit())
        normalized["phone"] = digits or None
    if normalized.get("cdl_number"):
        normalized["cdl_number"] = str(normalized["cdl_number"]).strip().upper()
        normalized["cdl_state"] = str(normalized.get("cdl_state") or "").strip().upper()
    elif normalized.get("cdl_state"):
        normalized["cdl_state"] = str(normalized["cdl_state"]).strip().upper()
    return normalized


def _driver_identity(data: dict) -> str:
    if data.get("cdl_number"):
        value = f"cdl:{data.get('cdl_state', '')}:{data['cdl_number']}"
    elif data.get("email"):
        value = f"email:{data['email']}"
    else:
        value = f"phone:{data.get('phone', '')}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _driver_document_id(carrier_id: str, data: dict) -> str:
    digest = hashlib.sha256(
        f"{carrier_id}:{_driver_identity(data)}".encode("utf-8")
    ).hexdigest()[:32]
    return f"roster_{digest}"


def _roster_identities(roster) -> dict[str, str]:
    identities = {}
    for snapshot in roster.stream():
        data = snapshot.to_dict() or {}
        identity = data.get("roster_identity")
        if not identity and any(data.get(key) for key in ("cdl_number", "email", "phone")):
            identity = _driver_identity(_normalized_driver_data(data))
        if identity:
            identities[str(identity)] = snapshot.id
    return identities


@router.get("/drivers")
def list_drivers(include_fired: bool = False, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    drivers = [_driver_out(d) for d in ref.collection("drivers").stream()]
    if not include_fired:
        drivers = [d for d in drivers if not d.get("fired_at")]
    return {"drivers": drivers, "count": len(drivers)}


@router.post("/drivers")
def create_driver(body: DriverCreate, authorization: Optional[str] = Header(None)):
    decoded, _, ref = _carrier(authorization)
    data = _normalized_driver_data(body.model_dump())
    now = datetime.now(timezone.utc)
    roster = ref.collection("drivers")
    identity = _driver_identity(data)
    existing_id = _roster_identities(roster).get(identity)
    doc = roster.document(
        existing_id or _driver_document_id(decoded["uid"], data)
    )
    if existing_id or doc.get().exists:
        return {"ok": True, "driver_id": doc.id, "duplicate": True}
    doc.set({**data, "roster_identity": _driver_identity(data),
             "active": True, "fired_at": None,
             "created_at": now, "updated_at": now})
    return {"ok": True, "driver_id": doc.id, "duplicate": False}


def _carrier_platform(decoded: dict, db, carrier_ref):
    profile = carrier_ref.get().to_dict() or {}
    service = PlatformService(db)
    principal_id = principal_id_for_uid(decoded["uid"])
    organization_id = organization_id_for_profile("carrier", decoded["uid"])
    if service.get_principal(principal_id) is None:
        service.bootstrap_principal({**decoded, "role": "carrier"})
    if service.get_organization(organization_id) is None:
        service.bootstrap_role_organization({**decoded, "role": "carrier"})
        db.collection("organizations").document(organization_id).set({
            "verification_status": profile.get("verification_status", "unverified"),
            "tenant_status": profile.get("tenant_status", "pending"),
            "updated_at": datetime.now(timezone.utc),
        }, merge=True)
    return service, principal_id, organization_id


@router.get("/relationships")
def list_driver_relationships(authorization: Optional[str] = Header(None)):
    decoded, db, carrier_ref = _carrier(authorization)
    service, _, organization_id = _carrier_platform(decoded, db, carrier_ref)
    return {
        "relationships": service.list_organization_relationships(organization_id),
    }


@router.post("/relationships/connect")
def connect_driver(
    body: DriverConnectionRequest,
    authorization: Optional[str] = Header(None),
):
    """Consume a Driver-created one-time code and create a pending relationship."""
    decoded, db, carrier_ref = _carrier(authorization)
    service, principal_id, organization_id = _carrier_platform(decoded, db, carrier_ref)
    normalized = "".join(character for character in body.code.upper() if character.isalnum())
    if len(normalized) != 12:
        raise HTTPException(status_code=422, detail="Enter the complete Driver connection code.")
    digest = hashlib.sha256(normalized.encode("ascii")).hexdigest()
    code_ref = db.collection("driver_connection_codes").document(digest)
    snapshot = code_ref.get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Connection code not found or expired.")
    code = snapshot.to_dict() or {}
    expires_at = code.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if (
        code.get("status") != "active"
        or not isinstance(expires_at, datetime)
        or (expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)) <= now
    ):
        raise HTTPException(status_code=409, detail="Connection code not found or expired.")
    driver_principal_id = code.get("driver_principal_id")
    if not isinstance(driver_principal_id, str) or service.get_principal(driver_principal_id) is None:
        raise HTTPException(status_code=409, detail="Connection code cannot be used.")
    if not any(
        membership.organization_id == organization_id
        and membership.principal_id == principal_id
        and membership.status.value == "active"
        for membership in service.list_memberships(principal_id)
    ):
        raise HTTPException(status_code=403, detail="Active Carrier membership required.")
    try:
        code_ref.update({
            "status": "consumed",
            "consumed_at": now,
            "consumed_by_organization_id": organization_id,
        }, option=LastUpdateOption(snapshot.update_time))
    except (Aborted, FailedPrecondition) as exc:
        raise HTTPException(status_code=409, detail="Connection code was already used.") from exc
    try:
        relationship, created = service.create_driver_relationship_invitation(
            principal_id,
            organization_id,
            DriverCarrierRelationshipCreate(
                driver_principal_id=driver_principal_id,
                relationship_type=body.relationship_type,
            ),
        )
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail="Driver relationship could not be created.") from exc
    _record_acquisition_event(db, principal_id, "first_driver_relationship_requested")
    return {"relationship": relationship, "created": created}


@router.post("/relationships/{relationship_id}/end")
def end_driver_relationship(
    relationship_id: str,
    body: EndDriverRelationshipRequest,
    authorization: Optional[str] = Header(None),
):
    decoded, db, carrier_ref = _carrier(authorization)
    service, principal_id, _ = _carrier_platform(decoded, db, carrier_ref)
    try:
        return {
            "relationship": service.end_driver_relationship(
                principal_id, relationship_id, body.reason
            )
        }
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/drivers/bulk")
def bulk_create_drivers(body: BulkDriverCreate, authorization: Optional[str] = Header(None)):
    """Validate the complete payload before committing any row."""
    decoded, db, ref = _carrier(authorization)
    if not body.drivers or len(body.drivers) > 100:
        raise HTTPException(status_code=400, detail="Upload between 1 and 100 drivers at a time.")
    seen: set[str] = set()
    errors = []
    normalized_rows = []
    for row, driver in enumerate(body.drivers, start=2):
        data = _normalized_driver_data(driver.model_dump())
        identity = _driver_identity(data)
        if identity in seen:
            errors.append({"row": row, "message": "Duplicate Driver identity in this file."})
        seen.add(identity)
        normalized_rows.append((data, identity))
    if errors:
        raise HTTPException(status_code=422, detail={"message": "No drivers were imported.", "errors": errors})
    roster = ref.collection("drivers")
    existing_identities = _roster_identities(roster)
    now = datetime.now(timezone.utc)
    batch = db.batch()
    ids = []
    duplicate_ids = []
    for data, identity in normalized_rows:
        existing_id = existing_identities.get(identity)
        doc = roster.document(
            existing_id or _driver_document_id(decoded["uid"], data)
        )
        if existing_id or doc.get().exists:
            duplicate_ids.append(doc.id)
            continue
        batch.set(doc, {
            **data,
            "roster_identity": identity,
            "active": True,
            "fired_at": None,
            "created_at": now,
            "updated_at": now,
        })
        ids.append(doc.id)
    batch.commit()
    return {
        "ok": True,
        "created": len(ids),
        "duplicates": len(duplicate_ids),
        "driver_ids": ids,
        "duplicate_driver_ids": duplicate_ids,
    }


@router.patch("/drivers/{driver_id}")
def update_driver(driver_id: str, body: DriverUpdate, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    roster = ref.collection("drivers")
    doc = roster.document(driver_id)
    snapshot = doc.get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    merged = _normalized_driver_data({**(snapshot.to_dict() or {}), **patch})
    try:
        DriverCreate.model_validate(merged)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    identity = _driver_identity(merged)
    collision = _roster_identities(roster).get(identity)
    if collision and collision != driver_id:
        raise HTTPException(status_code=409, detail="Another roster record has the same CDL or contact identity.")
    patch = {
        key: merged[key]
        for key in patch
    }
    patch["roster_identity"] = identity
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


@router.put("/drivers/{driver_id}/active")
def set_driver_active(
    driver_id: str,
    body: DriverActiveRequest,
    authorization: Optional[str] = Header(None),
):
    _, _, ref = _carrier(authorization)
    doc = ref.collection("drivers").document(driver_id)
    snapshot = doc.get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    data = snapshot.to_dict() or {}
    if data.get("fired_at"):
        raise HTTPException(status_code=409, detail="A former Driver cannot be reactivated.")
    current = bool(data.get("active", True))
    if current == body.active:
        return {"ok": True, "active": current, "duplicate": True}
    doc.update({"active": body.active, "updated_at": datetime.now(timezone.utc)})
    return {"ok": True, "active": body.active, "duplicate": False}


@router.post("/drivers/{driver_id}/fire")
def fire_driver(driver_id: str, authorization: Optional[str] = Header(None)):
    """Soft-remove — keeps the record (and ticket/MVR history) intact."""
    _, _, ref = _carrier(authorization)
    doc = ref.collection("drivers").document(driver_id)
    snapshot = doc.get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    existing = snapshot.to_dict() or {}
    if existing.get("fired_at"):
        return {
            "ok": True,
            "fired_at": iso(existing["fired_at"]),
            "duplicate": True,
        }
    now = datetime.now(timezone.utc)
    doc.update({"active": False, "fired_at": now, "updated_at": now})
    return {"ok": True, "fired_at": iso(now), "duplicate": False}


@router.get("/drivers/{driver_id}/profile")
def driver_profile(driver_id: str, authorization: Optional[str] = Header(None)):
    decoded, db, ref = _carrier(authorization)
    snap = ref.collection("drivers").document(driver_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Driver not found.")
    driver = snap.to_dict()
    driver["driver_id"] = snap.id
    principal_id = driver.pop("principal_id", None)
    if not principal_id:
        return {
            "driver": driver,
            "relationship_status": "carrier_provided_roster_only",
            "safety_summary": None,
            "case_data_shared": False,
        }
    _, actor_id, organization_id = _carrier_platform(decoded, db, ref)
    try:
        summary = CarrierResolveService(db).driver_summary(
            actor_id, organization_id, principal_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {
        "driver": driver,
        "relationship_status": "active_consented",
        "safety_summary": summary,
        "case_data_shared": False,
    }


@router.get("/drivers/{driver_id}/tickets")
def driver_tickets(driver_id: str, authorization: Optional[str] = Header(None)):
    _carrier(authorization)
    raise HTTPException(
        status_code=403,
        detail="Driver legal case data is not shared by Carrier safety consent.",
    )


# ── FMCSA / subscription / notifications / billing ──────────────────────────

def _fmcsa_basics(raw: dict) -> list[dict]:
    source = (
        raw.get("basics")
        or raw.get("sms_basics")
        or (raw.get("risk_profile") or {}).get("basics")
        or []
    )
    normalized = []
    for item in source:
        if not isinstance(item, dict):
            continue
        percentile = item.get("percentile")
        if isinstance(percentile, bool) or not isinstance(percentile, (int, float)):
            percentile = None
        elif percentile < 0 or percentile > 100:
            percentile = None
        normalized.append({
            "code": item.get("code"),
            "name": item.get("name") or item.get("basic") or item.get("code") or "BASIC",
            "percentile": percentile,
            "measure": item.get("measure"),
            "threshold": item.get("threshold"),
            "alert": bool(item.get("alert")),
            "metric_name": "FMCSA SMS BASIC percentile",
            "scale": {"minimum": 0, "maximum": 100, "direction": "0 best; 100 worst"},
        })
    return normalized


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
    safety_rating = raw.get("safety_rating") or raw.get("fmcsa_safety_rating")
    return {"status": "ready", "source": "FMCSA SMS cached data", "dot_number": dot,
            "last_updated": iso(updated) if updated else None,
            "carrier": {k: raw.get(k) for k in (
                "legal_name", "dba_name", "operating_status", "power_units", "driver_count",
                "inspection_count", "violation_count", "crash_count", "oos_status", "oos_date", "oos_reason")},
            "safety_rating": safety_rating,
            "safety_rating_note": "FMCSA Safety Rating is separate from SMS BASIC percentiles.",
            "basics": _fmcsa_basics(raw),
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
    decoded, db, ref = _carrier(authorization)
    principal_id = principal_id_for_uid(decoded["uid"])
    items = PlatformService(db).list_notifications(
        principal_id, unread_only=unread_only
    )
    # Preserve legacy Carrier alerts while new cross-role events use the
    # principal-owned collection.
    for snap in ref.collection("notifications").stream():
        data = snap.to_dict()
        data["notification_id"] = snap.id
        if data.get("created_at"):
            data["created_at"] = iso(data["created_at"])
        if (
            not unread_only or not data.get("read", False)
        ) and not any(item.get("id") == data["notification_id"] for item in items):
            items.append(data)
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return {"notifications": items[:50],
            "unread_count": sum(1 for item in items if not item.get("read", False))}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, authorization: Optional[str] = Header(None)):
    decoded, db, ref = _carrier(authorization)
    try:
        PlatformService(db).mark_notification_read(
            principal_id_for_uid(decoded["uid"]), notification_id
        )
        return {"ok": True}
    except LookupError:
        pass
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
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(..., min_length=1, max_length=80),
    name: str = Form(..., min_length=1, max_length=160),
    authorization: Optional[str] = Header(None),
):
    decoded, _, ref = _carrier(authorization)
    content = await file.read()
    try:
        safe_name, digest = validate_upload(
            file.filename or "document",
            file.content_type or "",
            content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    category = category.strip()
    name = name.strip()
    identity = f"{decoded['uid']}:{category}:{name}:{digest}".encode("utf-8")
    document_id = f"carrier_doc_{hashlib.sha256(identity).hexdigest()[:32]}"
    doc = ref.collection("documents").document(document_id)
    existing = doc.get()
    if existing.exists:
        return {
            "ok": True,
            "document_id": document_id,
            "created_at": iso((existing.to_dict() or {}).get("created_at")),
            "duplicate": True,
        }
    path = f"carriers/{decoded['uid']}/documents/{document_id}_{safe_name}"
    try:
        _bucket().blob(path).upload_from_string(content, content_type=file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable.") from exc
    now = datetime.now(timezone.utc)
    doc.set({"name": name, "category": category, "file_name": safe_name,
             "storage_path": path, "content_type": file.content_type,
             "size_bytes": len(content), "sha256": digest, "status": "received",
             "created_at": now, "uploaded_by": decoded["uid"]})
    return {
        "ok": True,
        "document_id": document_id,
        "created_at": iso(now),
        "duplicate": False,
    }


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, authorization: Optional[str] = Header(None)):
    _, _, ref = _carrier(authorization)
    snap = ref.collection("documents").document(document_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        url = _bucket().blob(snap.to_dict()["storage_path"]).generate_signed_url(
            version="v4", expiration=900, method="GET")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document download is unavailable.") from exc
    return {"url": url, "expires_in": 900}
