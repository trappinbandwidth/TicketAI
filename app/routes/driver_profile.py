"""Authenticated Driver profile API and verification-data boundary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from google.api_core.exceptions import AlreadyExists
from pydantic import BaseModel, Field, model_validator

from app.routes._common import get_db
from app.platform.documents import validate_upload
from app.platform.models import ConsentGrantCreate
from app.platform.service import PlatformService, principal_id_for_uid
from app.services.auth_rbac import require_role, verify_firebase_token
from app.services.driver_profile import DriverProfileService, PiiCipher
from app.services.carrier_lookup import carrier_discovery_detail
from app.services.file_naming import FileDepartment, governed_file_name, opaque_storage_object

router = APIRouter(prefix="/driver/profile", tags=["driver-profile"])


class DriverAddress(BaseModel):
    street: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    zip: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")


class DriverProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    middle_initial: str = Field(default="", max_length=1)
    last_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=32)
    dob: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    cdl_number: str = Field(min_length=1, max_length=40)
    cdl_state: str = Field(pattern=r"^[A-Z]{2}$")
    cdl_expiration: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    address: DriverAddress
    ssn_last4: str = Field(pattern=r"^\d{4}$")
    driver_role: Literal["company_driver", "owner_operator"]
    carrier_name: Optional[str] = Field(default=None, max_length=160)
    business_name: Optional[str] = Field(default=None, max_length=160)
    profile_image: str = Field(min_length=20, max_length=750_000)

    @model_validator(mode="after")
    def require_organization(self):
        if self.driver_role == "company_driver" and not (self.carrier_name or "").strip():
            raise ValueError("carrier_name is required for a company Driver.")
        if self.driver_role == "owner_operator" and not (self.business_name or "").strip():
            raise ValueError("business_name is required for an owner-operator.")
        return self


class DriverProfileEdit(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    driver_role: Literal["company_driver", "owner_operator"]
    carrier_name: Optional[str] = Field(default=None, max_length=160)
    business_name: Optional[str] = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def require_organization(self):
        if self.driver_role == "company_driver" and not (self.carrier_name or "").strip():
            raise ValueError("carrier_name is required for a company Driver.")
        if self.driver_role == "owner_operator" and not (self.business_name or "").strip():
            raise ValueError("business_name is required for an owner-operator.")
        return self


def _driver_claims(authorization: Optional[str]) -> dict:
    claims = require_role(verify_firebase_token(authorization), {"driver"})
    uid = claims.get("uid")
    if not isinstance(uid, str) or not uid:
        raise HTTPException(status_code=401, detail="Authenticated Driver identity is missing.")
    return claims


def _service() -> DriverProfileService:
    return DriverProfileService(get_db(), PiiCipher.from_env())


class RelationshipResponse(BaseModel):
    accept: bool
    reason: Optional[str] = Field(default=None, max_length=500)


class SafetyConsentRequest(BaseModel):
    disclosure_version: str = Field(min_length=1, max_length=80)


class RevokeSafetyConsentRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class EmploymentHistoryWrite(BaseModel):
    dot_number: str = Field(min_length=1, max_length=24)
    started_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ended_on: Optional[str] = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    relationship_type: Literal[
        "employee", "contractor", "lease_operator", "owner_operator"
    ]
    title: Optional[str] = Field(default=None, max_length=120)
    source_record_reviewed: bool

    @model_validator(mode="after")
    def validate_dates_and_confirmation(self):
        try:
            started = datetime.fromisoformat(self.started_on).date()
            ended = (
                datetime.fromisoformat(self.ended_on).date()
                if self.ended_on
                else None
            )
        except ValueError as exc:
            raise ValueError("Enter valid employment dates.") from exc
        if ended and ended < started:
            raise ValueError("Employment end date cannot be before the start date.")
        if not self.source_record_reviewed:
            raise ValueError("Review the selected FMCSA Carrier record first.")
        return self


def _platform(db, claims: dict) -> tuple[PlatformService, str]:
    service = PlatformService(db)
    principal, _ = service.bootstrap_principal({**claims, "role": "driver"})
    return service, principal.id


def _employment_identity(
    driver_principal_id: str, dot_number: str, started_on: str
) -> str:
    digest = hashlib.sha256(
        f"{driver_principal_id}:{dot_number}:{started_on}".encode("utf-8")
    ).hexdigest()[:32]
    return f"emp_{digest}"


def _normalized_dot(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _employment_record(
    principal_id: str, body: EmploymentHistoryWrite, existing: Optional[dict] = None
) -> tuple[str, dict]:
    dot_number = _normalized_dot(body.dot_number)
    carrier = carrier_discovery_detail(dot_number)
    if carrier is None:
        raise HTTPException(status_code=404, detail="FMCSA Carrier record not found.")
    employment_id = _employment_identity(
        principal_id, dot_number, body.started_on
    )
    now = datetime.now(timezone.utc)
    return employment_id, {
        "id": employment_id,
        "driver_principal_id": principal_id,
        "dot_number": dot_number,
        "employment_claim": {
            "started_on": body.started_on,
            "ended_on": body.ended_on,
            "relationship_type": body.relationship_type,
            "title": body.title.strip() if body.title else None,
            "source_kind": "driver_self_reported",
            "verification_status": "self_reported",
        },
        "carrier_source_snapshot": carrier,
        "carrier_context_scope": "carrier_level_public_context",
        "individual_driver_safety_record": False,
        "created_at": (existing or {}).get("created_at", now),
        "updated_at": now,
    }


@router.get("")
def get_profile(authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    return _service().get(claims["uid"], phone=claims.get("phone_number"))


@router.put("")
def save_profile(body: DriverProfileUpdate, authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    return _service().save(claims["uid"], body, phone=claims.get("phone_number"))


@router.patch("")
def edit_profile(body: DriverProfileEdit, authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    return _service().edit_public(claims["uid"], body, phone=claims.get("phone_number"))


@router.get("/employment-history")
def list_employment_history(authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    db = get_db()
    _, principal_id = _platform(db, claims)
    docs = db.collection("driver_employment_history").where(
        "driver_principal_id", "==", principal_id
    ).stream()
    items = [dict(snapshot.to_dict() or {}) for snapshot in docs]
    for item in items:
        for field in ("created_at", "updated_at"):
            value = item.get(field)
            if hasattr(value, "isoformat"):
                item[field] = value.isoformat()
    items.sort(
        key=lambda item: (
            (item.get("employment_claim") or {}).get("started_on") or ""
        ),
        reverse=True,
    )
    return {"employment_history": items, "count": len(items)}


@router.post("/employment-history")
def create_employment_history(
    body: EmploymentHistoryWrite,
    authorization: Optional[str] = Header(None),
):
    claims = _driver_claims(authorization)
    db = get_db()
    service, principal_id = _platform(db, claims)
    employment_id, record = _employment_record(principal_id, body)
    ref = db.collection("driver_employment_history").document(employment_id)
    existing = ref.get()
    if getattr(existing, "exists", False):
        return {
            "employment": existing.to_dict(),
            "created": False,
            "duplicate": True,
        }
    try:
        ref.create(record)
    except AlreadyExists:
        return {
            "employment": ref.get().to_dict(),
            "created": False,
            "duplicate": True,
        }
    service._audit(
        "driver.employment_history_created",
        principal_id,
        "driver_employment_history",
        employment_id,
        {"dot_number": record["dot_number"], "source_kind": "driver_self_reported"},
    )
    return {"employment": record, "created": True, "duplicate": False}


@router.put("/employment-history/{employment_id}")
def update_employment_history(
    employment_id: str,
    body: EmploymentHistoryWrite,
    authorization: Optional[str] = Header(None),
):
    claims = _driver_claims(authorization)
    db = get_db()
    service, principal_id = _platform(db, claims)
    ref = db.collection("driver_employment_history").document(employment_id)
    snapshot = ref.get()
    if not getattr(snapshot, "exists", False):
        raise HTTPException(status_code=404, detail="Employment record not found.")
    existing = snapshot.to_dict() or {}
    if existing.get("driver_principal_id") != principal_id:
        raise HTTPException(status_code=404, detail="Employment record not found.")
    expected_id, record = _employment_record(principal_id, body, existing)
    if expected_id != employment_id:
        raise HTTPException(
            status_code=409,
            detail="USDOT and employment start date identify this record and cannot be changed.",
        )
    ref.set(record)
    service._audit(
        "driver.employment_history_updated",
        principal_id,
        "driver_employment_history",
        employment_id,
        {"fields": ["ended_on", "relationship_type", "title"]},
    )
    return {"employment": record, "updated": True}


@router.delete("/employment-history/{employment_id}")
def delete_employment_history(
    employment_id: str, authorization: Optional[str] = Header(None)
):
    claims = _driver_claims(authorization)
    db = get_db()
    service, principal_id = _platform(db, claims)
    ref = db.collection("driver_employment_history").document(employment_id)
    snapshot = ref.get()
    if (
        not getattr(snapshot, "exists", False)
        or (snapshot.to_dict() or {}).get("driver_principal_id") != principal_id
    ):
        raise HTTPException(status_code=404, detail="Employment record not found.")
    ref.delete()
    service._audit(
        "driver.employment_history_deleted",
        principal_id,
        "driver_employment_history",
        employment_id,
    )
    return {"ok": True}


@router.post("/carrier-connection-code")
def create_carrier_connection_code(authorization: Optional[str] = Header(None)):
    """Create a short-lived, one-time code without exposing Driver identifiers."""
    claims = _driver_claims(authorization)
    db = get_db()
    _, principal_id = _platform(db, claims)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=15)
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    for _ in range(3):
        code = "".join(secrets.choice(alphabet) for _ in range(12))
        digest = hashlib.sha256(code.encode("ascii")).hexdigest()
        try:
            db.collection("driver_connection_codes").document(digest).create({
                "code_hash": digest,
                "driver_principal_id": principal_id,
                "status": "active",
                "created_at": now,
                "expires_at": expires_at,
            })
            return {
                "code": f"{code[:4]}-{code[4:8]}-{code[8:]}",
                "expires_at": expires_at.isoformat(),
            }
        except AlreadyExists:
            continue
    raise HTTPException(status_code=503, detail="Couldn't create a connection code. Try again.")


@router.get("/carrier-relationships")
def list_carrier_relationships(authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    service, principal_id = _platform(get_db(), claims)
    return {
        "relationships": service.list_driver_relationships(principal_id),
        "consents": service.list_consents(principal_id),
    }


@router.get("/notifications")
def list_notifications(
    unread_only: bool = False, authorization: Optional[str] = Header(None)
):
    """Return only in-app notifications owned by the authenticated Driver."""
    claims = _driver_claims(authorization)
    service, principal_id = _platform(get_db(), claims)
    items = service.list_notifications(principal_id, unread_only=unread_only)
    return {
        "notifications": items,
        "unread_count": sum(1 for item in items if not item.get("read", False)),
    }


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str, authorization: Optional[str] = Header(None)
):
    claims = _driver_claims(authorization)
    service, principal_id = _platform(get_db(), claims)
    try:
        service.mark_notification_read(principal_id, notification_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/carrier-relationships/{relationship_id}/respond")
def respond_to_carrier_relationship(
    relationship_id: str,
    body: RelationshipResponse,
    authorization: Optional[str] = Header(None),
):
    claims = _driver_claims(authorization)
    service, principal_id = _platform(get_db(), claims)
    try:
        relationship = service.respond_to_driver_relationship(
            principal_id, relationship_id, body.accept, body.reason
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"relationship": relationship}


@router.post("/carrier-relationships/{relationship_id}/safety-consent")
def grant_carrier_safety_consent(
    relationship_id: str,
    body: SafetyConsentRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _driver_claims(authorization)
    service, principal_id = _platform(get_db(), claims)
    relationships = {
        relationship.id: relationship
        for relationship in service.list_driver_relationships(principal_id)
    }
    relationship = relationships.get(relationship_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Carrier relationship not found.")
    try:
        consent = service.create_consent(
            principal_id,
            ConsentGrantCreate(
                subject_principal_id=principal_id,
                recipient_organization_id=relationship.carrier_organization_id,
                purpose="safety_compliance",
                record_categories=["profile", "credential", "employment", "inspection"],
                actions=["read"],
                disclosure_version=body.disclosure_version,
                related_resource_type="driver_carrier_relationship",
                related_resource_id=relationship_id,
            ),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"consent": consent}


@router.post("/carrier-safety-consents/{consent_id}/revoke")
def revoke_carrier_safety_consent(
    consent_id: str,
    body: RevokeSafetyConsentRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _driver_claims(authorization)
    service, principal_id = _platform(get_db(), claims)
    try:
        return {"consent": service.revoke_consent(principal_id, consent_id, body.reason)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _driver_ticket(db, uid: str, ticket_id: str):
    """Resolve only a ticket owned by the authenticated Driver."""
    owned_ref = (
        db.collection("drivers")
        .document(uid)
        .collection("tickets")
        .document(ticket_id)
    )
    owned = owned_ref.get()
    if owned.exists:
        return owned_ref, owned.to_dict() or {}

    canonical_ref = db.collection("tickets").document(ticket_id)
    canonical = canonical_ref.get()
    data = canonical.to_dict() if canonical.exists else {}
    if not canonical.exists or data.get("driver_id") != uid:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return owned_ref, data


def _mark_requested_document_received(ticket: dict, label: str) -> list[dict]:
    updated = []
    matched = False
    for item in ticket.get("documents_needed") or []:
        copy = dict(item)
        if not matched and str(copy.get("label", "")).strip() == label.strip():
            copy["status"] = "received"
            matched = True
        updated.append(copy)
    return updated


@router.post("/tickets/{ticket_id}/documents")
async def upload_ticket_document(
    ticket_id: str,
    file: UploadFile = File(...),
    label: str = Form(..., min_length=1, max_length=160),
    authorization: Optional[str] = Header(None),
):
    """Attach a requested document to the authenticated Driver's existing case."""
    claims = _driver_claims(authorization)
    db = get_db()
    ticket_ref, ticket = _driver_ticket(db, claims["uid"], ticket_id)
    content = await file.read()
    try:
        safe_name, digest = validate_upload(
            file.filename or "document",
            file.content_type or "",
            content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from firebase_admin import storage

    idempotency_material = f"{ticket_id}:{label.strip()}:{digest}".encode("utf-8")
    document_id = f"driver_doc_{hashlib.sha256(idempotency_material).hexdigest()[:32]}"
    existing = ticket_ref.collection("documents").document(document_id).get()
    if existing.exists:
        return {"ok": True, "document_id": document_id, "status": "received", "duplicate": True}
    profile_snapshot = db.collection("drivers").document(claims["uid"]).get()
    profile = profile_snapshot.to_dict() if profile_snapshot.exists else {}
    subject_name = " ".join(
        part for part in [profile.get("first_name"), profile.get("last_name")] if part
    ).strip() or str(claims.get("name") or "").strip()
    if not subject_name:
        raise HTTPException(
            status_code=422,
            detail="Your verified profile name is required before uploading documents.",
        )
    now = datetime.now(timezone.utc)
    naming = governed_file_name(
        subject_name=subject_name,
        department=FileDepartment.DRIVER,
        case_id=ticket_id,
        general_id=None,
        uploaded_at=now,
        content_type=file.content_type or "",
    )
    object_name = opaque_storage_object(document_id, file.content_type or "")
    path = f"drivers/{claims['uid']}/tickets/{ticket_id}/documents/{object_name}"
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not project_id:
        raise HTTPException(status_code=503, detail="Document storage is unavailable.")
    try:
        storage.bucket(f"{project_id}.appspot.com").blob(path).upload_from_string(
            content,
            content_type=file.content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable.") from exc

    metadata = {
        "document_id": document_id,
        "ticket_id": ticket_id,
        "driver_id": claims["uid"],
        "label": label.strip(),
        "file_name": naming.display_name,
        "original_file_name": safe_name,
        "naming_policy_version": naming.policy_version,
        "naming_department": naming.department,
        "naming_case": naming.case_component,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "sha256": digest,
        "storage_path": path,
        "status": "received",
        "created_at": now,
    }
    ticket_ref.collection("documents").document(document_id).set(metadata)
    updates = {
        "documents_needed": _mark_requested_document_received(ticket, label),
        "updated_at": now,
    }
    ticket_ref.set(updates, merge=True)

    canonical_ref = db.collection("tickets").document(ticket_id)
    canonical = canonical_ref.get()
    if canonical.exists and (canonical.to_dict() or {}).get("driver_id") == claims["uid"]:
        canonical_ref.set(updates, merge=True)
        canonical_ref.collection("driver_documents").document(document_id).set(metadata)

    return {"ok": True, "document_id": document_id, "status": "received"}
