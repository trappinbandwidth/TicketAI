import logging
import os
import uuid
from typing import List
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.models.response import AttorneyMatch, DocumentResult, ProcessResponse, PriceEstimate, TicketResponse
from app.services.attorney_matching import find_attorneys
from app.services.doc_scoring import score_document
from app.services.preprocessor import image_file_to_base64, pdf_to_images_and_text
from app.services.pricing import get_price_estimate
from app.services.queue_store import save_scan
from app.services.textract_service import extract_word_positions
from orchestrator.graph import ticket_graph

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
}


def _check_auth(x_api_key: str | None):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


@router.post("/process", response_model=ProcessResponse)
async def process_ticket(
    files: List[UploadFile] = File(...),
    driver_name: str | None = Form(None),
    prompt_version: str = Form("v1"),
    x_api_key: str | None = Header(None),
):
    _check_auth(x_api_key)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images per ticket.")

    # Use the first file's name as the ticket filename
    filename = files[0].filename or "unknown"

    # Combine pages from all uploaded files in order
    images_b64: list[str] = []
    ocr_parts:  list[str] = []

    for f in files:
        content_type = f.content_type or ""
        file_kind = SUPPORTED_TYPES.get(content_type)
        if not file_kind:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type: {content_type} ({f.filename}). Send PDF, JPG, or PNG.",
            )
        raw_bytes = await f.read()
        if file_kind == "pdf":
            imgs, txt = pdf_to_images_and_text(raw_bytes)
        else:
            imgs, txt = image_file_to_base64(raw_bytes, content_type)
        images_b64.extend(imgs)
        if txt:
            ocr_parts.append(txt)

    ocr_text = "\n\n---\n\n".join(ocr_parts) if ocr_parts else ""
    logger.warning("[process] file=%s total_pages=%d from %d file(s)", filename, len(images_b64), len(files))

    # Extract word-level bounding boxes via Textract (no-op if AWS creds not set)
    word_positions = extract_word_positions(images_b64)

    queue_id = str(uuid.uuid4())

    # Run the full agent graph
    try:
        result_state = ticket_graph.invoke({
            "images_b64": images_b64,
            "ocr_text": ocr_text,
            "driver_name": driver_name,
            "filename": filename,
            "prompt_version": prompt_version,
            "scan_id": queue_id,
            "word_positions": word_positions,
            "extraction": None,
            "extraction_2": None,
            "pass1_extraction": None,
            "pass2_extraction": None,
            "consensus_extraction": None,
            "dual_conflicts": [],
            "is_mock": False,
            "pass_status": None,
            "low_confidence_fields": [],
            "referee_notes": None,
            "cdl_point_impact": None,
            "final_result": None,
            "escalation_reason": None,
        })
    except Exception as exc:
        logger.exception("ticket_graph.invoke failed for file=%s", filename)
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    final = result_state.get("final_result") or {}
    is_mock = result_state.get("is_mock", False)

    # Strip orchestration keys before building TicketResponse
    ticket_fields = {
        k: v for k, v in final.items()
        if k not in {"pass_status", "low_confidence_fields", "referee_notes",
                     "cdl_point_impact", "escalation_reason", "dual_conflicts"}
    }

    try:
        ticket_result = DocumentResult(**ticket_fields)
    except Exception as exc:
        logger.warning("TicketResponse validation failed, falling back to mock shape: %s", exc)
        # Return partial data rather than a 500 — escalate so a human can review
        raise HTTPException(
            status_code=422,
            detail=f"Extraction produced incomplete fields: {exc}",
        ) from exc

    # Build price estimate from extracted state + violation
    ticket_state = (ticket_fields.get("Ticket_State__c") or {}).get("value", "")
    ticket_violation = (ticket_fields.get("Violation_Category__c") or {}).get("value", "")
    price_est = None
    if ticket_state and ticket_violation:
        est = get_price_estimate(ticket_state, ticket_violation)
        price_est = PriceEstimate(
            avg_attny_price=est.avg_attny_price,
            cdl_fee=est.cdl_fee,
            driver_price_base=est.driver_price_base,
            driver_price_low=est.driver_price_low,
            driver_price_high=est.driver_price_high,
            win_rate_pct=est.win_rate_pct,
            sample_size=est.sample_size,
            high_risk=est.high_risk,
            data_source=est.data_source,
            display=(f"${est.driver_price_low:,} – ${est.driver_price_high:,}"
                     if est.driver_price_base > 0 else "Unavailable"),
            note=est.note,
        )
        logger.warning("[pricing] file=%s state=%r violation=%r → %s (source=%s)",
                       filename, ticket_state, ticket_violation,
                       price_est.display, price_est.data_source)

    # Attorney matching
    ticket_county = (ticket_fields.get("Ticket_County__c") or {}).get("value", "")
    atty_matches_raw, no_atty = find_attorneys(ticket_state, ticket_county)
    atty_matches = [
        AttorneyMatch(
            attorney_id=m.attorney_id,
            name=m.name,
            email=m.email,
            phone=m.phone,
            rating=m.rating,
            win_rate=m.win_rate,
            total_tickets=m.total_tickets,
            match_type=m.match_type,
        )
        for m in atty_matches_raw
    ]
    if no_atty:
        logger.warning("[attorney] NO ATTORNEY state=%r county=%r", ticket_state, ticket_county)

    # Severity scoring: tickets use cdl_point_impact (from orchestrator); all other types use doc_scoring
    doc_sev = None
    file_type = (ticket_fields.get("file_type") or "Ticket")
    if file_type != "Ticket":
        try:
            doc_sev = score_document(ticket_result)
        except Exception as exc:
            logger.warning("doc_scoring failed for file_type=%r: %s", file_type, exc)

    response = ProcessResponse(
        success=True,
        mock=is_mock,
        filename=filename,
        pages_processed=len(images_b64),
        pass_status=final.get("pass_status", "unknown"),
        low_confidence_fields=final.get("low_confidence_fields", []),
        referee_notes=final.get("referee_notes"),
        cdl_point_impact=final.get("cdl_point_impact"),
        doc_severity=doc_sev,
        escalation_reason=final.get("escalation_reason"),
        queue_id=queue_id,
        price_estimate=price_est,
        dual_conflicts=final.get("dual_conflicts", []),
        attorney_matches=atty_matches,
        no_attorney_flag=no_atty,
        result=ticket_result,
    )

    try:
        save_scan(
            id=queue_id,
            filename=filename,
            pass_status=final.get("pass_status", "unknown"),
            image_b64=images_b64[0] if images_b64 else "",
            process_response_json=response.model_dump_json(),
            pass1_extraction=result_state.get("pass1_extraction"),
            pass2_extraction=result_state.get("pass2_extraction"),
            consensus_extraction=result_state.get("consensus_extraction"),
            doc_type=file_type,
            prompt_version=prompt_version,
            attorney_matched=len(atty_matches) > 0,
            attorney_match_type=atty_matches[0].match_type if atty_matches else None,
            has_price_estimate=price_est is not None,
            price_estimate=price_est.model_dump() if price_est else None,
        )
    except Exception as exc:
        logger.warning("Failed to save scan to queue (non-fatal): %s", exc)

    return response
