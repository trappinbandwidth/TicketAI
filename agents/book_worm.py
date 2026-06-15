"""
Book Worm — legal logic agent.
Maps the violation category to CDL point impact and severity context.
Runs after Referee on green/yellow passes.
"""
import logging

from app.services.queue_store import log_agent_event
from orchestrator.state import TicketState

AGENT_NAME = "book_worm"

logger = logging.getLogger(__name__)

CDL_POINT_MAP = {
    "Driver license violation":               {"points": 6, "severity": "critical", "csa_category": "Driver Fitness"},
    "Alcohol / Drug related violation":       {"points": 6, "severity": "critical", "csa_category": "Controlled Substances/Alcohol"},
    "Reckless Driving":                       {"points": 5, "severity": "serious",  "csa_category": "Unsafe Driving"},
    "Speeding (15+)":                         {"points": 4, "severity": "serious",  "csa_category": "Unsafe Driving"},
    "Cell Phone":                             {"points": 4, "severity": "serious",  "csa_category": "Unsafe Driving"},
    "Failure to yield to emergency vehicle":  {"points": 4, "severity": "serious",  "csa_category": "Unsafe Driving"},
    "Following too close":                    {"points": 3, "severity": "serious",  "csa_category": "Unsafe Driving"},
    "Careless Driving":                       {"points": 3, "severity": "standard", "csa_category": "Unsafe Driving"},
    "Lane Violation":                         {"points": 2, "severity": "standard", "csa_category": "Unsafe Driving"},
    "Failure to Obey Traffic Control Device": {"points": 2, "severity": "standard", "csa_category": "Unsafe Driving"},
    "Too Fast for Conditions":                {"points": 2, "severity": "standard", "csa_category": "Unsafe Driving"},
    "Speeding (1-14)":                        {"points": 2, "severity": "standard", "csa_category": "Unsafe Driving"},
    "Seatbelt":                               {"points": 1, "severity": "standard", "csa_category": "Unsafe Driving"},
    "ELD/Logs":                               {"points": 3, "severity": "standard", "csa_category": "Hours of Service"},
    "Equipment/Maintenance":                  {"points": 2, "severity": "standard", "csa_category": "Vehicle Maintenance"},
    "Registration Violations":                {"points": 1, "severity": "minor",    "csa_category": "Vehicle Maintenance"},
    "Overweight/Overlength":                  {"points": 1, "severity": "minor",    "csa_category": "Vehicle Maintenance"},
    "Parking":                                {"points": 0, "severity": "minor",    "csa_category": "Unsafe Driving"},
}

MUST_APPEAR_CATEGORIES = {
    "Driver license violation",
    "Alcohol / Drug related violation",
    "Reckless Driving",
}


def book_worm(state: TicketState) -> dict:
    filename = state.get("filename", "unknown")
    extraction = state.get("extraction") or {}
    category_field = extraction.get("Violation_Category__c", {})
    category = category_field.get("value", "") if isinstance(category_field, dict) else ""

    if not category:
        logger.warning("[book_worm] file=%s — Violation_Category__c is empty. "
                       "CDL point impact will be unknown. "
                       "If this is a real ticket, check lone_ranger extraction and the "
                       "Violation_Category__c picklist in the prompt.", filename)
    elif category not in CDL_POINT_MAP:
        logger.warning("[book_worm] file=%s — category %r not in CDL_POINT_MAP. "
                       "This means referee let an unrecognised category through, OR "
                       "lone_ranger extracted a value outside the prompt picklist. "
                       "Add %r to both CDL_POINT_MAP and the prompt picklist.", filename, category, category)

    impact = CDL_POINT_MAP.get(category, {
        "points": 0,
        "severity": "unknown",
        "csa_category": "Unknown",
    })

    must_appear = category in MUST_APPEAR_CATEGORIES
    attorney_recommended = impact["points"] >= 3 or must_appear

    logger.warning("[book_worm] OK file=%s category=%r points=%d severity=%s attorney=%s",
                   filename, category, impact["points"], impact["severity"], attorney_recommended)

    unknown_category = bool(category) and category not in CDL_POINT_MAP
    log_agent_event(state.get("scan_id", ""), AGENT_NAME, "scored", {
        "violation_category": category,
        "cdl_points": impact["points"],
        "severity": impact["severity"],
        "attorney_recommended": attorney_recommended,
        "must_appear_in_court": must_appear,
        "unknown_category": unknown_category,
        "zero_points": impact["points"] == 0,
    })

    return {
        "cdl_point_impact": {
            "violation_category": category,
            "cdl_points": impact["points"],
            "severity": impact["severity"],
            "csa_category": impact.get("csa_category", "Unknown"),
            "must_appear_in_court": must_appear,
            "attorney_recommended": attorney_recommended,
        }
    }
