"""Authenticated WP-03 document intake and human verification APIs."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.platform.document_service import DocumentService
from app.platform.documents import DocumentStatus
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token
from app.services.malware_scanner import configured_scanner
from app.services.document_worker import run_document_job
from app.services.driver_resolve import DriverResolveService


router = APIRouter(prefix="/documents", tags=["tip-os-documents"])


class VerifyExtractionRequest(BaseModel):
    corrections: dict[str, str] = Field(default_factory=dict)


def _claims(authorization: Optional[str]) -> dict:
    if os.getenv("TIP_OS_DOCUMENTS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Document APIs are not enabled.")
    return verify_firebase_token(authorization)


def _actor(claims: dict) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _staff(claims: dict) -> bool:
    return claims.get("role") in STAFF_ROLES or claims.get("staff_role") in STAFF_ROLES


def _service() -> DocumentService:
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Document store unavailable.")
    return DocumentService(firebase_service._firestore_client, configured_scanner())


def _store_quarantine(document_id: str, filename: str, content_type: str, content: bytes) -> str:
    from firebase_admin import storage

    project = os.getenv("FIREBASE_PROJECT_ID", "rigresolve")
    bucket = storage.bucket(f"{project}.appspot.com")
    path = f"tip-os-quarantine/{document_id}/{filename}"
    bucket.blob(path).upload_from_string(content, content_type=content_type)
    return f"gs://{bucket.name}/{path}"


@router.post("", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor(_claims(authorization))
    content = await file.read()
    service = _service()
    try:
        # Validate and scan before storage; the object stays in a private quarantine prefix.
        asset = service.ingest(
            actor_id,
            file.filename or "document",
            file.content_type or "",
            content,
        )
        storage_path = _store_quarantine(asset.id, asset.filename, asset.content_type, content)
        asset.storage_path = storage_path
        service.db.collection("document_assets").document(asset.id).set(
            asset.model_dump(mode="json")
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if "asset" in locals():
            asset.status = DocumentStatus.FAILED
            service.db.collection("document_assets").document(asset.id).set(
                asset.model_dump(mode="json")
            )
        raise HTTPException(status_code=503, detail="Secure document storage unavailable.") from exc
    return {"document": asset}


@router.get("")
def list_documents(authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    return {"documents": _service().list_documents(actor_id)}


@router.get("/extractions/{run_id}")
def get_extraction(run_id: str, authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    try:
        return {"extraction": _service().get_extraction(actor_id, run_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{document_id}/extract", status_code=202)
def enqueue_extraction(document_id: str, authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    try:
        job, created = _service().enqueue_extraction(actor_id, document_id)
        return {"job": job, "created": created}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    try:
        return {"job": _service().get_job(actor_id, job_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/internal/jobs/{job_id}/run")
def run_job(job_id: str, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    if not _staff(claims):
        raise HTTPException(status_code=403, detail="Staff role required.")
    try:
        return run_document_job(_service().db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{document_id}")
def get_document(document_id: str, authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    try:
        return {"document": _service().get_document(actor_id, document_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/extractions/{run_id}/verify")
def verify_extraction(
    run_id: str,
    body: VerifyExtractionRequest,
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor(_claims(authorization))
    try:
        return {"extraction": _service().verify_extraction(actor_id, run_id, body.corrections)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/extractions/{run_id}/finalize", status_code=201)
def finalize_extraction(run_id: str, authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    try:
        return DriverResolveService(_service().db).finalize_verified_extraction(actor_id, run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
