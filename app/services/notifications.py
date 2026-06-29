"""
Notification service — Twilio SMS + SendGrid email.
All sends are no-op when credentials are absent (dev mode).
"""

import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Twilio SMS
# ---------------------------------------------------------------------------
TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER", "")


def _twilio_client():
    if not (TWILIO_SID and TWILIO_TOKEN):
        return None
    try:
        from twilio.rest import Client
        return Client(TWILIO_SID, TWILIO_TOKEN)
    except ImportError:
        logger.warning("twilio package not installed — SMS disabled")
        return None


def send_sms(to: str, body: str) -> bool:
    """Send an SMS. Returns True on success, False (non-raising) on failure."""
    if not to:
        return False
    client = _twilio_client()
    if client is None:
        logger.info("[SMS-STUB] to=%s | %s", to, body)
        return True  # dev no-op counts as success
    try:
        # Normalise to E.164
        number = to.strip()
        if not number.startswith("+"):
            number = "+1" + number.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        msg = client.messages.create(body=body, from_=TWILIO_FROM, to=number)
        logger.info("[SMS] sent sid=%s to=%s", msg.sid, number)
        return True
    except Exception as exc:
        logger.error("[SMS] failed to=%s: %s", to, exc)
        return False


# ---------------------------------------------------------------------------
# SendGrid email
# ---------------------------------------------------------------------------
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY", "")
EMAIL_FROM    = os.getenv("EMAIL_FROM_ADDRESS", "noreply@rigresolve.com")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Rig Resolve")


def send_email(to: str, subject: str, html_body: str, plain_body: str = "") -> bool:
    """Send a transactional email via SendGrid."""
    if not to:
        return False
    if not SENDGRID_KEY:
        logger.info("[EMAIL-STUB] to=%s subject=%s", to, subject)
        return True
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, From, To, Content

        message = Mail(
            from_email=From(EMAIL_FROM, EMAIL_FROM_NAME),
            to_emails=To(to),
            subject=subject,
            html_content=html_body or plain_body,
        )
        sg = SendGridAPIClient(SENDGRID_KEY)
        resp = sg.send(message)
        logger.info("[EMAIL] sent to=%s status=%s", to, resp.status_code)
        return resp.status_code in (200, 202)
    except ImportError:
        logger.warning("sendgrid package not installed — email disabled")
        return False
    except Exception as exc:
        logger.error("[EMAIL] failed to=%s: %s", to, exc)
        return False


# ---------------------------------------------------------------------------
# Status-change notification helpers
# ---------------------------------------------------------------------------

STATUS_SMS: dict[str, str] = {
    "New": (
        "Rig Resolve: Your ticket has been submitted and is available to attorneys. "
        "Log in to check status: rigresolve.web.app"
    ),
    "Accepted": (
        "Rig Resolve: Great news! An attorney has accepted your case. "
        "Log in to see attorney details: rigresolve.web.app"
    ),
    "Ticket Closed": (
        "Rig Resolve: Your case has been closed. "
        "Log in to view the outcome: rigresolve.web.app"
    ),
    "Rejected": (
        "Rig Resolve: Your ticket was reviewed and could not be processed. "
        "Please contact support: support@rigresolve.com"
    ),
}

STATUS_EMAIL_SUBJECT: dict[str, str] = {
    "New":           "Your ticket is live — attorneys can now view your case",
    "Accepted":      "Attorney accepted your case",
    "Ticket Closed": "Your case has been closed",
    "Rejected":      "Ticket review update",
}

STATUS_EMAIL_HTML: dict[str, str] = {
    "New": """
<p>Hi {name},</p>
<p>Your citation has been submitted to the Rig Resolve attorney network.
Attorneys in your area can now review and accept your case.</p>
<p><a href="https://rigresolve.web.app">View your ticket status →</a></p>
<p>— The Rig Resolve Team</p>
""",
    "Accepted": """
<p>Hi {name},</p>
<p>An attorney has accepted your case. Log in to see their contact information
and next steps.</p>
<p><strong>Attorney:</strong> {attorney_name}</p>
<p><a href="https://rigresolve.web.app">View case details →</a></p>
<p>— The Rig Resolve Team</p>
""",
    "Ticket Closed": """
<p>Hi {name},</p>
<p>Your case has been marked closed. Log in to view the final outcome.</p>
<p><a href="https://rigresolve.web.app">View outcome →</a></p>
<p>— The Rig Resolve Team</p>
""",
    "Rejected": """
<p>Hi {name},</p>
<p>After review, we were unable to process your ticket submission.
Please contact <a href="mailto:support@rigresolve.com">support@rigresolve.com</a>
if you have questions.</p>
<p>— The Rig Resolve Team</p>
""",
}


def notify_status_change(
    new_status: str,
    driver_phone: str = "",
    driver_email: str = "",
    driver_name: str = "Driver",
    attorney_name: str = "",
) -> None:
    """Fire SMS + email notifications for a ticket status transition.

    Called from admin.py (approve/reject) and cases.py (accept/close).
    Both sends are best-effort — failures are logged, never raised.
    """
    sms_template = STATUS_SMS.get(new_status)
    if sms_template and driver_phone:
        send_sms(driver_phone, sms_template)

    email_subject = STATUS_EMAIL_SUBJECT.get(new_status)
    email_html_template = STATUS_EMAIL_HTML.get(new_status)
    if email_subject and email_html_template and driver_email:
        html = email_html_template.format(
            name=driver_name,
            attorney_name=attorney_name or "your assigned attorney",
        )
        send_email(driver_email, email_subject, html)
