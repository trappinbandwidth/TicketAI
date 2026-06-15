"""
Salesforce integration — creates Ticket__c records from approved QA scans.

Credentials are read from .env:
  SF_USERNAME, SF_PASSWORD, SF_SECURITY_TOKEN, SF_DOMAIN (default: login)

The client is instantiated lazily and cached per-process. If credentials are
missing the module degrades gracefully — callers receive None instead of a
Ticket__c ID and a warning is logged.
"""
import logging
import os
import re
from datetime import datetime
from functools import lru_cache

logger = logging.getLogger(__name__)

_SF_INSTANCE_URL_TMPL = "https://{domain}.salesforce.com"


@lru_cache(maxsize=1)
def _get_client():
    username = os.getenv("SF_USERNAME", "")
    password = os.getenv("SF_PASSWORD", "")
    token    = os.getenv("SF_SECURITY_TOKEN", "")
    domain   = os.getenv("SF_DOMAIN", "login")

    if not (username and password and token):
        logger.warning("[salesforce] credentials not configured — SF integration disabled")
        return None

    try:
        from simple_salesforce import Salesforce
        sf = Salesforce(username=username, password=password,
                        security_token=token, domain=domain)
        logger.warning("[salesforce] connected to %s", sf.base_url)
        return sf
    except Exception as exc:
        logger.error("[salesforce] connection failed: %s", exc)
        return None


def _parse_date(value: str) -> str | None:
    """Convert MM/DD/YYYY → YYYY-MM-DD for SF date fields. Returns None on failure."""
    if not value:
        return None
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", value.strip())
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()):
        return value.strip()
    return None


def _field_val(extracted: dict, key: str) -> str:
    """Safely pull .value from an extracted field dict."""
    return (extracted.get(key) or {}).get("value", "") or ""


def create_ticket(
    extracted_fields: dict,
    cdl_point_impact: dict | None,
    filename: str,
    driver_name: str | None = None,
    insp_report_num: str | None = None,
) -> str | None:
    """
    Create a Ticket__c record in Salesforce from an approved AI extraction.

    Returns the new Ticket__c Id on success, None if SF is not configured or
    the create fails.

    extracted_fields: the TicketResult dict (field → {value, confidence_score, …})
    cdl_point_impact: the CdlPointImpact dict or None
    """
    sf = _get_client()
    if sf is None:
        return None

    # Build field map
    record: dict = {
        "ai_processed__c": True,
        "Document_Text_Format__c": extracted_fields.get("document_text_format", ""),
    }

    # Direct string/text fields
    str_fields = [
        "Violation_Description__c",
        "Ticket_State__c",
        "Ticket_County__c",
        "Ticket_City__c",
        "Ticket_Court__c",
        "Court_Phone_Number__c",
        "Citation_Number__c",
        "Drivers_License_Type__c",
        "Accident__c",
        "Violation_Category__c",
    ]
    for f in str_fields:
        val = _field_val(extracted_fields, f)
        if val:
            record[f] = val

    # Date fields
    for date_field in ("Date_of_Ticket__c", "Court_Date__c"):
        iso = _parse_date(_field_val(extracted_fields, date_field))
        if iso:
            record[date_field] = iso

    # CDL point impact → court appearance flag
    if cdl_point_impact:
        must_appear = cdl_point_impact.get("must_appear_in_court", False)
        record["Driver_to_Appear_in_Court__c"] = must_appear

    # Notes — include filename and inspection report number for traceability
    note_parts = [f"AI scanned from: {filename}"]
    if insp_report_num:
        note_parts.append(f"Insp Report #: {insp_report_num}")
    record["Notes__c"] = "\n".join(note_parts)

    # Try to look up driver by name if provided
    if driver_name:
        try:
            result = sf.query(
                f"SELECT Id FROM Contact WHERE Name = '{driver_name}' "
                f"OR (FirstName = '{driver_name.split()[0]}' "
                f"AND LastName = '{driver_name.split()[-1]}') LIMIT 1"
            )
            if result["totalSize"] > 0:
                record["Driver__c"] = result["records"][0]["Id"]
                logger.warning("[salesforce] matched driver %r → %s", driver_name, record["Driver__c"])
        except Exception as exc:
            logger.warning("[salesforce] driver lookup failed for %r: %s", driver_name, exc)

    try:
        response = sf.Ticket__c.create(record)
        ticket_id = response.get("id")
        logger.warning("[salesforce] Ticket__c created id=%s file=%s", ticket_id, filename)
        return ticket_id
    except Exception as exc:
        logger.error("[salesforce] create failed file=%s error=%s", filename, exc)
        return None


def ticket_url(ticket_id: str) -> str:
    """Return a browser-navigable URL for a Ticket__c record."""
    domain = os.getenv("SF_DOMAIN", "login")
    # Convert login/test domain to the lightning URL pattern
    base = f"https://cdllegal.lightning.force.com" if "login" in domain else f"https://{domain}.lightning.force.com"
    return f"{base}/lightning/r/Ticket__c/{ticket_id}/view"
