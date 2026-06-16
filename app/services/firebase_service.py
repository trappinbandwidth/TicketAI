"""
Firebase Admin SDK service.

Writes AI scan results back to Firestore so the driver app
updates in real-time without polling.

Required env vars (set in .env):
  FIREBASE_PROJECT_ID     — your Firebase project ID
  FIREBASE_SERVICE_ACCOUNT_JSON — full service account JSON as a single-line string
                                  OR leave blank to use Application Default Credentials
"""
from __future__ import annotations
import json
import logging
import os

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


def write_scan_result(driver_id: str, ticket_id: str, result: dict) -> bool:
    """
    Update the Firestore ticket document with AI extraction results.
    Called after the AI engine finishes processing.
    Returns True on success, False if Firebase is not configured or write fails.
    """
    _init()
    if _firestore_client is None:
        return False

    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        extraction = result.get("result", {})

        def fv(field: str) -> str | None:
            """Extract the value string from an ExtractedField dict."""
            f = extraction.get(field)
            if isinstance(f, dict):
                return f.get("value") or None
            return None

        # Map AI engine response to Firestore fields
        attorneys = result.get("attorney_matches", [])
        top_atty = attorneys[0] if attorneys else {}

        price = result.get("price_estimate") or {}

        doc_data = {
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
            "date_of_ticket": fv("Date_of_Ticket__c"),
            "citation_number": fv("Citation_Number__c"),
            "drivers_license_type": fv("Drivers_License_Type__c"),
            "driver_first_name": fv("Driver_First_Name__c"),
            "driver_last_name": fv("Driver_Last_Name__c"),
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
            "referee_notes": result.get("referee_notes"),
            "low_confidence_fields": result.get("low_confidence_fields", []),
            "dual_conflicts": result.get("dual_conflicts", []),
            "updated_at": SERVER_TIMESTAMP,
        }

        ref = _firestore_client.collection("drivers").document(driver_id).collection("tickets").document(ticket_id)
        ref.update(doc_data)
        logger.warning("[firebase] Wrote scan result driver=%s ticket=%s status=%s", driver_id, ticket_id, doc_data["status"])
        return True

    except Exception as exc:
        logger.error("[firebase] write_scan_result failed driver=%s ticket=%s: %s", driver_id, ticket_id, exc)
        return False


def _pass_to_status(pass_status: str) -> str:
    """Map AI pass_status to a driver-facing ticket status."""
    if pass_status == "green":
        return "needs_review"   # clean extraction, goes to QA queue
    if pass_status == "yellow":
        return "needs_review"   # some fields need human verification
    return "needs_review"       # red also goes to review, just flagged urgently
