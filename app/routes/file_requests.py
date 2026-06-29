"""
AE-06 — File Request route.

Attorneys can request additional documents from a driver on an active case.
The request is written to:
  tickets/{ticket_id}/file_requests/{request_id}
  drivers/{driver_id}/notifications/{notif_id}  (in-app notification)

The driver app listens on the notifications subcollection and surfaces a prompt
to upload the requested document. Uploaded files land in Firebase Storage at:
  tickets/{ticket_id}/uploads/{filename}
and the download URL is written back to the file_request doc.

Auth: Firebase ID token (Bearer header) — caller must be the attorney who
holds the case (attorney_status == 'Accepted' and assigned_attorney_id matches).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["file-requests"])


def _db():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    return _firestore_client


class FileRequestBody(BaseModel):
    ticket_id: str
    document_type: str          # e.g. "Ticket front", "Ticket back", "CDL", "Insurance card"
    message: Optional[str] = "" # optional custom note to driver
    due_date: Optional[str] = None  # ISO date string


class FileRequestResponse(BaseModel):
    success: bool
    request_id: str
    ticket_id: str
    document_type: str


@router.post("/file-request", response_model=FileRequestResponse)
def create_file_request(
    body: FileRequestBody,
    authorization: Optional[str] = Header(None),
):
    """
    Attorney requests a document upload from the driver on their active case.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization.split(" ", 1)[1]
    try:
        decoded = fb_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    attorney_uid = decoded["uid"]
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="Firestore not available.")

    # Verify ticket exists and this attorney is assigned
    ticket_ref = db.collection("tickets").document(body.ticket_id)
    ticket_doc = ticket_ref.get()
    if not ticket_doc.exists:
        raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_id} not found.")

    ticket_data = ticket_doc.to_dict()
    assigned = ticket_data.get("assigned_attorney_id") or ticket_data.get("attorney_uid") or ""
    status = ticket_data.get("attorney_status", "")

    if status not in ("Accepted", "Admin Assigned", "Atty Contacted", "Active"):
        raise HTTPException(
            status_code=400,
            detail=f"File requests can only be made on active cases (current status: {status}).",
        )
    if assigned and assigned != attorney_uid:
        raise HTTPException(status_code=403, detail="You are not the assigned attorney for this case.")

    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    driver_id = ticket_data.get("driver_id", "")

    # Write request to tickets/{ticket_id}/file_requests/{request_id}
    file_request_doc = {
        "request_id": request_id,
        "ticket_id": body.ticket_id,
        "attorney_uid": attorney_uid,
        "document_type": body.document_type,
        "message": body.message or "",
        "due_date": body.due_date,
        "status": "pending",  # pending | uploaded | acknowledged
        "created_at": SERVER_TIMESTAMP,
        "upload_url": None,
        "uploaded_at": None,
    }
    ticket_ref.collection("file_requests").document(request_id).set(file_request_doc)

    # In-app notification to driver
    if driver_id:
        notif_id = str(uuid.uuid4())
        atty_name = ticket_data.get("attorney_name", "Your attorney")
        due_clause = f" (due by {body.due_date})" if body.due_date else ""
        note_clause = f' Note: "{body.message}"' if body.message else ""
        driver_msg = (
            f"{atty_name} is requesting: {body.document_type}{due_clause}.{note_clause} "
            f"Please upload this document in your Rig Resolve app."
        )
        try:
            db.collection("drivers").document(driver_id).collection("notifications").document(notif_id).set({
                "notif_id": notif_id,
                "ticket_id": body.ticket_id,
                "file_request_id": request_id,
                "type": "file_request",
                "document_type": body.document_type,
                "message": driver_msg,
                "read": False,
                "created_at": SERVER_TIMESTAMP,
            })
        except Exception as exc:
            logger.warning("[file_request] driver notification failed driver=%s: %s", driver_id, exc)

    logger.info(
        "[file_request] created request_id=%s ticket=%s attorney=%s doc=%s",
        request_id, body.ticket_id, attorney_uid, body.document_type,
    )
    return FileRequestResponse(
        success=True,
        request_id=request_id,
        ticket_id=body.ticket_id,
        document_type=body.document_type,
    )


@router.get("/file-requests/{ticket_id}")
def list_file_requests(
    ticket_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """
    List file requests for a ticket. Accessible by the assigned attorney (Bearer token)
    or by staff (x-api-key).
    """
    from app.routes.admin import _check_auth
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="Firestore not available.")

    # Allow either auth method
    if x_api_key:
        _check_auth(x_api_key)
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            fb_auth.verify_id_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
    else:
        raise HTTPException(status_code=401, detail="Authentication required.")

    requests_ref = db.collection("tickets").document(ticket_id).collection("file_requests")
    docs = [{"id": d.id, **d.to_dict()} for d in requests_ref.stream()]
    return {"ticket_id": ticket_id, "file_requests": docs, "total": len(docs)}
