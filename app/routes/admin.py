"""
Admin dashboard API routes.
All endpoints require the same API key as the process endpoint.
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from app.services.queue_store import DB_PATH, TRAINING_FILE

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


def _db():
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="No data yet — run a scan first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Overview stats ──────────────────────────────────────────────────────────

@router.get("/admin/stats/overview")
def get_overview(days: int = 30, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    conn = _db()

    rows = conn.execute("""
        SELECT pass_status, status, doc_type, attorney_matched, has_price_estimate,
               created_at, attorney_match_type
        FROM queue
        WHERE created_at >= datetime('now', ? || ' days')
        ORDER BY created_at DESC
    """, (f"-{days}",)).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return {"total": 0, "days": days}

    pass_counts = defaultdict(int)
    doc_type_counts = defaultdict(int)
    daily_counts: dict[str, dict] = defaultdict(lambda: {"green": 0, "yellow": 0, "red": 0, "total": 0})
    attorney_matched = 0
    county_matches = 0
    price_estimated = 0

    for r in rows:
        ps = r["pass_status"] or "unknown"
        pass_counts[ps] += 1
        doc_type_counts[r["doc_type"] or "Unknown"] += 1
        day = (r["created_at"] or "")[:10]
        daily_counts[day]["total"] += 1
        if ps in ("green", "yellow", "red"):
            daily_counts[day][ps] += 1
        if r["attorney_matched"]:
            attorney_matched += 1
            if r["attorney_match_type"] == "county":
                county_matches += 1
        if r["has_price_estimate"]:
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
        "daily_volume": [
            {"date": d, **v} for d, v in sorted(daily_counts.items())
        ],
    }


# ── Field performance ───────────────────────────────────────────────────────

@router.get("/admin/stats/fields")
def get_field_stats(doc_type: Optional[str] = None, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)

    if not TRAINING_FILE.exists():
        return {"fields": [], "sample_size": 0}

    field_data: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0, "empty": 0,
        "edited": 0, "confidence_sum": 0.0, "conf_samples": 0,
        "pass1_filled": 0, "pass2_improved": 0,
    })

    sample_size = 0
    with open(TRAINING_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
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

    if not TRAINING_FILE.exists():
        return {"field": field_key, "cases": []}

    cases = []
    with open(TRAINING_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
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
                "scan_id": rec.get("id"),
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

    # Sort wrong cases first
    cases.sort(key=lambda c: (not c["was_wrong"], c["approved_at"] or ""))
    prompt_info = PROMPT_SECTION_MAP.get(field_key, {"section": "Unknown", "step": 99})
    return {"field": field_key, "prompt_section": prompt_info["section"], "cases": cases}


# ── Agent scorecard ─────────────────────────────────────────────────────────

@router.get("/admin/stats/agents")
def get_agent_stats(days: int = 30, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    conn = _db()

    events = conn.execute("""
        SELECT ae.agent, ae.event, ae.detail_json, ae.created_at, q.pass_status, q.doc_type
        FROM agent_events ae
        JOIN queue q ON q.id = ae.scan_id
        WHERE ae.created_at >= datetime('now', ? || ' days')
    """, (f"-{days}",)).fetchall()
    conn.close()

    agents: dict[str, dict] = {
        "lone_ranger": {
            "name": "🤠 Lone Ranger", "events": 0, "errors": 0,
            "pass1_fills": [], "pass1_empty_fields": defaultdict(int),
            "pass1_low_conf_fields": defaultdict(int),
            "pass2_fills": [], "improvements": [],
        },
        "referee": {
            "name": "⚖️ Referee", "events": 0, "errors": 0,
            "scores": [], "critical_failures": defaultdict(int),
            "low_conf_fields": defaultdict(int),
            "false_escalations": 0,
        },
        "consensus": {
            "name": "🔀 Consensus", "events": 0, "errors": 0,
            "dual_conflicts": defaultdict(int),
            "improvements_per_scan": [],
        },
        "book_worm": {
            "name": "📚 Book Worm", "events": 0, "errors": 0,
            "unknown_categories": [], "zero_point_tickets": 0,
            "attorney_recommended": 0,
        },
    }

    for ev in events:
        agent = ev["agent"]
        event = ev["event"]
        detail = json.loads(ev["detail_json"]) if ev["detail_json"] else {}
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

        results.append(summary)

    # Sort by health score ascending (worst agents first)
    results.sort(key=lambda r: r["health_score"])
    return {"agents": results, "days": days}


# ── Scan feed ────────────────────────────────────────────────────────────────

@router.get("/admin/stats/feed")
def get_scan_feed(limit: int = 100, x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    conn = _db()
    rows = conn.execute("""
        SELECT id, filename, pass_status, status, doc_type, created_at,
               attorney_matched, attorney_match_type, has_price_estimate, prompt_version
        FROM queue ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        # Parse confidence from process_response_json is expensive — skip for feed
        result.append(d)
    return {"scans": result, "total": len(result)}


# ── Attorney coverage ────────────────────────────────────────────────────────

@router.get("/admin/stats/attorneys")
def get_attorney_stats(x_api_key: Optional[str] = Header(None)):
    _check_auth(x_api_key)
    conn = _db()

    rows = conn.execute("""
        SELECT process_response_json, pass_status, doc_type
        FROM queue WHERE doc_type = 'Ticket' OR doc_type IS NULL
        ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    conn.close()

    state_stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "matched": 0, "county_match": 0, "no_match": 0,
        "win_rates": [],
    })

    no_attorney_cases = []

    for row in rows:
        try:
            pr = json.loads(row["process_response_json"])
        except Exception:
            continue
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
                    "state": state, "county": county,
                    "filename": pr.get("filename", ""),
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
