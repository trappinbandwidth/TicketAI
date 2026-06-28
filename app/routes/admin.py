"""
Admin dashboard API routes.
All endpoints require the same API key as the process endpoint.
"""
from __future__ import annotations
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import FileResponse

from app.services.queue_store import EXTRACTED_FIELDS

logger = logging.getLogger(__name__)
router = APIRouter()

# Prompt section map: field_key → {section, description} for prompt drill-down
PROMPT_SECTION_MAP = {
    # Ticket / Warning
    "Date_of_Ticket__c":         {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Violation_Description__c":  {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Violation_Category__c":     {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Court_Date__c":             {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Accident__c":               {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Drivers_License_Type__c":   {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Ticket_Court__c":           {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Court_Phone_Number__c":     {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Ticket_City__c":            {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Ticket_County__c":          {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Ticket_State__c":           {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Citation_Number__c":        {"section": "Step 4 — Ticket Extraction", "step": 4},
    "Insp_Report_Num__c":        {"section": "Step 4 — Ticket Extraction", "step": 4},
    # Inspection Report
    "Inspection_Date__c":        {"section": "Step 2 — IR Extraction", "step": 2},
    "Inspection_Time__c":        {"section": "Step 2 — IR Extraction", "step": 2},
    "Inspection_State__c":       {"section": "Step 2 — IR Extraction", "step": 2},
    "Inspection_County__c":      {"section": "Step 2 — IR Extraction", "step": 2},
    "Inspection_City__c":        {"section": "Step 3 — IR Location", "step": 3},
    "Inspection_Location__c":    {"section": "Step 3 — IR Location", "step": 3},
    "DOT_Number__c":             {"section": "Step 2 — IR Extraction", "step": 2},
    "Inspection_Level__c":       {"section": "Step 2 — IR Extraction", "step": 2},
    "VIN__c":                    {"section": "Step 2 — IR Extraction", "step": 2},
    "Unit_Make__c":              {"section": "Step 2 — IR Extraction", "step": 2},
    "Driver_OOS__c":             {"section": "Step 2 — IR Extraction", "step": 2},
    "Vehicle_OOS__c":            {"section": "Step 2 — IR Extraction", "step": 2},
    "BASIC_Categories__c":       {"section": "Step 2 — IR Extraction", "step": 2},
    # Crash
    "Crash_Report_Number__c":    {"section": "Step 5 — Crash Extraction", "step": 5},
    "Crash_Date__c":             {"section": "Step 5 — Crash Extraction", "step": 5},
    "Crash_State__c":            {"section": "Step 5 — Crash Extraction", "step": 5},
    "Federal_Recordable__c":     {"section": "Step 5 — Crash Extraction", "step": 5},
    "Number_of_Fatalities__c":   {"section": "Step 5 — Crash Extraction", "step": 5},
    "Number_of_Injuries__c":     {"section": "Step 5 — Crash Extraction", "step": 5},
    # Civil Penalty
    "Civil_Penalty_Case_Number__c": {"section": "Step 6 — Civil Penalty Extraction", "step": 6},
    "Civil_Penalty_Amount__c":   {"section": "Step 6 — Civil Penalty Extraction", "step": 6},
    "Civil_Penalty_Due_Date__c": {"section": "Step 6 — Civil Penalty Extraction", "step": 6},
    # CDL
    "CDL_License_Number__c":     {"section": "Step 7 — CDL Extraction", "step": 7},
    "CDL_Class__c":              {"section": "Step 7 — CDL Extraction", "step": 7},
    "CDL_Expiration__c":         {"section": "Step 7 — CDL Extraction", "step": 7},
    # MVR
    "MVR_License_Number__c":     {"section": "Step 8 — MVR Extraction", "step": 8},
    "MVR_Total_Points__c":       {"section": "Step 8 — MVR Extraction", "step": 8},
    "MVR_Violations_Summary__c": {"section": "Step 8 — MVR Extraction", "step": 8},
}


def _check_auth(x_api_key: Optional[str]):
    expected = os.getenv("API_KEY", "cdl-local-dev")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _fs():
    """Return the Firestore client. Raises 503 if not configured."""
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


# ── Overview stats ──────────────────────────────────────────────────────────

@router.get("/admin/stats/overview")
def get_overview(days: int = 30, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _fs()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    docs = list(
        db.collection("scan_queue")
        .where("created_at", ">=", cutoff)
        .order_by("created_at", direction="DESCENDING")
        .stream()
    )

    total = len(docs)
    if total == 0:
        return {"total": 0, "days": days}

    pass_counts: dict[str, int] = defaultdict(int)
    doc_type_counts: dict[str, int] = defaultdict(int)
    daily_counts: dict[str, dict] = defaultdict(lambda: {"green": 0, "yellow": 0, "red": 0, "total": 0})
    attorney_matched = 0
    county_matches = 0
    price_estimated = 0

    for d in docs:
        r = d.to_dict()
        ps = r.get("pass_status") or "unknown"
        pass_counts[ps] += 1
        doc_type_counts[r.get("doc_type") or "Unknown"] += 1
        day = (r.get("created_at") or "")[:10]
        daily_counts[day]["total"] += 1
        if ps in ("green", "yellow", "red"):
            daily_counts[day][ps] += 1
        if r.get("attorney_matched"):
            attorney_matched += 1
            if r.get("attorney_match_type") == "county":
                county_matches += 1
        if r.get("has_price_estimate"):
            price_estimated += 1

    return {
        "total": total,
        "days": days,
        "pass_counts": dict(pass_counts),
        "green_rate": round(pass_counts["green"] / total, 3),
        "yellow_rate": round(pass_counts["yellow"] / total, 3),
        "red_rate": round(pass_counts["red"] / total, 3),
        "attorney_match_rate": round(attorney_matched / total, 3),
        "county_match_rate": round(county_matches / total, 3) if attorney_matched else 0,
        "price_estimate_rate": round(price_estimated / total, 3),
        "doc_type_breakdown": dict(doc_type_counts),
        "daily_volume": [{"date": d, **v} for d, v in sorted(daily_counts.items())],
    }


# ── Field performance ───────────────────────────────────────────────────────

@router.get("/admin/stats/fields")
def get_field_stats(doc_type: Optional[str] = None, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _fs()

    query = db.collection("training_records")
    if doc_type:
        query = query.where("doc_type", "==", doc_type)
    records = list(query.stream())

    if not records:
        return {"fields": [], "sample_size": 0}

    field_data: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0, "empty": 0,
        "edited": 0, "confidence_sum": 0.0, "conf_samples": 0,
        "pass1_filled": 0, "pass2_improved": 0,
    })

    sample_size = 0
    for doc in records:
        rec = doc.to_dict()
        if doc_type and rec.get("doc_type") != doc_type:
            continue
        sample_size += 1

        original = rec.get("original_extraction", {})
        final_vals = rec.get("final_values", {})
        feedback = rec.get("field_feedback", {})
        pass1 = rec.get("pass1_extraction", {})
        pass2 = rec.get("pass2_extraction", {})

        for field in set(list(original.keys()) + list(final_vals.keys())):
            if not field.endswith("__c") and field not in ("Insp_Report_Num__c",):
                continue
            orig = original.get(field, {})
            if not isinstance(orig, dict):
                continue

            fd = field_data[field]
            fd["total"] += 1

            ai_val = (orig.get("value") or "").strip()
            final_val = (final_vals.get(field) or "").strip()
            conf = orig.get("confidence_score", 0.0)

            if not ai_val:
                fd["empty"] += 1
            else:
                fd["confidence_sum"] += conf
                fd["conf_samples"] += 1

            if ai_val != final_val and final_val:
                fd["edited"] += 1

            # ✓/✗ explicit feedback
            fb = feedback.get(field)
            if fb == "correct":
                fd["correct"] += 1
            elif fb == "wrong":
                fd["wrong"] += 1
            elif ai_val and ai_val == final_val:
                fd["correct"] += 1  # no feedback but human didn't change it = correct
            elif ai_val and ai_val != final_val:
                fd["wrong"] += 1

            # Pass 1 vs pass 2 fill tracking
            p1 = pass1.get(field, {})
            p2 = pass2.get(field, {})
            if isinstance(p1, dict) and p1.get("value"):
                fd["pass1_filled"] += 1
            if isinstance(p2, dict) and p2.get("value") and (
                not isinstance(p1, dict) or not p1.get("value")
            ):
                fd["pass2_improved"] += 1

    results = []
    for field, fd in field_data.items():
        total = fd["total"]
        if total == 0:
            continue
        judged = fd["correct"] + fd["wrong"]
        accuracy = round(fd["correct"] / judged, 3) if judged > 0 else None
        avg_conf = round(fd["confidence_sum"] / fd["conf_samples"], 3) if fd["conf_samples"] > 0 else 0.0
        empty_rate = round(fd["empty"] / total, 3)
        edit_rate = round(fd["edited"] / total, 3)

        prompt_info = PROMPT_SECTION_MAP.get(field, {"section": "Unknown", "step": 99})

        results.append({
            "field": field,
            "accuracy": accuracy,
            "avg_confidence": avg_conf,
            "empty_rate": empty_rate,
            "edit_rate": edit_rate,
            "total": total,
            "correct": fd["correct"],
            "wrong": fd["wrong"],
            "edited": fd["edited"],
            "pass1_fill_rate": round(fd["pass1_filled"] / total, 3),
            "pass2_improvement_rate": round(fd["pass2_improved"] / total, 3),
            "prompt_section": prompt_info["section"],
            "prompt_step": prompt_info["step"],
        })

    # Sort by accuracy ascending (worst fields first)
    results.sort(key=lambda r: (r["accuracy"] is None, r["accuracy"] or 0))
    return {"fields": results, "sample_size": sample_size, "doc_type_filter": doc_type}


# ── Field drill-down ────────────────────────────────────────────────────────

@router.get("/admin/stats/fields/{field_key}")
def get_field_drilldown(field_key: str, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _fs()

    records = list(db.collection("training_records").stream())
    cases = []
    for doc in records:
        rec = doc.to_dict()
        original = rec.get("original_extraction", {})
        orig_field = original.get(field_key, {})
        if not isinstance(orig_field, dict):
            continue

        ai_val = (orig_field.get("value") or "").strip()
        final_val = (rec.get("final_values", {}).get(field_key) or "").strip()
        feedback = rec.get("field_feedback", {}).get(field_key)
        was_wrong = feedback == "wrong" or (ai_val != final_val and bool(final_val))

        pass1_val = ((rec.get("pass1_extraction") or {}).get(field_key) or {})
        pass2_val = ((rec.get("pass2_extraction") or {}).get(field_key) or {})

        cases.append({
            "scan_id": rec.get("scan_id") or doc.id,
            "filename": rec.get("filename"),
            "approved_at": rec.get("approved_at"),
            "doc_type": rec.get("doc_type"),
            "pass_status": rec.get("pass_status"),
            "ai_value": ai_val,
            "final_value": final_val,
            "confidence": orig_field.get("confidence_score", 0),
            "ai_reason": orig_field.get("ai_reason", ""),
            "was_wrong": was_wrong,
            "feedback": feedback,
            "pass1_value": pass1_val.get("value", "") if isinstance(pass1_val, dict) else "",
            "pass1_confidence": pass1_val.get("confidence_score", 0) if isinstance(pass1_val, dict) else 0,
            "pass2_value": pass2_val.get("value", "") if isinstance(pass2_val, dict) else "",
            "pass2_confidence": pass2_val.get("confidence_score", 0) if isinstance(pass2_val, dict) else 0,
        })

    cases.sort(key=lambda c: (not c["was_wrong"], c["approved_at"] or ""))
    prompt_info = PROMPT_SECTION_MAP.get(field_key, {"section": "Unknown", "step": 99})
    return {"field": field_key, "prompt_section": prompt_info["section"], "cases": cases}


# ── Agent scorecard ─────────────────────────────────────────────────────────

@router.get("/admin/stats/agents")
def get_agent_stats(days: int = 30, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _fs()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    # Collection-group query across all scan_queue/{id}/agent_events subcollections
    events = list(
        db.collection_group("agent_events")
        .where("created_at", ">=", cutoff)
        .stream()
    )

    agents: dict[str, dict] = {
        "lone_ranger": {
            "name": "Lone Ranger", "events": 0, "errors": 0,
            "pass1_fills": [], "pass1_empty_fields": defaultdict(int),
            "pass1_low_conf_fields": defaultdict(int),
            "pass2_fills": [], "improvements": [],
        },
        "referee": {
            "name": "Referee", "events": 0, "errors": 0,
            "scores": [], "critical_failures": defaultdict(int),
            "low_conf_fields": defaultdict(int),
            "false_escalations": 0,
        },
        "consensus": {
            "name": "Consensus", "events": 0, "errors": 0,
            "dual_conflicts": defaultdict(int),
            "improvements_per_scan": [],
        },
        "book_worm": {
            "name": "Book Worm", "events": 0, "errors": 0,
            "unknown_categories": [], "zero_point_tickets": 0,
            "attorney_recommended": 0,
        },
        # New agents
        "case_intake": {
            "name": "Case Intake", "events": 0, "errors": 0,
            "passed": 0, "failed": 0,
            "intake_error_counts": defaultdict(int),
        },
        "document_completeness": {
            "name": "Document Completeness", "events": 0, "errors": 0,
            "scores": [], "missing_field_counts": defaultdict(int),
        },
        "pii_match": {
            "name": "PII Match", "events": 0, "errors": 0,
            "matched": 0, "mismatched": 0, "unverified": 0,
            "not_found": 0, "skipped": 0,
        },
        "mvr_request": {
            "name": "MVR Request", "events": 0, "errors": 0,
            "queued": 0, "skipped": 0,
        },
        "psp_request": {
            "name": "PSP Request", "events": 0, "errors": 0,
            "queued": 0, "skipped": 0,
        },
        "urgency_router": {
            "name": "Urgency Router", "events": 0, "errors": 0,
            "level_counts": defaultdict(int),
            "no_court_date": 0,
            "days_until_court": [],
        },
    }

    for ev_doc in events:
        ev = ev_doc.to_dict() if hasattr(ev_doc, "to_dict") else ev_doc
        agent = ev.get("agent", "")
        event = ev.get("event", "")
        detail = ev.get("detail") or {}
        ag = agents.get(agent)
        if not ag:
            continue
        ag["events"] += 1

        if "error" in event:
            ag["errors"] += 1

        if agent == "lone_ranger":
            if event == "pass_1_complete":
                ag["pass1_fills"].append(detail.get("fields_filled", 0))
                for f in (detail.get("empty_fields") or []):
                    ag["pass1_empty_fields"][f] += 1
                for f in (detail.get("low_confidence_fields") or []):
                    ag["pass1_low_conf_fields"][f] += 1
            elif event == "pass_2_complete":
                ag["pass2_fills"].append(detail.get("fields_filled", 0))

        elif agent == "referee":
            if event == "scored":
                ag["scores"].append(detail.get("avg_score", 0))
                for f in (detail.get("critical_failures") or []):
                    ag["critical_failures"][f] += 1
                for f in (detail.get("low_confidence_fields") or []):
                    ag["low_conf_fields"][f] += 1

        elif agent == "consensus":
            if event == "merge_complete":
                ag["improvements_per_scan"].append(detail.get("improvements_count", 0))
                for f in (detail.get("dual_conflicts") or []):
                    ag["dual_conflicts"][f] += 1

        elif agent == "book_worm":
            if event == "scored":
                if detail.get("unknown_category"):
                    ag["unknown_categories"].append(detail.get("violation_category", ""))
                if detail.get("zero_points"):
                    ag["zero_point_tickets"] += 1
                if detail.get("attorney_recommended"):
                    ag["attorney_recommended"] += 1

        elif agent == "case_intake":
            if event == "passed":
                ag["passed"] += 1
            elif event == "failed":
                ag["failed"] += 1
                for err in (detail.get("errors") or []):
                    ag["intake_error_counts"][err] += 1

        elif agent == "document_completeness":
            if event == "complete":
                score = detail.get("completeness_score")
                if score is not None:
                    ag["scores"].append(score)
                for f in (detail.get("missing_fields") or []):
                    ag["missing_field_counts"][f] += 1

        elif agent == "pii_match":
            if event == "complete":
                match = detail.get("cdl_match", "unverified")
                if match == "match":
                    ag["matched"] += 1
                elif match == "mismatch":
                    ag["mismatched"] += 1
                else:
                    ag["unverified"] += 1
            elif event == "no_profile":
                ag["not_found"] += 1
            elif event == "skipped":
                ag["skipped"] += 1

        elif agent == "mvr_request":
            if event == "queued":
                ag["queued"] += 1
            elif event == "skipped":
                ag["skipped"] += 1

        elif agent == "psp_request":
            if event == "queued":
                ag["queued"] += 1
            elif event == "skipped":
                ag["skipped"] += 1

        elif agent == "urgency_router":
            if event == "complete":
                level = detail.get("urgency_level", "LOW")
                ag["level_counts"][level] += 1
                if detail.get("reason") == "no_court_date":
                    ag["no_court_date"] += 1
                days = detail.get("days_until_court")
                if days is not None:
                    ag["days_until_court"].append(days)

    # Build summary per agent
    results = []
    for agent_key, ag in agents.items():
        total_events = ag["events"]
        errors = ag["errors"]
        health = round(1 - (errors / max(total_events, 1)), 3)

        summary: dict = {
            "agent": agent_key,
            "name": ag["name"],
            "total_events": total_events,
            "errors": errors,
            "health_score": health,
        }

        if agent_key == "lone_ranger":
            fills = ag["pass1_fills"]
            summary["avg_pass1_fill_rate"] = round(sum(fills) / len(fills), 1) if fills else 0
            summary["top_empty_fields"] = sorted(ag["pass1_empty_fields"].items(), key=lambda x: -x[1])[:8]
            summary["top_low_conf_fields"] = sorted(ag["pass1_low_conf_fields"].items(), key=lambda x: -x[1])[:8]

        elif agent_key == "referee":
            scores = ag["scores"]
            summary["avg_confidence_score"] = round(sum(scores) / len(scores), 3) if scores else 0
            summary["top_critical_failures"] = sorted(ag["critical_failures"].items(), key=lambda x: -x[1])[:5]
            summary["top_low_conf_fields"] = sorted(ag["low_conf_fields"].items(), key=lambda x: -x[1])[:8]

        elif agent_key == "consensus":
            imps = ag["improvements_per_scan"]
            summary["avg_improvements_per_scan"] = round(sum(imps) / len(imps), 2) if imps else 0
            summary["top_dual_conflict_fields"] = sorted(ag["dual_conflicts"].items(), key=lambda x: -x[1])[:5]

        elif agent_key == "book_worm":
            summary["unknown_category_count"] = len(ag["unknown_categories"])
            summary["unknown_categories"] = list(set(ag["unknown_categories"]))[:10]
            summary["zero_point_ticket_count"] = ag["zero_point_tickets"]
            summary["attorney_recommended_count"] = ag["attorney_recommended"]

        elif agent_key == "case_intake":
            total_decided = ag["passed"] + ag["failed"]
            summary["passed"] = ag["passed"]
            summary["failed"] = ag["failed"]
            summary["fail_rate"] = round(ag["failed"] / total_decided, 3) if total_decided else 0
            summary["top_intake_errors"] = sorted(
                ag["intake_error_counts"].items(), key=lambda x: -x[1]
            )[:5]

        elif agent_key == "document_completeness":
            scores = ag["scores"]
            summary["avg_completeness_score"] = round(sum(scores) / len(scores), 3) if scores else 0
            summary["top_missing_fields"] = sorted(
                ag["missing_field_counts"].items(), key=lambda x: -x[1]
            )[:10]

        elif agent_key == "pii_match":
            total_checked = ag["matched"] + ag["mismatched"] + ag["unverified"]
            summary["matched"] = ag["matched"]
            summary["mismatched"] = ag["mismatched"]
            summary["unverified"] = ag["unverified"]
            summary["not_found"] = ag["not_found"]
            summary["skipped"] = ag["skipped"]
            summary["mismatch_rate"] = round(ag["mismatched"] / total_checked, 3) if total_checked else 0

        elif agent_key == "mvr_request":
            total_mvr = ag["queued"] + ag["skipped"]
            summary["queued"] = ag["queued"]
            summary["skipped"] = ag["skipped"]
            summary["queue_rate"] = round(ag["queued"] / total_mvr, 3) if total_mvr else 0

        elif agent_key == "psp_request":
            total_psp = ag["queued"] + ag["skipped"]
            summary["queued"] = ag["queued"]
            summary["skipped"] = ag["skipped"]
            summary["queue_rate"] = round(ag["queued"] / total_psp, 3) if total_psp else 0

        elif agent_key == "urgency_router":
            days = ag["days_until_court"]
            summary["level_distribution"] = dict(ag["level_counts"])
            summary["no_court_date_count"] = ag["no_court_date"]
            summary["avg_days_until_court"] = round(sum(days) / len(days), 1) if days else None
            summary["critical_count"] = ag["level_counts"].get("CRITICAL", 0)

        results.append(summary)

    # Sort by health score ascending (worst agents first)
    results.sort(key=lambda r: r["health_score"])
    return {"agents": results, "days": days}


# ── Scan feed ────────────────────────────────────────────────────────────────

@router.get("/admin/stats/feed")
def get_scan_feed(limit: int = 100, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _fs()

    docs = list(
        db.collection("scan_queue")
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
        .stream()
    )
    result = []
    for d in docs:
        r = d.to_dict()
        result.append({
            "id": d.id,
            "filename": r.get("filename", ""),
            "pass_status": r.get("pass_status", ""),
            "status": r.get("status", ""),
            "doc_type": r.get("doc_type"),
            "created_at": r.get("created_at", ""),
            "attorney_matched": r.get("attorney_matched", False),
            "attorney_match_type": r.get("attorney_match_type"),
            "has_price_estimate": r.get("has_price_estimate", False),
            "prompt_version": r.get("prompt_version"),
        })
    return {"scans": result, "total": len(result)}


# ── Attorney coverage ────────────────────────────────────────────────────────

@router.get("/admin/stats/attorneys")
def get_attorney_stats(x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    db = _fs()

    docs = list(
        db.collection("scan_queue")
        .order_by("created_at", direction="DESCENDING")
        .limit(500)
        .stream()
    )

    state_stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "matched": 0, "county_match": 0, "no_match": 0, "win_rates": [],
    })
    no_attorney_cases = []

    for d in docs:
        r = d.to_dict()
        doc_type = r.get("doc_type")
        if doc_type and doc_type != "Ticket":
            continue
        pr = r.get("process_response", {})
        result = pr.get("result", {})
        state = (result.get("Ticket_State__c") or {}).get("value", "Unknown")
        county = (result.get("Ticket_County__c") or {}).get("value", "")
        matches = pr.get("attorney_matches", [])
        no_flag = pr.get("no_attorney_flag", False)

        ss = state_stats[state]
        ss["total"] += 1
        if matches:
            ss["matched"] += 1
            if any(m.get("match_type") == "county" for m in matches):
                ss["county_match"] += 1
            for m in matches:
                if m.get("win_rate"):
                    ss["win_rates"].append(m["win_rate"])
        else:
            ss["no_match"] += 1
            if no_flag and len(no_attorney_cases) < 20:
                no_attorney_cases.append({
                    "state": state, "county": county, "filename": pr.get("filename", ""),
                })

    summary = []
    for state, ss in sorted(state_stats.items()):
        total = ss["total"]
        wr = ss["win_rates"]
        summary.append({
            "state": state,
            "total_tickets": total,
            "matched": ss["matched"],
            "no_match": ss["no_match"],
            "match_rate": round(ss["matched"] / total, 3) if total else 0,
            "county_match_rate": round(ss["county_match"] / ss["matched"], 3) if ss["matched"] else 0,
            "avg_win_rate": round(sum(wr) / len(wr), 3) if wr else 0,
        })
    summary.sort(key=lambda s: s["match_rate"])
    return {"by_state": summary, "no_attorney_cases": no_attorney_cases}


# ── Urgency breakdown ────────────────────────────────────────────────────────

@router.get("/admin/stats/urgency")
def get_urgency_stats(x_api_key: Optional[str] = Header(None)):
    """
    Live urgency breakdown of the current AI Review queue in Firestore.

    Returns:
      - count and list of tickets at each urgency level
      - how many have no court date on file
      - CDL mismatch alerts (needs human investigation before attorney sees it)
      - average days until court for tickets in queue
    """
    _check_auth(x_api_key)
    from app.services.firebase_service import _init, _firestore_client
    from datetime import datetime, timezone
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")

    try:
        docs = _firestore_client.collection("tickets") \
            .where("attorney_status", "==", "AI Review").stream()

        level_buckets: dict[str, list] = {
            "CRITICAL": [], "HIGH": [], "STANDARD": [], "LOW": [],
        }
        no_court_date: list[dict] = []
        cdl_mismatches: list[dict] = []
        days_list: list[int] = []
        now = datetime.now(timezone.utc)

        for d in docs:
            data = d.to_dict()
            ticket_id = d.id
            urgency = data.get("urgency_level") or "LOW"
            court_date = data.get("court_date") or ""
            driver_profile = data.get("driver_profile") or {}
            completeness = data.get("completeness_score")
            missing = data.get("missing_fields") or []

            card = {
                "ticket_id": ticket_id,
                "driver_name": data.get("driver_full_name") or data.get("driver_name") or "",
                "violation": data.get("violation_category") or "",
                "ticket_state": data.get("ticket_state") or "",
                "court_date": court_date,
                "urgency_reason": data.get("urgency_reason") or "",
                "completeness_score": completeness,
                "missing_fields": missing,
                "cdl_match": driver_profile.get("cdl_match", "unverified"),
                "created_at": data.get("created_at") or "",
            }

            level_buckets.setdefault(urgency, []).append(card)

            if not court_date:
                no_court_date.append(card)
            else:
                try:
                    from dateutil import parser as du
                    ct = du.parse(court_date, dayfirst=False)
                    if ct.tzinfo is None:
                        ct = ct.replace(tzinfo=timezone.utc)
                    days = (ct - now).days
                    days_list.append(days)
                except Exception:
                    pass

            if driver_profile.get("cdl_match") == "mismatch":
                cdl_mismatches.append({
                    **card,
                    "ticket_cdl": driver_profile.get("ticket_cdl", ""),
                    "profile_cdl": driver_profile.get("profile_cdl", ""),
                })

        total = sum(len(v) for v in level_buckets.values())
        return {
            "total_in_review": total,
            "avg_days_until_court": round(sum(days_list) / len(days_list), 1) if days_list else None,
            "no_court_date_count": len(no_court_date),
            "cdl_mismatch_count": len(cdl_mismatches),
            "cdl_mismatches": cdl_mismatches,
            "by_urgency": {
                level: {
                    "count": len(tickets),
                    "tickets": sorted(tickets, key=lambda t: t.get("court_date") or "9999"),
                }
                for level, tickets in level_buckets.items()
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Training data export ────────────────────────────────────────────────────

@router.get("/admin/training/export")
def export_training(x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    if not TRAINING_FILE.exists():
        raise HTTPException(status_code=404, detail="No training data yet.")
    return FileResponse(
        path=str(TRAINING_FILE),
        filename="approved_tickets.jsonl",
        media_type="application/x-ndjson",
    )


# ── Reviewer: AI Review queue ────────────────────────────────────────────────

_URGENCY_ORDER = {"CRITICAL": 0, "HIGH": 1, "STANDARD": 2, "LOW": 3}


def _review_queue_summary(data: dict) -> dict:
    """Flatten agent outputs into a reviewer-friendly summary dict."""
    sor = data.get("statement_of_record") or {}
    driver_profile = data.get("driver_profile") or {}
    mvr = data.get("mvr_request") or {}
    psp = data.get("psp_request") or {}
    return {
        # Urgency
        "urgency_level":    data.get("urgency_level", "LOW"),
        "urgency_reason":   data.get("urgency_reason", ""),
        # Completeness
        "completeness_score": data.get("completeness_score"),
        "missing_fields":     data.get("missing_fields", []),
        # PII Match
        "cdl_match":          driver_profile.get("cdl_match", "unverified"),
        "profile_cdl":        driver_profile.get("profile_cdl", ""),
        "ticket_cdl":         driver_profile.get("ticket_cdl", ""),
        # Statement of Record
        "conflict_count":     sor.get("conflict_count", 0),
        "evidence_count":     sor.get("evidence_count", 0),
        "conflict_types":     [c.get("conflict_type") for c in (sor.get("conflict_map") or [])],
        # Pending requests
        "mvr_status":         mvr.get("status"),
        "psp_status":         psp.get("status"),
    }


@router.get("/admin/review-queue")
def get_review_queue(x_api_key: Optional[str] = Header(None)):
    """
    Returns all tickets currently in 'AI Review' status, sorted by urgency
    (CRITICAL first) then by court date proximity.

    Each ticket includes a reviewer_summary with completeness score,
    missing fields, CDL match status, conflict map summary, and MVR/PSP
    request status — everything the reviewer needs before approve/reject.
    """
    _check_auth(x_api_key)
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")

    try:
        docs = _firestore_client.collection("tickets") \
            .where("attorney_status", "==", "AI Review").stream()
        tickets = []
        critical_count = 0
        cdl_mismatch_count = 0

        for d in docs:
            data = d.to_dict()
            summary = _review_queue_summary(data)
            if summary["urgency_level"] == "CRITICAL":
                critical_count += 1
            if summary["cdl_match"] == "mismatch":
                cdl_mismatch_count += 1
            tickets.append({
                "ticket_id": d.id,
                **data,
                "reviewer_summary": summary,
            })

        # Sort: urgency level first, then by court date (soonest first)
        tickets.sort(key=lambda t: (
            _URGENCY_ORDER.get(t["reviewer_summary"]["urgency_level"], 3),
            t.get("court_date") or "9999",
        ))

        return {
            "tickets": tickets,
            "total": len(tickets),
            "critical_count": critical_count,
            "cdl_mismatch_count": cdl_mismatch_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _notify_driver_background(driver_id: str, ticket_id: str) -> None:
    """Runs after the HTTP response is sent — keeps approve fast."""
    try:
        from app.services.driver_concierge import notify_driver
        notify_driver(driver_id, ticket_id, "New")
    except Exception as exc:
        logger.warning("[reviewer] driver_concierge failed ticket=%s: %s", ticket_id, exc)


@router.post("/admin/approve-ticket/{ticket_id}")
def approve_ticket(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    reviewer_id: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """
    Reviewer approves AI-extracted data for a manually scanned ticket.
    Moves attorney_status from 'AI Review' → 'New' so attorneys can claim it.
    Returns immediately; driver notification runs in the background.
    """
    _check_auth(x_api_key)
    from app.services.firebase_service import _firestore_client, _init
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")

    try:
        ref = _firestore_client.collection("tickets").document(ticket_id)
        doc = ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")

        data = doc.to_dict()
        if data.get("attorney_status") != "AI Review":
            return {
                "success": False,
                "ticket_id": ticket_id,
                "message": f"Ticket is not in AI Review (current: {data.get('attorney_status')}).",
            }

        ref.update({
            "attorney_status": "New",
            "reviewed_by": reviewer_id,
            "reviewed_at": SERVER_TIMESTAMP,
            "last_modified_date": SERVER_TIMESTAMP,
        })

        # Fire-and-forget: notify the driver after we respond
        driver_id = data.get("driver_id") or ""
        if driver_id:
            background_tasks.add_task(_notify_driver_background, driver_id, ticket_id)

        logger.warning("[reviewer] approved ticket=%s reviewer=%s → New", ticket_id, reviewer_id)
        return {"success": True, "ticket_id": ticket_id, "attorney_status": "New"}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/admin/reject-ticket/{ticket_id}")
def reject_ticket(
    ticket_id: str,
    reason: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """
    Reviewer rejects a manually scanned ticket (e.g. bad image, wrong document).
    Moves attorney_status to 'Rejected' — will not appear in attorney queue.
    """
    _check_auth(x_api_key)
    from app.services.firebase_service import _init, _firestore_client
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")

    try:
        ref = _firestore_client.collection("tickets").document(ticket_id)
        doc = ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")

        ref.update({
            "attorney_status": "Rejected",
            "rejection_reason": reason,
            "last_modified_date": SERVER_TIMESTAMP,
        })

        logger.warning("[reviewer] rejected ticket=%s reason=%r", ticket_id, reason)
        return {"success": True, "ticket_id": ticket_id, "attorney_status": "Rejected"}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
