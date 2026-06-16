"""
Consensus — merges two Lone Ranger extractions for non-green tickets.

Strategy per field:
  1. Take the value with the higher confidence_score.
  2. If both have equal confidence, prefer pass-1 (deterministic default).
  3. If both scores are >= 0.70 but values disagree → flag the field as a
     "dual_conflict" so Referee knows a human should validate it.
  4. Pass-level metadata is merged into extraction for traceability.
"""
import logging

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "consensus"

_FIELD_KEYS = {
    # Shared / Ticket / Warning
    "Date_of_Ticket__c", "Violation_Description__c", "Violation_Category__c",
    "Court_Date__c", "Accident__c", "Drivers_License_Type__c",
    "Ticket_Court__c", "Court_Phone_Number__c", "Ticket_City__c",
    "Ticket_County__c", "Ticket_State__c", "Insp_Report_Num__c",
    "Citation_Number__c",
    # Inspection Report
    "Inspection_Date__c", "Inspection_Time__c", "Inspection_State__c", "Inspection_County__c",
    "Inspection_City__c", "Inspection_Location__c",
    "DOT_Number__c", "Inspection_Level__c", "VIN__c", "Unit_Make__c",
    "Unit_License_Plate__c", "Driver_OOS__c", "Vehicle_OOS__c", "BASIC_Categories__c",
    # Crash Report
    "Crash_Report_Number__c", "Crash_Date__c", "Crash_State__c", "Crash_County__c",
    "Crash_City__c", "Crash_Location__c", "Federal_Recordable__c", "State_Reportable__c",
    "Number_of_Fatalities__c", "Number_of_Injuries__c", "Towaway__c",
    "Citation_Issued__c", "HM_Involved__c",
    # Civil Penalty
    "Civil_Penalty_Case_Number__c", "Civil_Penalty_Amount__c",
    "Civil_Penalty_Due_Date__c", "BASIC_Category__c",
    # CDL License
    "CDL_License_Number__c", "CDL_State__c", "CDL_Class__c", "CDL_Expiration__c",
    "CDL_Endorsements__c", "CDL_Restrictions__c",
    "Driver_First_Name__c", "Driver_Last_Name__c", "Driver_DOB__c", "Driver_Address__c",
    # MVR
    "MVR_License_Number__c", "MVR_State__c", "MVR_Class__c", "MVR_Generated_Date__c",
    "MVR_Violations_Summary__c", "MVR_Total_Points__c", "MVR_Suspension_Count__c",
}

# Scalar keys that are shared at the top level (not per-field dicts)
_SCALAR_KEYS = {"file_type", "other_document_types", "file_type_analysis", "file_name", "document_text_format"}

CONFLICT_CONFIDENCE_FLOOR = 0.70


def consensus(state: TicketState) -> dict:
    filename = state.get("filename", "unknown")
    ext1: dict = state.get("extraction") or {}
    ext2: dict = state.get("extraction_2") or {}

    if not ext2:
        logger.warning("[consensus] file=%s — no second extraction, skipping merge", filename)
        return {}

    merged: dict = {}
    conflicts: list[str] = []
    improvements: list[str] = []

    # Scalar top-level fields — keep from pass 1 (more conservative)
    for k in _SCALAR_KEYS:
        merged[k] = ext1.get(k, ext2.get(k))

    for field in _FIELD_KEYS:
        f1 = ext1.get(field)
        f2 = ext2.get(field)

        # One pass missing the field entirely — use whichever exists
        if not isinstance(f1, dict):
            merged[field] = f2
            continue
        if not isinstance(f2, dict):
            merged[field] = f1
            continue

        s1 = f1.get("confidence_score", 0.0)
        s2 = f2.get("confidence_score", 0.0)
        v1 = f1.get("value", "")
        v2 = f2.get("value", "")

        values_agree = (v1 == v2) or (not v1 and not v2)

        if s2 > s1:
            merged[field] = f2
            if not values_agree:
                improvements.append(f"{field}({s1:.2f}→{s2:.2f})")
        else:
            merged[field] = f1

        # Flag disagreements where both passes were confident — needs human eye
        if not values_agree and s1 >= CONFLICT_CONFIDENCE_FLOOR and s2 >= CONFLICT_CONFIDENCE_FLOOR:
            merged[field] = {
                **merged[field],
                "dual_conflict": True,
                "conflict_values": [v1, v2],
            }
            conflicts.append(field)

    if improvements:
        logger.warning("[consensus] file=%s — pass-2 improved: %s", filename, ", ".join(improvements))
    if conflicts:
        logger.warning("[consensus] file=%s — dual conflicts (both confident, values differ): %s",
                       filename, ", ".join(conflicts))

    logger.warning("[consensus] file=%s — merge complete improvements=%d conflicts=%d",
                   filename, len(improvements), len(conflicts))

    scan_id = state.get("scan_id", "")
    log_agent_event(scan_id, AGENT_NAME, "merge_complete", {
        "improvements": improvements,
        "dual_conflicts": conflicts,
        "improvements_count": len(improvements),
        "conflicts_count": len(conflicts),
        # Which pass won for each field (for field-level analytics)
        "pass2_wins": [f.split("(")[0] for f in improvements],
    })

    return {"extraction": merged, "dual_conflicts": conflicts, "consensus_extraction": merged}
