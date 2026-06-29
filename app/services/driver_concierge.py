"""
Driver Concierge — proactive driver communication at every case lifecycle stage.

Writes in-app notifications to Firestore at:
  drivers/{driver_id}/notifications/{notif_id}

The driver app listens on this path in real-time (Firestore onSnapshot) and
surfaces the message immediately. The same payload is structured for future
SMS/email integration — add the send calls below each log line.

Status messages per attorney_status transition:
  AI Review     → ticket received, under review
  New           → reviewed and queued for attorney assignment
  Accepted      → attorney assigned, name + phone included
  Ticket Closed → case outcome delivered
  Rejected      → ticket needs more info, team will follow up
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_MESSAGES: dict[str, str] = {
    "AI Review": (
        "We received your ticket and our AI system is reviewing it now. "
        "You'll hear from us as soon as it's ready for an attorney."
    ),
    "New": (
        "Your ticket has been reviewed and is now in our attorney queue. "
        "An attorney will be assigned to your case shortly."
    ),
    "Accepted": (
        "Good news — an attorney has accepted your case. "
        "{attorney_name} will be reaching out to you directly. "
        "You can also contact them at {attorney_phone}."
    ),
    "Ticket Closed": (
        "Your case has been closed. Outcome: {outcome}. "
        "Thank you for being a Rig Resolve member. "
        "Contact us if you have any questions about your case record."
    ),
    "Rejected": (
        "Our team was unable to process your ticket with the information provided. "
        "A case manager will contact you within 1 business day to assist."
    ),
}


def notify_driver(
    driver_id: str,
    ticket_id: str,
    attorney_status: str,
    context: Optional[dict] = None,
) -> bool:
    """
    Write a notification to Firestore and log the message for SMS/email integration.

    context keys:
      attorney_name   (for Accepted status)
      attorney_phone  (for Accepted status)
      outcome         (for Ticket Closed status)

    Returns True if notification was written, False if skipped/failed.
    """
    if not driver_id or not ticket_id:
        logger.warning("[driver_concierge] missing driver_id or ticket_id — skipping")
        return False

    template = _MESSAGES.get(attorney_status)
    if not template:
        logger.warning("[driver_concierge] no message template for status=%r — skipping", attorney_status)
        return False

    ctx = context or {}
    try:
        message = template.format(
            attorney_name=ctx.get("attorney_name", "your assigned attorney"),
            attorney_phone=ctx.get("attorney_phone", "the number provided"),
            outcome=ctx.get("outcome", "see your case record for details"),
        )
    except KeyError:
        message = template

    notif_id = str(uuid.uuid4())
    payload = {
        "notif_id": notif_id,
        "ticket_id": ticket_id,
        "attorney_status": attorney_status,
        "message": message,
        "type": "case_update",
        "read": False,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        import firebase_admin.firestore as fs
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP
        payload["created_at"] = SERVER_TIMESTAMP

        db = fs.client()
        db.collection("drivers").document(driver_id) \
          .collection("notifications").document(notif_id) \
          .set(payload)

        logger.warning(
            "[driver_concierge] SENT driver_id=%s ticket_id=%s status=%r notif_id=%s",
            driver_id, ticket_id, attorney_status, notif_id,
        )

        # Fire SMS + email — best-effort, non-blocking
        try:
            from app.services.notifications import notify_status_change
            driver_doc = db.collection("drivers").document(driver_id).get()
            driver_data = driver_doc.to_dict() if driver_doc.exists else {}
            notify_status_change(
                new_status=attorney_status,
                driver_phone=driver_data.get("phone") or driver_data.get("Phone") or "",
                driver_email=driver_data.get("email") or driver_data.get("Email") or "",
                driver_name=driver_data.get("full_name") or driver_data.get("Name") or "Driver",
                attorney_name=ctx.get("attorney_name", ""),
            )
        except Exception as sms_exc:
            logger.warning("[driver_concierge] notification send failed: %s", sms_exc)

        return True

    except Exception as exc:
        logger.warning(
            "[driver_concierge] Firestore write failed driver_id=%s: %s", driver_id, exc
        )
        return False


def notify_court_reminder(
    driver_id: str,
    ticket_id: str,
    court_date: str,
    days_until: int,
    attorney_name: Optional[str] = None,
) -> bool:
    """Send a court date reminder notification to the driver."""
    if not driver_id or not ticket_id:
        return False

    if days_until < 0:
        msg = f"Your court date of {court_date} has passed. Contact your attorney immediately."
    elif days_until == 0:
        msg = f"Your court date is TODAY ({court_date}). Contact {attorney_name or 'your attorney'} right away."
    else:
        atty = f" Your attorney is {attorney_name}." if attorney_name else ""
        msg = f"Reminder: Your court date is {court_date} — {days_until} day(s) away.{atty}"

    notif_id = str(uuid.uuid4())
    try:
        import firebase_admin.firestore as fs
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP
        db = fs.client()
        db.collection("drivers").document(driver_id) \
          .collection("notifications").document(notif_id) \
          .set({
              "notif_id": notif_id,
              "ticket_id": ticket_id,
              "attorney_status": "court_reminder",
              "message": msg,
              "type": "court_reminder",
              "days_until_court": days_until,
              "court_date": court_date,
              "read": False,
              "created_at": SERVER_TIMESTAMP,
          })
        logger.warning(
            "[driver_concierge] COURT REMINDER driver_id=%s ticket_id=%s days=%d",
            driver_id, ticket_id, days_until,
        )
        return True
    except Exception as exc:
        logger.warning("[driver_concierge] court reminder failed driver_id=%s: %s", driver_id, exc)
        return False
