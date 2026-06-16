import logging
import os
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.queue_store import (
    TRAINING_FILE,
    approve_item,
    get_field_audit,
    get_item,
    list_recent,
    reject_item,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_auth(x_api_key: str | None):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


class ApproveRequest(BaseModel):
    edited_fields: dict[str, str] = {}
    reviewer_id: str | None = None


class RejectRequest(BaseModel):
    reason: str = ""


@router.get("/queue")
async def get_queue(x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    return list_recent(limit=50)


@router.get("/queue/{item_id}")
async def get_queue_item(item_id: str, x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    item = get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    return item


@router.put("/queue/{item_id}/approve")
async def approve_queue_item(
    item_id: str,
    body: ApproveRequest,
    x_api_key: str | None = Header(None),
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
    x_api_key: str | None = Header(None),
):
    _check_auth(x_api_key)
    try:
        reject_item(item_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": item_id, "status": "rejected"}


@router.get("/queue/{item_id}/audit")
async def get_queue_audit(item_id: str, x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    return {"scan_id": item_id, "audit": get_field_audit(item_id)}


@router.get("/training/export")
async def export_training(x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    if not TRAINING_FILE.exists():
        raise HTTPException(status_code=404, detail="No training data yet.")
    return FileResponse(
        path=str(TRAINING_FILE),
        media_type="application/x-ndjson",
        filename="approved_tickets.jsonl",
        headers={"Content-Disposition": "attachment; filename=approved_tickets.jsonl"},
    )
