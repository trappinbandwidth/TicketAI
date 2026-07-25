"""Authenticated Driver profile API and verification-data boundary."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field, model_validator

from app.routes._common import get_db
from app.platform.documents import validate_upload
from app.services.auth_rbac import require_role, verify_firebase_token
from app.services.driver_profile import DriverProfileService, PiiCipher

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
    path = f"drivers/{claims['uid']}/tickets/{ticket_id}/documents/{document_id}_{safe_name}"
    try:
        storage.bucket().blob(path).upload_from_string(content, content_type=file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable.") from exc

    now = datetime.now(timezone.utc)
    metadata = {
        "document_id": document_id,
        "ticket_id": ticket_id,
        "driver_id": claims["uid"],
        "label": label.strip(),
        "file_name": safe_name,
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
