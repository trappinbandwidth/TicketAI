from __future__ import annotations
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.queue_store import (
    approval_documents,
    approve_item,
    get_field_audit,
    get_image_bytes,
    get_item,
    list_recent,
    reject_item,
)
from app.services.auth_rbac import require_staff, verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_auth(x_api_key: Optional[str]):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _authorize_staff_or_integration(
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> Optional[dict]:
    """Use a staff identity for browsers; retain the key for non-browser jobs."""
    if authorization:
        return require_staff(verify_firebase_token(authorization))
    _check_auth(x_api_key)
    return None


class ApproveRequest(BaseModel):
    edited_fields: dict = {}
    reviewer_id: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str = ""


class ReviewDecisionRequest(BaseModel):
    action: str
    ticket_id: str
    edited_fields: dict = {}
    reason: str = ""


@router.get("/queue")
async def get_queue(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    _authorize_staff_or_integration(authorization, x_api_key)
    return list_recent(limit=50)


@router.get("/queue/{item_id}")
async def get_queue_item(
    item_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    _authorize_staff_or_integration(authorization, x_api_key)
    item = get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    # Strip raw image data from the detail response — frontend fetches images via /image/{page}
    item.pop("image_b64", None)
    item.pop("images_b64_json", None)
    return item


@router.get("/queue/{item_id}/image/{page}")
async def get_queue_image(
    item_id: str,
    page: int,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """Proxy a scan page image from Firebase Storage. Returns JPEG bytes."""
    _authorize_staff_or_integration(authorization, x_api_key)
    image_bytes = get_image_bytes(item_id, page)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    return Response(content=image_bytes, media_type="image/jpeg")


@router.put("/queue/{item_id}/approve")
async def approve_queue_item(
    item_id: str,
    body: ApproveRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    actor = _authorize_staff_or_integration(authorization, x_api_key)
    item = get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    try:
        reviewer_id = actor.get("uid") if actor else body.reviewer_id
        approve_item(item_id, body.edited_fields, reviewer_id=reviewer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": item_id, "status": "approved"}


@router.put("/queue/{item_id}/reject")
async def reject_queue_item(
    item_id: str,
    body: RejectRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    _authorize_staff_or_integration(authorization, x_api_key)
    try:
        reject_item(item_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": item_id, "status": "rejected"}


@router.get("/queue/{item_id}/audit")
async def get_queue_audit(
    item_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    _authorize_staff_or_integration(authorization, x_api_key)
    return {"scan_id": item_id, "audit": get_field_audit(item_id)}


@router.post("/queue/{item_id}/decision")
async def decide_queue_item(
    item_id: str,
    body: ReviewDecisionRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """Commit the scan decision and linked ticket lifecycle together."""
    actor = _authorize_staff_or_integration(authorization, x_api_key)
    if actor is None:
        raise HTTPException(
            status_code=403,
            detail="A staff identity is required for review decisions.",
        )
    if body.action not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Action must be approve or reject.")
    if body.action == "reject" and not body.reason.strip():
        raise HTTPException(status_code=422, detail="A rejection reason is required.")

    from app.services.queue_store import _fs, _serialize, _now
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    db = _fs()
    scan_ref = db.collection("scan_queue").document(item_id)
    ticket_ref = db.collection("tickets").document(body.ticket_id)
    scan_snap = scan_ref.get()
    ticket_snap = ticket_ref.get()
    if not scan_snap.exists:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if not ticket_snap.exists:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    scan = _serialize(scan_snap)
    ticket = ticket_snap.to_dict() or {}
    if ticket.get("ai_scan_id") != item_id:
        raise HTTPException(
            status_code=409,
            detail="Queue item does not belong to the selected ticket.",
        )

    target_scan = "approved" if body.action == "approve" else "rejected"
    target_ticket = "New" if body.action == "approve" else "Rejected"
    if scan.get("status") == target_scan and ticket.get("attorney_status") == target_ticket:
        return {
            "success": True,
            "action": body.action,
            "idempotent_replay": True,
        }
    if scan.get("status") in {"approved", "rejected"} or ticket.get("attorney_status") != "AI Review":
        raise HTTPException(
            status_code=409,
            detail="Review state changed. Reload before deciding.",
        )

    actor_id = actor.get("email") or actor.get("uid") or actor.get("sub") or "staff"
    batch = db.batch()
    if body.action == "approve":
        queue_update, audits, training = approval_documents(
            scan, body.edited_fields, actor_id,
        )
        batch.update(scan_ref, queue_update)
        for audit_id, audit in audits:
            batch.set(scan_ref.collection("field_audit").document(audit_id), audit)
        batch.set(db.collection("training_records").document(item_id), training)
        batch.update(ticket_ref, {
            "attorney_status": "New",
            "reviewed_by": actor_id,
            "reviewed_at": SERVER_TIMESTAMP,
            "last_modified_date": SERVER_TIMESTAMP,
        })
    else:
        batch.update(scan_ref, {
            "status": "rejected",
            "updated_at": _now(),
            "reject_reason": body.reason.strip(),
            "reviewed_by": actor_id,
        })
        batch.update(ticket_ref, {
            "attorney_status": "Rejected",
            "rejection_reason": body.reason.strip(),
            "last_modified_date": SERVER_TIMESTAMP,
        })
    batch.set(
        db.collection("captain_action_audits").document(
            f"review_{body.action}_{item_id}_{body.ticket_id}"
        ),
        {
            "action": f"ticket_review_{body.action}",
            "scan_id": item_id,
            "ticket_id": body.ticket_id,
            "actor_id": actor_id,
            "reason": body.reason.strip() or None,
            "created_at": SERVER_TIMESTAMP,
        },
    )
    try:
        batch.commit()
    except Exception as exc:
        logger.exception(
            "[queue] atomic review failed scan=%s ticket=%s",
            item_id,
            body.ticket_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Review decision was not committed. It is safe to retry.",
        ) from exc
    return {
        "success": True,
        "action": body.action,
        "idempotent_replay": False,
    }


@router.get("/training/export")
async def export_training(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """Export all approved training records as NDJSON."""
    _authorize_staff_or_integration(authorization, x_api_key)
    from app.services.queue_store import _fs
    db = _fs()
    docs = list(db.collection("training_records").stream())
    if not docs:
        raise HTTPException(status_code=404, detail="No training data yet.")
    lines = "\n".join(json.dumps(d.to_dict()) for d in docs)
    return Response(
        content=lines.encode(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=approved_tickets.jsonl"},
    )
