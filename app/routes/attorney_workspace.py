"""
Attorney workspace — Wallet/payouts (Slice 5), document requests + file viewer
(Slice 4), and client upload links (Slice 6). Dashboard Eng Spec v2 §5/§6.

Firebase token auth for attorney/staff routes; the client-link submit is public.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from app.routes._common import get_db, verify_token, require_staff, iso
from app.services import case_lifecycle as cl

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-workspace"])


def _now():
    return datetime.now(timezone.utc)


# ── Wallet (Slice 5) ─────────────────────────────────────────────────────────
@router.get("/wallet/summary")
def wallet_summary(authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    return cl.wallet_summary(get_db(), decoded["uid"])


@router.post("/wallet/checkout")
def wallet_checkout(authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    try:
        res = cl.create_payout_request(get_db(), decoded["uid"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Honest manual-payout messaging (§7.4). Timeframe is a placeholder pending §9.4.
    return {**res, "message": "Payout requested. Payouts are processed manually, "
                              "typically within 5–7 business days."}


# ── Availability (self-toggle) ────────────────────────────────────────────────
class AcceptingCasesUpdate(BaseModel):
    accepting_cases: bool


@router.get("/profile/accepting-cases")
def get_accepting_cases(authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    snap = get_db().collection("attorneys").document(decoded["uid"]).get()
    accepting = snap.to_dict().get("accepting_cases", True) if snap.exists else True
    return {"accepting_cases": accepting}


@router.patch("/profile/accepting-cases")
def update_accepting_cases(body: AcceptingCasesUpdate, authorization: Optional[str] = Header(None)):
    """Attorney self-toggle for whether they're currently accepting new cases."""
    decoded = verify_token(authorization)
    ref = get_db().collection("attorneys").document(decoded["uid"])
    ref.set({"accepting_cases": body.accepting_cases, "updated_at": _now()}, merge=True)
    return {"ok": True, "accepting_cases": body.accepting_cases}


# Admin-console routes (frontend-qa): staff Firebase Bearer token auth.
@router.get("/admin/payout-requests")
def admin_payout_requests(status: Optional[str] = None, authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    return {"payout_requests": cl.list_payout_requests(get_db(), status)}


class MarkPaid(BaseModel):
    paid_by: str
    payout_method: str = "Manual"


@router.post("/admin/payout-requests/{payout_id}/mark-paid")
def admin_mark_paid(payout_id: str, body: MarkPaid, authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    try:
        return cl.mark_payout_paid(get_db(), payout_id, body.payout_method, body.paid_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Case updates + document requests + files (Slice 4) ───────────────────────
class CaseUpdate(BaseModel):
    message: str
    category: Optional[str] = None


@router.post("/cases/{ticket_id}/updates")
def add_case_update(ticket_id: str, body: CaseUpdate, authorization: Optional[str] = Header(None)):
    """Attorney-authored update → shared case activity timeline."""
    decoded = verify_token(authorization)
    db = get_db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    ref = db.collection("tickets").document(ticket_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    _, doc = ref.collection("activity").add({
        "author_uid": decoded["uid"],
        "author_name": decoded.get("name") or decoded.get("email") or "Attorney",
        "category": body.category or "Attorney Note",
        "message": body.message, "created_at": SERVER_TIMESTAMP,
    })
    ref.update({"last_activity_at": SERVER_TIMESTAMP})
    return {"ok": True, "activity_id": doc.id}


class DocRequest(BaseModel):
    requested_from: str            # "driver" | "external_client"
    description: str


@router.post("/cases/{ticket_id}/document-requests")
def create_doc_request(ticket_id: str, body: DocRequest, authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    if body.requested_from not in ("driver", "external_client"):
        raise HTTPException(status_code=400, detail="requested_from must be 'driver' or 'external_client'.")
    db = get_db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    req_id = str(uuid.uuid4())
    db.collection("document_requests").document(req_id).set({
        "ticket_id": ticket_id, "requested_by_attorney_id": decoded["uid"],
        "requested_from": body.requested_from, "description": body.description,
        "status": "requested", "requested_at": SERVER_TIMESTAMP,
        "fulfilled_at": None, "file_urls": [],
    })
    # Notify the driver via the concierge pattern; external clients are notified via
    # their upload link out of band (no app/notification channel).
    if body.requested_from == "driver":
        tsnap = db.collection("tickets").document(ticket_id).get()
        driver_id = (tsnap.to_dict() or {}).get("driver_id")
        if driver_id:
            try:
                from app.services.anansi import anansi_notify
                anansi_notify(driver_id, ticket_id, "Document Requested",
                              context={"description": body.description})
            except Exception as exc:
                logger.warning("[workspace] driver doc-request notify failed: %s", exc)
    return {"ok": True, "document_request_id": req_id}


@router.get("/cases/{ticket_id}/document-requests")
def list_doc_requests(ticket_id: str, authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    db = get_db()
    docs = db.collection("document_requests").where("ticket_id", "==", ticket_id).stream()
    out = [{"document_request_id": d.id, **{k: iso(v) for k, v in d.to_dict().items()}} for d in docs]
    return {"document_requests": out}


@router.get("/cases/{ticket_id}/files")
def case_files(ticket_id: str, authorization: Optional[str] = Header(None)):
    """Ticket images, requested-file uploads, and MVR/PSP (graceful when absent)."""
    verify_token(authorization)
    db = get_db()
    tsnap = db.collection("tickets").document(ticket_id).get()
    if not tsnap.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    t = tsnap.to_dict()
    requested_files = []
    for d in db.collection("document_requests").where("ticket_id", "==", ticket_id).stream():
        dd = d.to_dict()
        for url in dd.get("file_urls") or []:
            requested_files.append({"url": url, "description": dd.get("description")})
    driver_files = []
    for snap in tsnap.reference.collection("driver_documents").stream():
        document = snap.to_dict() or {}
        path = document.get("storage_path")
        if not path:
            continue
        try:
            from firebase_admin import storage

            url = storage.bucket().blob(path).generate_signed_url(
                version="v4",
                expiration=900,
                method="GET",
            )
        except Exception:
            # Do not leak a private storage path when signing is unavailable.
            continue
        driver_files.append({
            "document_id": snap.id,
            "url": url,
            "description": document.get("label"),
            "file_name": document.get("file_name"),
            "content_type": document.get("content_type"),
        })
    return {
        "ticket_images": t.get("image_urls") or t.get("attachments") or [],
        "requested_documents": requested_files,
        "driver_documents": driver_files,
        "mvr": {"status": (t.get("mvr_request") or {}).get("status", "not_available")},
        "psp": {"status": (t.get("psp_request") or {}).get("status", "not_available")},
    }


# ── Client upload links (Slice 6) ────────────────────────────────────────────
class ClientLinkBody(BaseModel):
    label: Optional[str] = None
    max_uses: Optional[int] = None
    expires_in_days: Optional[int] = None


@router.post("/client-links")
def create_client_link(body: ClientLinkBody, authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    db = get_db()
    # Gate on the same self_sourced_enabled profile-completion threshold.
    a = db.collection("attorneys").document(decoded["uid"]).get()
    if not (a.exists and a.to_dict().get("self_sourced_enabled")):
        raise HTTPException(status_code=403, detail={"error": "profile_incomplete",
                            "message": "Complete your profile to generate client links."})
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    token = secrets.token_urlsafe(16)
    expires_at = None
    if body.expires_in_days:
        from datetime import timedelta
        expires_at = _now() + timedelta(days=body.expires_in_days)
    db.collection("client_upload_links").document(token).set({
        "attorney_id": decoded["uid"], "label": body.label, "external_client_id": None,
        "created_at": SERVER_TIMESTAMP, "expires_at": expires_at,
        "max_uses": body.max_uses, "uses_count": 0, "status": "active",
    })
    return {"ok": True, "token": token, "upload_path": f"/upload/{token}"}


@router.get("/client-links")
def list_client_links(authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    db = get_db()
    docs = db.collection("client_upload_links").where("attorney_id", "==", decoded["uid"]).stream()
    out = []
    for d in docs:
        dd = d.to_dict()
        out.append({"token": d.id, "label": dd.get("label"), "status": dd.get("status"),
                    "uses_count": dd.get("uses_count", 0), "max_uses": dd.get("max_uses"),
                    "expires_at": iso(dd.get("expires_at")), "upload_path": f"/upload/{d.id}"})
    return {"links": out}


@router.delete("/client-links/{token}")
def revoke_client_link(token: str, authorization: Optional[str] = Header(None)):
    decoded = verify_token(authorization)
    db = get_db()
    ref = db.collection("client_upload_links").document(token)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("attorney_id") != decoded["uid"]:
        raise HTTPException(status_code=404, detail="Link not found.")
    ref.update({"status": "revoked"})
    return {"ok": True}


@router.post("/client-links/{token}/submit")
async def client_link_submit(
    token: str,
    files: List[UploadFile] = File(...),
    client_name: str = Form(...),
    client_phone: Optional[str] = Form(None),
    client_email: Optional[str] = Form(None),
    cdl_number: Optional[str] = Form(None),
):
    """PUBLIC (no auth) — a client uploads their ticket via an attorney's link (§4.6)."""
    db = get_db()
    ref = db.collection("client_upload_links").document(token)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Link not found.")
    link = snap.to_dict()
    if link.get("status") != "active":
        raise HTTPException(status_code=410, detail="link_revoked")
    exp = link.get("expires_at")
    if hasattr(exp, "timestamp") and datetime.fromtimestamp(exp.timestamp(), tz=timezone.utc) < _now():
        raise HTTPException(status_code=410, detail="link_expired")
    if link.get("max_uses") and link.get("uses_count", 0) >= link["max_uses"]:
        raise HTTPException(status_code=410, detail="link_exhausted")

    attorney_id = link["attorney_id"]
    # Create the external client, then run the shared self-sourced pipeline.
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment
    client_id = link.get("external_client_id") or str(uuid.uuid4())
    if not link.get("external_client_id"):
        db.collection("external_clients").document(client_id).set({
            "attorney_id": attorney_id, "client_name": client_name,
            "client_phone": client_phone, "client_email": client_email,
            "cdl_number": cdl_number, "consent_on_file": True,  # client submitted directly
            "created_at": SERVER_TIMESTAMP,
        })

    import os
    from app.routes.process import process_ticket
    result = await process_ticket(
        files=files, source="attorney_self_sourced",
        attorney_id=attorney_id, external_client_id=client_id,
        x_api_key=os.getenv("API_KEY", "cdl-local-dev"),
    )
    ref.update({"uses_count": Increment(1),
                "external_client_id": client_id if not link.get("external_client_id") else link["external_client_id"]})
    try:
        cl.notify_attorney(db, attorney_id, "client_upload",
                           "New case from your client link",
                           f"{client_name} submitted a ticket via '{link.get('label') or 'your link'}'.")
        from app.services.attorney_levels import log_self_sourced
        log_self_sourced(db, attorney_id)
    except Exception as exc:
        logger.warning("[workspace] client-link post-process failed: %s", exc)
    return result
