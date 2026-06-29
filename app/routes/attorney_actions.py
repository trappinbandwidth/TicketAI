"""
Attorney-facing action endpoints — verified via Firebase ID token.
These are called from the attorney portal frontend, NOT by admin tooling.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_firebase_token(authorization: Optional[str]) -> dict:
    """Returns decoded token payload or raises 401."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required.")
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    try:
        import firebase_admin.auth as fb_auth
        decoded = fb_auth.verify_id_token(token)
        return decoded
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def _db():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


class DeclineCaseRequest(BaseModel):
    ticket_id: str
    reason: Optional[str] = None


@router.post("/decline-case")
def decline_case(
    body: DeclineCaseRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Attorney formally declines (passes on) a ticket.

    - Records the decline in tickets/{ticket_id}/declines/{attorney_id}
    - Does NOT change attorney_status — the ticket remains available to others
    - Prevents the same attorney from being matched again via team_quest

    Called by the attorney portal when an attorney explicitly passes.
    """
    decoded = _verify_firebase_token(authorization)
    attorney_id = decoded.get("uid", "")
    db = _db()

    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        ticket_ref = db.collection("tickets").document(body.ticket_id)
        ticket_doc = ticket_ref.get()
        if not ticket_doc.exists:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_id} not found.")

        data = ticket_doc.to_dict()
        if data.get("attorney_status") not in ("New", "AI Review"):
            return {
                "success": False,
                "message": f"Cannot decline — ticket status is '{data.get('attorney_status')}'.",
            }

        # Record the decline in a subcollection for audit + future matching exclusion
        decline_ref = ticket_ref.collection("declines").document(attorney_id)
        decline_ref.set({
            "attorney_id": attorney_id,
            "reason": body.reason or "",
            "declined_at": SERVER_TIMESTAMP,
        })

        # Also append to the ticket's declined_by array for easy query filtering
        ticket_ref.update({
            "declined_by": _array_union(attorney_id),
            "last_modified_date": SERVER_TIMESTAMP,
        })

        logger.warning(
            "[decline-case] attorney=%s declined ticket=%s reason=%r",
            attorney_id, body.ticket_id, body.reason,
        )
        return {
            "success": True,
            "ticket_id": body.ticket_id,
            "attorney_id": attorney_id,
            "message": "Ticket declined. It remains available to other attorneys.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _array_union(value: str):
    from google.cloud.firestore_v1 import ArrayUnion
    return ArrayUnion([value])
