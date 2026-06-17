from __future__ import annotations
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.models.response import AttorneyMatch, CourtInfo, CountyCourt, DocumentResult, ExtractedField, ProcessResponse, PriceEstimate, TicketResponse
from app.services.attorney_matching import AttorneyMatch as RawAttorneyMatch
from app.services.cdl_points import estimate_cdl_points
from app.services.doc_scoring import score_document
from app.services.payment_options import calculate_payment_options
from app.services.preprocessor import image_file_to_base64, pdf_to_images_and_text
from app.services.pricing import get_price_estimate
from app.services.queue_store import cache_get, cache_set, get_item, save_scan
from app.services.textract_service import extract_word_positions
from app.services.firebase_service import write_scan_result
from app.services.court_lookup import lookup_court
from orchestrator.graph import ticket_graph

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
}


_DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
    "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
    "%d/%m/%Y", "%d-%m-%Y",
]


def _artificial_court_date(ticket_date_str: str, days: int = 10) -> Optional[str]:
    """Parse ticket issue date and return a date `days` later as MM/DD/YYYY."""
    s = (ticket_date_str or "").strip()
    if not s:
        return None
    try:
        from dateutil import parser as du
        dt = du.parse(s, dayfirst=False)
        return (dt + timedelta(days=days)).strftime("%m/%d/%Y")
    except Exception:
        pass
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return (dt + timedelta(days=days)).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return None


def _days_from_ai_reason(ai_reason: str) -> Optional[int]:
    """
    Scan Court_Date__c ai_reason for explicit day-count language the AI detected
    but didn't calculate (e.g. 'pay or respond within 30 days').
    Returns the day count if found and plausible (7–90), else None.
    """
    if not ai_reason:
        return None
    matches = re.findall(r'\b(\d+)\s+days?\b', ai_reason, re.IGNORECASE)
    for m in matches:
        n = int(m)
        if 7 <= n <= 90:
            return n
    return None


def _parse_violation_items(value: str) -> Optional[list[str]]:
    """
    Split a Violation_Description__c value into a list when multiple violations exist.
    Handles numbered list format ('1. ... \\n2. ...') and legacy semicolon format.
    Returns None for single violations (no split needed).
    """
    if not value:
        return None
    # Numbered list: "1. ...\n2. ..."
    numbered = re.split(r'\n\d+\.\s+', value)
    if len(numbered) > 1:
        # Re-attach the first item (which won't have a leading number after split)
        first = re.sub(r'^\d+\.\s+', '', numbered[0]).strip()
        rest = [v.strip() for v in numbered[1:] if v.strip()]
        items = ([first] if first else []) + rest
        return items if len(items) > 1 else None
    # Legacy semicolon format: "Speeding; No Seatbelt"
    semi = [v.strip() for v in re.split(r';\s*', value) if v.strip()]
    if len(semi) > 1:
        return semi
    return None


def _check_auth(x_api_key: Optional[str]):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


@router.post("/process", response_model=ProcessResponse)
async def process_ticket(
    files: List[UploadFile] = File(...),
    driver_name: Optional[str] = Form(None),
    driver_id: Optional[str] = Form(None),
    ticket_id: Optional[str] = Form(None),
    prompt_version: str = Form("v2"),
    x_api_key: Optional[str] = Header(None),
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

    # Check document cache — skip pipeline for identical uploads
    content_hash = hashlib.sha256("".join(images_b64).encode()).hexdigest()
    cached_scan_id = cache_get(content_hash)
    if cached_scan_id:
        cached_item = get_item(cached_scan_id)
        if cached_item:
            logger.warning("[process] CACHE HIT file=%s hash=%s → scan=%s", filename, content_hash[:12], cached_scan_id)
            cached_resp = cached_item["process_response"]
            new_queue_id = str(uuid.uuid4())
            cached_resp["queue_id"] = new_queue_id
            cached_resp["filename"] = filename
            cached_resp["cached"] = True
            save_scan(
                id=new_queue_id,
                filename=filename,
                pass_status=cached_resp.get("pass_status", "unknown"),
                images_b64=images_b64,
                process_response_json=json.dumps(cached_resp),
                doc_type=cached_resp.get("result", {}).get("file_type", "Ticket"),
                prompt_version=prompt_version,
            )
            if driver_id and ticket_id:
                write_scan_result(driver_id, ticket_id, cached_resp)
            return JSONResponse(content=cached_resp)

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
            "jurisdiction_context": None,
            "attorney_matches": [],
            "no_attorney_flag": True,
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

    # Artificial court date — generated when the document has no court date.
    # Rule priority:
    #   1. If ticket says "pay within 30 days" (or any X days) → ticket date + X days
    #   2. Default → ticket date + 10 days
    # The attorney can update the real court date once confirmed with the court.
    artificial_court_date_applied = False
    if not ticket_result.Court_Date__c.value and ticket_result.Date_of_Ticket__c.value:
        court_ai_reason = ticket_result.Court_Date__c.ai_reason or ""
        art_days = _days_from_ai_reason(court_ai_reason) or 10
        art_date = _artificial_court_date(ticket_result.Date_of_Ticket__c.value, days=art_days)
        if art_date:
            if art_days != 10:
                rule_note = (f"Document states a {art_days}-day payment/response window — "
                             f"placeholder set to {art_days} days from ticket issue date.")
            else:
                rule_note = "No day-count rule found on document — placeholder set to 10 days from ticket issue date."
            art_field = ExtractedField(
                value=art_date,
                confidence_score=0.0,
                ai_reason=(
                    f"ARTIFICIAL DATE — no court date found on document. {rule_note} "
                    f"(Ticket issued: {ticket_result.Date_of_Ticket__c.value}.) "
                    "CDL Legal will contact the court to obtain and update the real court date. "
                    "Attorney can update this date once confirmed."
                ),
            )
            ticket_result = ticket_result.model_copy(update={"Court_Date__c": art_field})
            artificial_court_date_applied = True
            logger.warning("[court_date] ARTIFICIAL file=%s days=%d ticket_date=%r → art_date=%s",
                           filename, art_days, ticket_result.Date_of_Ticket__c.value, art_date)

    # Parse Violation_Description__c into a numbered list when multiple violations exist
    vd = ticket_result.Violation_Description__c
    if vd.value:
        violation_items = _parse_violation_items(vd.value)
        if violation_items:
            ticket_result = ticket_result.model_copy(
                update={"Violation_Description__c": vd.model_copy(update={"items": violation_items})}
            )
            logger.warning("[violations] file=%s split into %d items", filename, len(violation_items))

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

    # Attorney matching — results come from Team Quest graph node
    ticket_county = (ticket_fields.get("Ticket_County__c") or {}).get("value", "")
    atty_matches_raw: list[RawAttorneyMatch] = result_state.get("attorney_matches") or []
    no_atty: bool = result_state.get("no_attorney_flag", len(atty_matches_raw) == 0)
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

    # Court lookup
    court_info = None
    raw_court = lookup_court(ticket_state, ticket_county, ticket_violation)
    if raw_court:
        county_court = None
        if raw_court.get("county_court"):
            cc = raw_court["county_court"]
            county_court = CountyCourt(
                county=cc.get("county", ""),
                court_name=cc.get("court_name", ""),
                website=cc.get("website", ""),
                scheduling_url=cc.get("scheduling_url", ""),
                phone=cc.get("phone", ""),
                address=cc.get("address", ""),
                notes=cc.get("notes", ""),
            )
        court_info = CourtInfo(
            state=raw_court["state"],
            state_name=raw_court["state_name"],
            court_system=raw_court["court_system"],
            state_portal=raw_court["state_portal"],
            online_payment_url=raw_court["online_payment_url"],
            scheduling_url=raw_court["scheduling_url"],
            cdl_info_url=raw_court["cdl_info_url"],
            appear_required_for_serious=raw_court["appear_required_for_serious"],
            appear_required=raw_court["appear_required"],
            notes=raw_court["notes"],
            county_court=county_court,
        )
        logger.warning("[court] state=%r county=%r → %s", ticket_state, ticket_county,
                       raw_court.get("county_court", {}).get("court_name") if raw_court.get("county_court") else raw_court["court_system"])

    # CDL point estimation — state + violation + zone flags from extracted fields
    cdl_point_est = None
    if ticket_state and ticket_violation:
        school_zone_val = (ticket_fields.get("School_Zone__c") or {}).get("value", "")
        construction_zone_val = (ticket_fields.get("Construction_Zone__c") or {}).get("value", "")
        try:
            cdl_point_est = estimate_cdl_points(
                state=ticket_state,
                violation_category=ticket_violation,
                school_zone=(school_zone_val.lower() == "yes"),
                construction_zone=(construction_zone_val.lower() == "yes"),
            )
            if cdl_point_est:
                logger.warning("[cdl_points] file=%s state=%r cat=%r → %s risk=%s",
                               filename, ticket_state, ticket_violation,
                               cdl_point_est.state_points_display, cdl_point_est.disqualification_risk)
        except Exception as exc:
            logger.warning("[cdl_points] estimation failed file=%s: %s", filename, exc)

    # Payment options — based on attorney fee + court date distance
    payment_opts = None
    if price_est and price_est.driver_price_base > 0:
        court_date_val = ticket_result.Court_Date__c.value if ticket_result.Court_Date__c else ""
        try:
            payment_opts = calculate_payment_options(
                base_amount=float(price_est.driver_price_base),
                court_date_str=court_date_val or None,
            )
            if payment_opts:
                logger.warning("[payment_opts] file=%s base=$%.0f days=%s plans=%d",
                               filename, payment_opts.base_amount,
                               payment_opts.days_until_court, len(payment_opts.options))
        except Exception as exc:
            logger.warning("[payment_opts] calculation failed file=%s: %s", filename, exc)

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
        artificial_court_date=artificial_court_date_applied,
        court_info=court_info,
        cdl_point_estimate=cdl_point_est,
        payment_options=payment_opts,
        result=ticket_result,
    )

    try:
        save_scan(
            id=queue_id,
            filename=filename,
            pass_status=final.get("pass_status", "unknown"),
            images_b64=images_b64,
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
    else:
        cache_set(content_hash, queue_id)

    # Write results to Firestore so the driver app updates in real-time
    if driver_id and ticket_id:
        write_scan_result(driver_id, ticket_id, response.model_dump())

    return response
