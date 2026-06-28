"""
Queue store — Firestore-backed.

Previously used SQLite + a local JSONL file, both of which are ephemeral on
Cloud Run (lost on container restart). All data now lives in Firestore so it
survives restarts and scales horizontally.

Collections:
  scan_queue/{scan_id}                    — scan results pending/approved/rejected
  scan_queue/{scan_id}/agent_events/      — per-scan agent performance log
  scan_queue/{scan_id}/field_audit/       — reviewer edits per field
  training_records/{scan_id}              — approved scan data (was approved_tickets.jsonl)
  document_cache/{content_hash}           — dedup cache (hash → scan_id)
  attorneys/{attorney_id}                 — managed via the Firestore attorneys/ collection

Images are stored in Firebase Storage (GCS) at:
  scan_images/{scan_id}/page_{n}.jpg
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Kept for import compatibility — both are now None (not file-backed)
DB_PATH = None
TRAINING_FILE = None

EXTRACTED_FIELDS = [
    "Date_of_Ticket__c", "Violation_Description__c", "Violation_Category__c",
    "Court_Date__c", "Accident__c", "Drivers_License_Type__c", "Ticket_Court__c",
    "Court_Phone_Number__c", "Ticket_City__c", "Ticket_County__c", "Ticket_State__c",
    "Insp_Report_Num__c", "Citation_Number__c",
    "Inspection_Date__c", "Inspection_Time__c", "Inspection_State__c",
    "Inspection_County__c", "Inspection_City__c", "Inspection_Location__c",
    "DOT_Number__c", "Inspection_Level__c", "Driver_OOS__c", "Vehicle_OOS__c",
    "BASIC_Categories__c", "Crash_Report_Number__c", "Crash_Date__c",
    "Crash_State__c", "Crash_County__c", "Crash_City__c", "Crash_Location__c",
    "Federal_Recordable__c", "State_Reportable__c", "Number_of_Fatalities__c",
    "Number_of_Injuries__c", "Towaway__c", "Citation_Issued__c", "HM_Involved__c",
    "Civil_Penalty_Case_Number__c", "Civil_Penalty_Amount__c", "Civil_Penalty_Due_Date__c",
    "BASIC_Category__c", "CDL_License_Number__c", "CDL_State__c", "CDL_Class__c",
    "CDL_Expiration__c", "CDL_Endorsements__c", "CDL_Restrictions__c",
    "Driver_First_Name__c", "Driver_Last_Name__c", "Driver_DOB__c", "Driver_Address__c",
    "MVR_License_Number__c", "MVR_State__c", "MVR_Class__c", "MVR_Generated_Date__c",
    "MVR_Violations_Summary__c", "MVR_Total_Points__c", "MVR_Suspension_Count__c",
]

_SEED_ATTORNEYS = [
    # Florida
    ("mock-fl-001", "James R. Holloway",      "jholloway@hollowaytransportlaw.com", "(850) 555-0142", "Florida",     "", 4.8, 0.74, 312),
    ("mock-fl-002", "Sandra M. Vega",         "svega@vegacdldefense.com",           "(407) 555-0219", "Florida",     "", 4.6, 0.68, 187),
    ("mock-fl-003", "Derek W. Fontaine",      "dfontaine@fontainelegal.com",        "(305) 555-0387", "Florida",     "", 4.5, 0.61,  98),
    # Maryland
    ("mock-md-001", "Patricia L. Nguyen",     "pnguyen@nguyen-trucklaw.com",        "(410) 555-0174", "Maryland",    "", 4.9, 0.81, 445),
    ("mock-md-002", "Thomas A. Griggs",       "tgriggs@griggslawmd.com",            "(301) 555-0263", "Maryland",    "", 4.7, 0.72, 229),
    ("mock-md-003", "Carol B. Simmons",       "csimmons@simmonstraffic.com",        "(443) 555-0318", "Maryland",    "", 4.4, 0.65, 153),
    # Washington
    ("mock-wa-001", "Marcus J. Breckenridge", "mbreckenridge@breckenridgecdl.com",  "(206) 555-0492", "Washington",  "", 4.7, 0.77, 381),
    ("mock-wa-002", "Yuki T. Yamamoto",       "yyamamoto@yamamotolegal.com",        "(253) 555-0135", "Washington",  "", 4.6, 0.71, 204),
    ("mock-wa-003", "Brenda K. Okafor",       "bokafor@okafortrucklaw.com",         "(360) 555-0277", "Washington",  "", 4.3, 0.58, 117),
    ("mock-wa-004", "Kevin L. Sorensen",      "ksorensen@sorensentraffic.com",      "(509) 555-0348", "Washington",  "", 4.5, 0.69, 278),
    ("mock-wa-005", "Alicia R. Montoya",      "amontoya@montoyacdllaw.com",         "(425) 555-0461", "Washington",  "", 4.8, 0.83, 512),
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fs():
    """Return the Firestore client. Raises RuntimeError if not configured."""
    from app.services.firebase_service import _firestore_client, _init
    _init()
    if _firestore_client is None:
        raise RuntimeError("Firestore not configured — set FIREBASE_PROJECT_ID in environment.")
    return _firestore_client


def _bucket():
    """Return the Firebase Storage bucket. Returns None if not configured."""
    try:
        from firebase_admin import storage
        return storage.bucket()
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(doc) -> dict:
    data = doc.to_dict() if hasattr(doc, "to_dict") else dict(doc)
    data["id"] = doc.id if hasattr(doc, "id") else data.get("id", "")
    if "process_response" not in data:
        data["process_response"] = {}
    return data


# ── Startup ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Called at app startup. Seeds the Firestore attorneys collection if empty."""
    try:
        db = _fs()
        col = db.collection("attorneys")
        if not list(col.limit(1).stream()):
            ts = _now()
            for a in _SEED_ATTORNEYS:
                col.document(a[0]).set({
                    "attorney_id": a[0],
                    "full_name": a[1],
                    "email": a[2],
                    "phone": a[3],
                    "states_licensed": [a[4]],
                    "counties_covered": [a[5]] if a[5] else [],
                    "rating": a[6],
                    "win_rate": a[7],
                    "total_tickets": a[8],
                    "status": "active",
                    "cases_active": 0,
                    "max_active_cases": 999,
                    "preferred_contact_method": "phone",
                    "created_at": ts,
                    "updated_at": ts,
                })
            logger.warning("[queue_store] Seeded %d attorneys into Firestore", len(_SEED_ATTORNEYS))
    except Exception as exc:
        logger.warning("[queue_store] Attorney seed skipped: %s", exc)


# ── Document cache (deduplication) ───────────────────────────────────────────

def cache_get(content_hash: str) -> Optional[str]:
    """Return scan_id for a previously processed document, or None."""
    try:
        doc = _fs().collection("document_cache").document(content_hash).get()
        return doc.to_dict().get("scan_id") if doc.exists else None
    except Exception:
        return None


def cache_set(content_hash: str, scan_id: str) -> None:
    try:
        _fs().collection("document_cache").document(content_hash).set({
            "scan_id": scan_id,
            "created_at": _now(),
        })
    except Exception:
        pass


# ── Agent event logging ───────────────────────────────────────────────────────

def log_agent_event(scan_id: str, agent: str, event: str, detail: Optional[dict] = None) -> None:
    """Append a structured agent event. Safe to call even if scan not yet written."""
    try:
        _fs().collection("scan_queue").document(scan_id).collection("agent_events").add({
            "scan_id": scan_id,
            "agent": agent,
            "event": event,
            "detail": detail or {},
            "created_at": _now(),
        })
    except Exception:
        pass  # Never crash the pipeline over a logging call


# ── Scan persistence ──────────────────────────────────────────────────────────

def save_scan(
    id: str,
    filename: str,
    pass_status: str,
    process_response_json: str,
    images_b64: Optional[list[str]] = None,
    image_b64: str = "",
    pass1_extraction: Optional[dict] = None,
    pass2_extraction: Optional[dict] = None,
    consensus_extraction: Optional[dict] = None,
    doc_type: Optional[str] = None,
    prompt_version: Optional[str] = None,
    attorney_matched: bool = False,
    attorney_match_type: Optional[str] = None,
    has_price_estimate: bool = False,
    price_estimate: Optional[dict] = None,
) -> None:
    ts = _now()
    page_list = images_b64 if images_b64 else ([image_b64] if image_b64 else [])

    # Upload images to Firebase Storage (GCS) — avoids Firestore 1 MB doc limit
    image_paths: list[str] = []
    bucket = _bucket()
    if bucket and page_list:
        for i, b64_data in enumerate(page_list):
            if not b64_data:
                continue
            try:
                image_bytes = base64.b64decode(b64_data)
                path = f"scan_images/{id}/page_{i}.jpg"
                blob = bucket.blob(path)
                blob.upload_from_string(image_bytes, content_type="image/jpeg")
                image_paths.append(path)
            except Exception as exc:
                logger.warning("[queue_store] Image upload failed scan=%s page=%d: %s", id, i, exc)

    _fs().collection("scan_queue").document(id).set({
        "id": id,
        "filename": filename,
        "pass_status": pass_status,
        "status": "pending",
        "created_at": ts,
        "updated_at": ts,
        "image_paths": image_paths,
        "process_response": json.loads(process_response_json),
        "pass1_extraction": pass1_extraction or {},
        "pass2_extraction": pass2_extraction or {},
        "consensus_extraction": consensus_extraction or {},
        "doc_type": doc_type,
        "prompt_version": prompt_version,
        "attorney_matched": attorney_matched,
        "attorney_match_type": attorney_match_type,
        "has_price_estimate": has_price_estimate,
        "price_estimate": price_estimate or {},
    })


def list_recent(limit: int = 50) -> list[dict]:
    docs = (
        _fs().collection("scan_queue")
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
        .stream()
    )
    return [_serialize(d) for d in docs]


def get_item(id: str) -> Optional[dict]:
    doc = _fs().collection("scan_queue").document(id).get()
    if not doc.exists:
        return None
    return _serialize(doc)


def get_agent_events(scan_id: str) -> list[dict]:
    docs = (
        _fs().collection("scan_queue").document(scan_id)
        .collection("agent_events")
        .order_by("created_at")
        .stream()
    )
    return [d.to_dict() for d in docs]


def approve_item(id: str, edited_fields: dict, reviewer_id: Optional[str] = None) -> None:
    item = get_item(id)
    if item is None:
        raise ValueError(f"Queue item not found: {id}")

    ts = _now()
    db = _fs()
    ref = db.collection("scan_queue").document(id)

    # Strip internal feedback key before storing edited_fields
    field_feedback = edited_fields.pop("__feedback__", {})

    ref.update({
        "status": "approved",
        "updated_at": ts,
        "edited_fields": edited_fields,
        "reviewed_by": reviewer_id,
        "reviewed_at": ts,
    })

    # Per-field audit trail
    original = item.get("process_response", {}).get("result", {})
    for field, new_val in edited_fields.items():
        if field.startswith("__"):
            continue
        orig_field = original.get(field, {})
        old_val = (orig_field.get("value", "") if isinstance(orig_field, dict) else "") or ""
        if old_val != new_val:
            ref.collection("field_audit").add({
                "field_key": field,
                "old_value": old_val,
                "new_value": new_val,
                "reviewer_id": reviewer_id,
                "changed_at": ts,
            })

    # Build final merged values for the training record
    final_values = {}
    for field in EXTRACTED_FIELDS:
        if field in edited_fields:
            final_values[field] = edited_fields[field]
        elif field in original and isinstance(original[field], dict):
            final_values[field] = original[field].get("value", "")
        else:
            final_values[field] = ""

    was_edited = any(
        final_values.get(f) != (original.get(f) or {}).get("value", "")
        for f in EXTRACTED_FIELDS if f in edited_fields
    )

    # Write approved training record to Firestore (replaces approved_tickets.jsonl)
    db.collection("training_records").document(id).set({
        "scan_id": id,
        "filename": item["filename"],
        "approved_at": ts,
        "pass_status": item["pass_status"],
        "doc_type": item.get("doc_type"),
        "prompt_version": item.get("prompt_version"),
        "original_extraction": original,
        "pass1_extraction": item.get("pass1_extraction", {}),
        "pass2_extraction": item.get("pass2_extraction", {}),
        "consensus_extraction": item.get("consensus_extraction", {}),
        "final_values": final_values,
        "was_edited": was_edited,
        "field_feedback": field_feedback,
    })


def get_field_audit(scan_id: str) -> list[dict]:
    docs = (
        _fs().collection("scan_queue").document(scan_id)
        .collection("field_audit")
        .order_by("changed_at")
        .stream()
    )
    return [d.to_dict() for d in docs]


def reject_item(id: str, reason: str) -> None:
    _fs().collection("scan_queue").document(id).update({
        "status": "rejected",
        "updated_at": _now(),
        "reject_reason": reason,
    })


def list_approved() -> list[dict]:
    docs = (
        _fs().collection("scan_queue")
        .where("status", "==", "approved")
        .order_by("updated_at", direction="DESCENDING")
        .stream()
    )
    return [_serialize(d) for d in docs]


def get_image_bytes(scan_id: str, page: int) -> Optional[bytes]:
    """Download a scan image from Firebase Storage. Used by the image proxy endpoint."""
    bucket = _bucket()
    if not bucket:
        return None
    try:
        path = f"scan_images/{scan_id}/page_{page}.jpg"
        blob = bucket.blob(path)
        return blob.download_as_bytes()
    except Exception as exc:
        logger.warning("[queue_store] Image download failed scan=%s page=%d: %s", scan_id, page, exc)
        return None
