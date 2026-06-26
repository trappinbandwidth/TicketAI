"""
Enrollment Verifier — gate before any case enters the processing pipeline.

Queries the driver's Firestore profile for active subscription status.
If the driver is not an active member, the ticket is blocked before the
Claude OCR call is made — protecting revenue and preventing free work.

Subscription states:
  active    → proceed
  trial     → proceed (grace period)
  lapsed    → block; flag for Sales follow-up
  cancelled → block
  unknown   → let through with a warning flag; admin can reject later
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def verify_enrollment(driver_id: Optional[str]) -> dict:
    """
    Returns:
      {
        enrolled: bool,
        status: "active" | "trial" | "lapsed" | "cancelled" | "unknown" | "no_driver_id",
        driver_name: str,
        plan: str,
        expires_at: str | None,
        message: str,
      }
    """
    if not driver_id:
        # Website form submissions and staff scans arrive without a driver_id.
        # Let them through as "unknown" — the admin review queue is the gate.
        return {
            "enrolled": True,
            "status": "unknown",
            "driver_name": "",
            "plan": "",
            "expires_at": None,
            "message": "No driver_id provided — proceeding as unverified submission for admin review.",
        }

    try:
        from app.services.firebase_service import _init as _firebase_init
        _firebase_init()
        import firebase_admin.firestore as fs
        db = fs.client()
        doc = db.collection("drivers").document(driver_id).get()

        if not doc.exists:
            logger.warning("[enrollment_verifier] driver_id=%s — no Firestore profile", driver_id)
            return {
                "enrolled": False,
                "status": "unknown",
                "driver_name": "",
                "plan": "",
                "expires_at": None,
                "message": f"Driver profile not found for {driver_id}. Manual verification required.",
            }

        profile = doc.to_dict() or {}
        sub_status = (profile.get("subscription_status") or "unknown").lower()
        plan       = profile.get("plan") or profile.get("subscription_plan") or ""
        driver_name = profile.get("full_name") or profile.get("name") or ""
        end_date_raw = profile.get("subscription_end_date")

        # Parse expiry
        expires_at: Optional[str] = None
        is_expired = False
        if end_date_raw:
            try:
                if hasattr(end_date_raw, "isoformat"):
                    end_dt = end_date_raw
                    if hasattr(end_dt, "tzinfo") and end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    expires_at = end_dt.isoformat()
                    is_expired = end_dt < datetime.now(timezone.utc)
                else:
                    expires_at = str(end_date_raw)
            except Exception:
                pass

        # Override status if subscription has expired
        if is_expired and sub_status in ("active", "trial"):
            sub_status = "lapsed"

        enrolled = sub_status in ("active", "trial")

        if enrolled:
            message = f"Driver {driver_name} is enrolled ({sub_status}, {plan})."
        elif sub_status == "lapsed":
            message = f"Driver {driver_name} subscription has lapsed. Flag for Sales."
        elif sub_status == "cancelled":
            message = f"Driver {driver_name} has cancelled their subscription."
        else:
            message = f"Driver {driver_name} subscription status unknown — proceeding with admin flag."
            enrolled = True  # Let through; reviewer can reject

        logger.warning(
            "[enrollment_verifier] driver_id=%s name=%r status=%s enrolled=%s",
            driver_id, driver_name, sub_status, enrolled,
        )
        return {
            "enrolled": enrolled,
            "status": sub_status,
            "driver_name": driver_name,
            "plan": plan,
            "expires_at": expires_at,
            "message": message,
        }

    except Exception as exc:
        logger.warning("[enrollment_verifier] Firestore error driver_id=%s: %s", driver_id, exc)
        # Fail open with a warning — don't block scans due to Firestore outage
        return {
            "enrolled": True,
            "status": "unknown",
            "driver_name": "",
            "plan": "",
            "expires_at": None,
            "message": f"Enrollment check failed (Firestore error) — proceeding. Error: {exc}",
        }
