"""
Bring-Your-Own-Case (BYOC) — attorney self-sourced tickets (Dashboard spec Slice 4).

Firebase Bearer token auth. An attorney runs their OWN outside case through the
engine (feeds pricing/training data); it is NOT a Rig Resolve driver case.

  POST /self-sourced/clients   Create an external_clients/ record
  POST /self-sourced/process   Gate-check → (create client) → run /process as self-sourced

Gate (§3.1): self_sourced_enabled must be true — it flips on once the attorney's
profile_completion_pct crosses the configured threshold and bar status isn't flagged.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.services import attorney_levels as levels

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-self-sourced"])


def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _verify_token(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    try:
        return fb_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def _require_self_sourced_enabled(db, attorney_uid: str) -> None:
    snap = db.collection("attorneys").document(attorney_uid).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Attorney profile not found.")
    if not snap.to_dict().get("self_sourced_enabled"):
        # Message states the actual requirement, per brand voice (§6).
        raise HTTPException(
            status_code=403,
            detail={
                "error": "profile_incomplete",
                "message": "Complete your profile to unlock self-sourced cases.",
            },
        )


def _create_external_client(db, attorney_uid: str, *, name: str,
                            phone: Optional[str], email: Optional[str],
                            cdl_number: Optional[str], consent_on_file: bool) -> str:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    client_id = str(uuid.uuid4())
    db.collection("external_clients").document(client_id).set({
        "attorney_id": attorney_uid,
        "client_name": name,
        "client_phone": phone,
        "client_email": email,
        "cdl_number": cdl_number,
        "consent_on_file": bool(consent_on_file),
        "created_at": SERVER_TIMESTAMP,
    })
    logger.warning("[self_sourced] external client created id=%s attorney=%s", client_id, attorney_uid)
    return client_id


@router.post("/self-sourced/clients")
def create_client(
    client_name: str = Form(...),
    client_phone: Optional[str] = Form(None),
    client_email: Optional[str] = Form(None),
    cdl_number: Optional[str] = Form(None),
    consent_on_file: bool = Form(False),
    authorization: Optional[str] = Header(None),
):
    """Create a lightweight external client record (no driver account/subscription)."""
    decoded = _verify_token(authorization)
    db = _db()
    _require_self_sourced_enabled(db, decoded["uid"])
    client_id = _create_external_client(
        db, decoded["uid"], name=client_name, phone=client_phone,
        email=client_email, cdl_number=cdl_number, consent_on_file=consent_on_file,
    )
    return {"ok": True, "client_id": client_id}


@router.post("/self-sourced/process")
async def process_self_sourced(
    files: List[UploadFile] = File(...),
    external_client_id: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    client_phone: Optional[str] = Form(None),
    client_email: Optional[str] = Form(None),
    cdl_number: Optional[str] = Form(None),
    consent_on_file: bool = Form(False),
    authorization: Optional[str] = Header(None),
):
    """
    Run an attorney's own case through the engine. Creates the external client
    inline if external_client_id isn't supplied, then delegates to /process with
    source=attorney_self_sourced (skips enrollment + queue, lands as Accepted).
    """
    decoded = _verify_token(authorization)
    attorney_uid = decoded["uid"]
    db = _db()
    _require_self_sourced_enabled(db, attorney_uid)

    # Resolve or create the external client.
    if external_client_id:
        c = db.collection("external_clients").document(external_client_id).get()
        if not c.exists:
            raise HTTPException(status_code=404, detail="external_client_id not found.")
        if c.to_dict().get("attorney_id") != attorney_uid:
            raise HTTPException(status_code=403, detail="Client does not belong to you.")
        client_id = external_client_id
    else:
        if not client_name:
            raise HTTPException(status_code=400,
                                detail="Provide external_client_id or client_name.")
        client_id = _create_external_client(
            db, attorney_uid, name=client_name, phone=client_phone,
            email=client_email, cdl_number=cdl_number, consent_on_file=consent_on_file,
        )

    # Delegate to the shared processing pipeline (internal call with server API key).
    from app.routes.process import process_ticket
    result = await process_ticket(
        files=files,
        source="attorney_self_sourced",
        attorney_id=attorney_uid,
        external_client_id=client_id,
        x_api_key=os.getenv("API_KEY", "cdl-local-dev"),
    )

    # Levels owns the self-sourced counters + XP event (§3.1 hands off here).
    try:
        levels.log_self_sourced(db, attorney_uid)
    except Exception as exc:
        logger.warning("[self_sourced] log_self_sourced failed attorney=%s: %s", attorney_uid, exc)

    return result
