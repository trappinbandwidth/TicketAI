"""
Lone Ranger — primary extraction agent.
Runs the master prompt against the ticket image + OCR text.
First agent in the pipeline.
"""
from __future__ import annotations

import logging

from app.services.claude_client import process_document
from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)

AGENT_NAME = "lone_ranger"


def _field_summary(extraction: dict) -> dict:
    """Build a compact per-field summary for agent event logging."""
    summary = {}
    for k, v in extraction.items():
        if isinstance(v, dict) and "confidence_score" in v:
            summary[k] = {
                "value": v.get("value", ""),
                "confidence_score": v.get("confidence_score", 0.0),
                "empty": not bool(v.get("value", "").strip()),
            }
    return summary


def _run_extraction(state: TicketState, pass_num: int, temperature: float) -> tuple[dict, bool, dict | None]:
    filename = state.get("filename", "unknown")
    scan_id = state.get("scan_id", "")
    prompt_version = state.get("prompt_version", "v1")
    logger.warning("[lone_ranger] pass=%d START file=%s temp=%.2f", pass_num, filename, temperature)

    log_agent_event(scan_id, AGENT_NAME, f"pass_{pass_num}_start", {
        "filename": filename,
        "temperature": temperature,
        "prompt_version": prompt_version,
        "pages": len(state.get("images_b64", [])),
    })

    try:
        extraction, is_mock, usage = process_document(
            images_b64=state["images_b64"],
            ocr_text=state["ocr_text"],
            driver_name=state.get("driver_name"),
            prompt_version=prompt_version,
            temperature=temperature,
        )
        field_summary = _field_summary(extraction)
        filled = sum(1 for v in field_summary.values() if not v["empty"])
        total = len(field_summary)
        empty_fields = [k for k, v in field_summary.items() if v["empty"]]
        low_conf_fields = [k for k, v in field_summary.items() if not v["empty"] and v["confidence_score"] < 0.6]

        logger.warning("[lone_ranger] pass=%d OK file=%s fields=%d/%d empty=%s",
                       pass_num, filename, filled, total, empty_fields[:5])

        log_agent_event(scan_id, AGENT_NAME, f"pass_{pass_num}_complete", {
            "is_mock": is_mock,
            "fields_filled": filled,
            "fields_total": total,
            "empty_fields": empty_fields,
            "low_confidence_fields": low_conf_fields,
            "doc_type": extraction.get("file_type", "unknown"),
            "field_summary": field_summary,
            "usage": usage,
        })
        return extraction, is_mock, usage

    except Exception as exc:
        logger.error("[lone_ranger] pass=%d FAILED file=%s error=%s", pass_num, filename, exc, exc_info=True)
        log_agent_event(scan_id, AGENT_NAME, f"pass_{pass_num}_error", {
            "error": str(exc),
        })
        raise


def lone_ranger(state: TicketState) -> dict:
    filename = state.get("filename", "unknown")
    logger.warning("[lone_ranger] START file=%s pages=%d ocr_chars=%d",
                   filename,
                   len(state.get("images_b64", [])),
                   len(state.get("ocr_text", "")))
    extraction, is_mock, usage = _run_extraction(state, pass_num=1, temperature=1.0)
    token_usage = list(state.get("token_usage") or [])
    if usage:
        token_usage.append(usage)
    return {
        "extraction": extraction, "is_mock": is_mock, "pass1_extraction": extraction,
        "token_usage": token_usage,
    }


def lone_ranger_2(state: TicketState) -> dict:
    """Second extraction pass — only runs for non-green tickets (fast-path skip for green)."""
    extraction, _, usage = _run_extraction(state, pass_num=2, temperature=0.4)
    token_usage = list(state.get("token_usage") or [])
    if usage:
        token_usage.append(usage)
    return {"extraction_2": extraction, "pass2_extraction": extraction, "token_usage": token_usage}
