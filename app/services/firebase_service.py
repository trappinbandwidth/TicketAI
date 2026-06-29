"""
Firebase Admin SDK service.

Writes AI scan results to two Firestore paths:
  1. drivers/{driver_id}/tickets/{ticket_id}  — driver app real-time updates
  2. tickets/{ticket_id}                       — attorney portal queue

Required env vars:
  FIREBASE_PROJECT_ID     — your Firebase project ID
  FIREBASE_SERVICE_ACCOUNT_JSON — full service account JSON as a single-line string
                                  OR leave blank to use Application Default Credentials
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_initialized = False
_firestore_client = None


def _init():
    global _initialized, _firestore_client
    if _initialized:
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as admin_firestore

        if not firebase_admin._apps:
            sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
            project_id = os.getenv("FIREBASE_PROJECT_ID", "")

            if sa_json:
                sa_dict = json.loads(sa_json)
                cred = credentials.Certificate(sa_dict)
            elif project_id:
                # Use Application Default Credentials (e.g. on Cloud Run / GCE)
                cred = credentials.ApplicationDefault()
            else:
                logger.warning("[firebase] No credentials configured — Firestore writes disabled")
                _initialized = True
                return

            firebase_admin.initialize_app(cred, {"projectId": project_id or sa_dict.get("project_id")})

        _firestore_client = admin_firestore.client()
        _initialized = True
        logger.warning("[firebase] Admin SDK initialized")

    except ImportError:
        logger.warning("[firebase] firebase-admin not installed — Firestore writes disabled")
        _initialized = True
    except Exception as exc:
        logger.error("[firebase] Initialization failed: %s", exc)
        _initialized = True


def write_scan_result(
    driver_id: Optional[str],
    ticket_id: str,
    result: dict,
    source: str = "driver_upload",
    carrier_id: Optional[str] = None,
) -> bool:
    """
    Write AI scan results to Firestore after processing.

    Two writes every time:
      1. drivers/{driver_id}/tickets/{ticket_id} — driver app (only when driver_id known)
      2. tickets/{ticket_id}                      — attorney portal available-cases queue

    source: "driver_upload"   (driver submitted via app/form)
            "manual"          (Rig Resolve staff scanned on behalf of driver)
            "carrier_upload"  (carrier submitted on behalf of a driver)
    carrier_id: UID of the carrier who submitted (stored on ticket for carrier filtering)
    """
    _init()
    if _firestore_client is None:
        return False

    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        extraction = result.get("result", {})

        def fv(field: str) -> Optional[str]:
            f = extraction.get(field)
            if isinstance(f, dict):
                return f.get("value") or None
            return None

        attorneys = result.get("attorney_matches", [])
        top_atty = attorneys[0] if attorneys else {}
        price = result.get("price_estimate") or {}

        first = fv("Driver_First_Name__c")
        last  = fv("Driver_Last_Name__c")
        full_name = " ".join(filter(None, [first, last])) or None

        # ── Write 1: driver subcollection (driver app real-time) ──────────────
        if driver_id:
            driver_doc = {
                "status": _pass_to_status(result.get("pass_status", "red")),
                "pass_status": result.get("pass_status"),
                "ai_scan_id": result.get("queue_id"),
                "cached": result.get("cached", False),
                "violation_category": fv("Violation_Category__c"),
                "violation_description": fv("Violation_Description__c"),
                "ticket_state": fv("Ticket_State__c"),
                "ticket_county": fv("Ticket_County__c"),
                "ticket_city": fv("Ticket_City__c"),
                "court_date": fv("Court_Date__c"),
                "court_time": fv("Court_Time__c"),
                "date_of_ticket": fv("Date_of_Ticket__c"),
                "citation_number": fv("Citation_Number__c"),
                "insp_report_num": fv("Insp_Report_Num__c"),
                "drivers_license_type": fv("Drivers_License_Type__c"),
                "driver_first_name": first,
                "driver_last_name": last,
                "driver_dob": fv("Driver_DOB__c"),
                "driver_address": fv("Driver_Address__c"),
                "cdl_license_number": fv("CDL_License_Number__c"),
                "cdl_class": fv("CDL_Class__c"),
                "attorney_name": top_atty.get("name"),
                "attorney_phone": top_atty.get("phone"),
                "attorney_email": top_atty.get("email"),
                "attorney_match_type": top_atty.get("match_type"),
                "price_display": price.get("display"),
                "price_low": price.get("driver_price_low"),
                "price_high": price.get("driver_price_high"),
                "fine_amount": fv("Fine_Amount__c"),
                "penalty_amount": fv("Penalty_Amount__c"),
                "fine_printed_on_ticket": fv("Fine_Printed_On_Ticket__c"),
                "referee_notes": result.get("referee_notes"),
                "low_confidence_fields": result.get("low_confidence_fields", []),
                "dual_conflicts": result.get("dual_conflicts", []),
                "updated_at": SERVER_TIMESTAMP,
            }
            driver_ref = (
                _firestore_client
                .collection("drivers").document(driver_id)
                .collection("tickets").document(ticket_id)
            )
            driver_ref.set(driver_doc, merge=True)
            logger.warning("[firebase] driver write driver=%s ticket=%s status=%s",
                           driver_id, ticket_id, driver_doc["status"])

        # ── Write 2: top-level tickets collection (attorney portal queue) ─────
        # Manual scans land in "AI Review" — hidden from attorneys until reviewer approves.
        # Driver uploads go straight to "New" — no review step required.
        citation = fv("Citation_Number__c")
        atty_doc = {
            "attorney_status": "AI Review" if source == "manual" else "New",
            "driver_id": driver_id,
            "driver_full_name": full_name,
            "driver_cdl": fv("CDL_License_Number__c"),
            "driver_dob": fv("Driver_DOB__c"),
            "driver_address": fv("Driver_Address__c"),
            "violation_category": fv("Violation_Category__c"),
            "violation_description": fv("Violation_Description__c"),
            "ticket_state": fv("Ticket_State__c"),
            "ticket_county": fv("Ticket_County__c"),
            "ticket_city": fv("Ticket_City__c"),
            "ticket_city_state": (
                ", ".join(filter(None, [fv("Ticket_City__c"), fv("Ticket_State__c")])) or None
            ),
            "court_date": fv("Court_Date__c"),
            "court_time": fv("Court_Time__c"),
            "date_of_ticket": fv("Date_of_Ticket__c"),
            "citation_number": citation,
            "insp_report_num": fv("Insp_Report_Num__c"),
            "name": citation or ticket_id,
            "region": fv("Ticket_State__c"),
            "source": source,
            "carrier_id": carrier_id,
            "ai_scan_id": result.get("queue_id"),
            "pass_status": result.get("pass_status"),
            "price_display": price.get("display"),
            "price_low": price.get("driver_price_low"),
            "price_high": price.get("driver_price_high"),
            "fine_amount": fv("Fine_Amount__c"),
            "penalty_amount": fv("Penalty_Amount__c"),
            "fine_printed_on_ticket": fv("Fine_Printed_On_Ticket__c"),
            "statute_code": fv("Statute_Code__c"),
            "created_at": SERVER_TIMESTAMP,
            "last_modified_date": SERVER_TIMESTAMP,
        }
        tickets_ref = _firestore_client.collection("tickets").document(ticket_id)
        tickets_ref.set(atty_doc, merge=True)
        logger.warning("[firebase] attorney queue write ticket=%s source=%s pass=%s",
                       ticket_id, source, result.get("pass_status"))

        # Driver Concierge — notify driver of initial status
        if driver_id:
            try:
                from app.services.driver_concierge import notify_driver
                initial_status = atty_doc["attorney_status"]
                notify_driver(driver_id, ticket_id, initial_status)
            except Exception as exc:
                logger.warning("[firebase] driver_concierge notify failed ticket=%s: %s", ticket_id, exc)

        return True

    except Exception as exc:
        logger.error("[firebase] write_scan_result failed driver=%s ticket=%s: %s",
                     driver_id, ticket_id, exc)
        return False


def _pass_to_status(pass_status: str) -> str:
    """Map AI pass_status to a driver-facing ticket status."""
    if pass_status == "green":
        return "needs_review"
    if pass_status == "yellow":
        return "needs_review"
    return "needs_review"


def upload_photo_to_storage(
    raw_bytes: bytes,
    photo_id: str,
    filename: str,
    content_type: str = "image/jpeg",
) -> Optional[str]:
    """
    Upload a photo to Firebase Storage and return its public download URL.
    Path: photos/{photo_id}/{filename}
    Returns None if Storage is not configured or upload fails.
    """
    _init()
    project_id = os.getenv("FIREBASE_PROJECT_ID", "")
    if not project_id:
        return None

    try:
        from firebase_admin import storage as admin_storage
        bucket_name = f"{project_id}.appspot.com"
        bucket = admin_storage.bucket(bucket_name)
        blob_path = f"photos/{photo_id}/{filename}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(raw_bytes, content_type=content_type)
        # Generate a signed-ish URL valid for 7 days; fall back to gs:// on failure
        try:
            download_url = blob.generate_signed_url(expiration=604800, method="GET", version="v4")
        except Exception:
            download_url = f"gs://{bucket_name}/{blob_path}"
        logger.warning("[firebase] storage upload photo=%s url=%s", photo_id, download_url[:60])
        return download_url
    except Exception as exc:
        logger.warning("[firebase] storage upload FAILED photo=%s: %s", photo_id, exc)
        return None


def write_photo_result(
    photo_id: str,
    driver_id: Optional[str],
    analysis: dict,
    source: str = "driver_upload",
    storage_url: Optional[str] = None,
) -> bool:
    """
    Write photo AI analysis to Firestore.

    Two paths:
      1. photos/{photo_id}                          — attorney portal access
      2. drivers/{driver_id}/photos/{photo_id}      — driver app (when driver_id known)

    analysis: the dict returned by agents.photo_analyst.analyze_photo()
    storage_url: Firebase Storage download URL for the original image (optional)
    """
    _init()
    if _firestore_client is None:
        return False

    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        def fv(field: str) -> Optional[str]:
            f = analysis.get(field)
            if isinstance(f, dict):
                return f.get("value") or None
            return None

        photo_doc = {
            "photo_id": photo_id,
            "driver_id": driver_id,
            "file_name": analysis.get("file_name", ""),
            "photo_type": analysis.get("photo_type", "Other"),
            "photo_summary": fv("Photo_Summary__c"),
            "damage_assessment": fv("Damage_Assessment__c"),
            "attorney_notes": fv("Attorney_Notes__c"),
            "storage_url": storage_url,
            "source": source,
            "pass_status": "green",
            "full_analysis": analysis,
            "created_at": SERVER_TIMESTAMP,
        }

        # Write 1: top-level photos collection (attorney portal queue)
        _firestore_client.collection("photos").document(photo_id).set(photo_doc, merge=True)
        logger.warning("[firebase] photo write photo=%s type=%s", photo_id, photo_doc["photo_type"])

        # Write 2: driver subcollection (driver app real-time)
        if driver_id:
            _firestore_client \
                .collection("drivers").document(driver_id) \
                .collection("photos").document(photo_id) \
                .set(photo_doc, merge=True)
            logger.warning("[firebase] driver photo write driver=%s photo=%s", driver_id, photo_id)

        return True

    except Exception as exc:
        logger.error("[firebase] write_photo_result FAILED photo=%s: %s", photo_id, exc)
        return False
