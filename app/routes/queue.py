import logging
import os
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.queue_store import (
    TRAINING_FILE,
    approve_item,
    get_item,
    list_recent,
    reject_item,
)
from app.services.salesforce import create_ticket as sf_create_ticket, ticket_url as sf_ticket_url

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_auth(x_api_key: str | None):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


class ApproveRequest(BaseModel):
    edited_fields: dict[str, str] = {}


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

    # Create Ticket__c in Salesforce (non-fatal if SF not configured)
    sf_id = None
    sf_url = None
    try:
        process_response = item.get("process_response", {})
        extracted = process_response.get("result", {})
        cdl_impact = process_response.get("cdl_point_impact")

        # Merge any reviewer edits over the original extracted values before sending to SF
        merged_extracted = dict(extracted)
        for field, new_val in body.edited_fields.items():
            if field in merged_extracted and isinstance(merged_extracted[field], dict):
                merged_extracted[field] = {**merged_extracted[field], "value": new_val}

        insp_num = (extracted.get("Insp_Report_Num__c") or {}).get("value", "") or None
        sf_id = sf_create_ticket(
            extracted_fields=merged_extracted,
            cdl_point_impact=cdl_impact,
            filename=item.get("filename", "unknown"),
            driver_name=process_response.get("filename", "").split(".")[0] or None,
            insp_report_num=insp_num,
        )
        if sf_id:
            sf_url = sf_ticket_url(sf_id)
            logger.warning("[queue] approve id=%s sf_ticket=%s", item_id, sf_id)
    except Exception as exc:
        logger.warning("[queue] SF create failed (non-fatal) id=%s error=%s", item_id, exc)

    try:
        approve_item(item_id, body.edited_fields, sf_ticket_id=sf_id, sf_ticket_url=sf_url)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"success": True, "id": item_id, "status": "approved",
            "sf_ticket_id": sf_id, "sf_ticket_url": sf_url}


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
