from __future__ import annotations
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response

from app.services.queue_store import (
    approve_item,
    get_field_audit,
    get_image_bytes,
    get_item,
    list_recent,
    reject_item,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_auth(x_api_key: Optional[str]):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


class ApproveRequest(BaseModel):
    edited_fields: dict = {}
    reviewer_id: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str = ""


from pydantic import BaseModel  # noqa: E402 — keep after class definitions above


@router.get("/queue")
async def get_queue(x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    return list_recent(limit=50)


@router.get("/queue/{item_id}")
async def get_queue_item(item_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
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
    x_api_key: Optional[str] = Header(None),
):
    """Proxy a scan page image from Firebase Storage. Returns JPEG bytes."""
    _check_auth(x_api_key)
    image_bytes = get_image_bytes(item_id, page)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    return Response(content=image_bytes, media_type="image/jpeg")


@router.put("/queue/{item_id}/approve")
async def approve_queue_item(
    item_id: str,
    body: ApproveRequest,
    x_api_key: Optional[str] = Header(None),
):
    _check_auth(x_api_key)
    item = get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    try:
        approve_item(item_id, body.edited_fields, reviewer_id=body.reviewer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": item_id, "status": "approved"}


@router.put("/queue/{item_id}/reject")
async def reject_queue_item(
    item_id: str,
    body: RejectRequest,
    x_api_key: Optional[str] = Header(None),
):
    _check_auth(x_api_key)
    try:
        reject_item(item_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": item_id, "status": "rejected"}


@router.get("/queue/{item_id}/audit")
async def get_queue_audit(item_id: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    return {"scan_id": item_id, "audit": get_field_audit(item_id)}


@router.get("/training/export")
async def export_training(x_api_key: Optional[str] = Header(None)):
    """Export all approved training records as NDJSON."""
    _check_auth(x_api_key)
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
