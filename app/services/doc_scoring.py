"""
Per-document-type severity scoring for non-ticket documents.
Tickets are scored via cdl_impact.py (CDL point impact).
"""
from __future__ import annotations
from app.models.response import DocumentResult, DocSeverityScore


def score_document(result: DocumentResult) -> DocSeverityScore | None:
    """Return a DocSeverityScore for non-ticket document types, or None for tickets."""
    ft = result.file_type

    if ft == "Inspection Report":
        return _score_inspection(result)
    elif ft == "Crash Report":
        return _score_crash(result)
    elif ft == "Warning":
        return _score_warning(result)
    elif ft == "Civil Penalty":
        return _score_civil_penalty(result)
    elif ft == "MVR":
        return _score_mvr(result)
    elif ft == "CDL":
        return _score_cdl(result)
    return None


def _v(field) -> str:
    if field is None:
        return ""
    return (field.value or "").strip()


# ── Inspection Report ─────────────────────────────────────────────────────────

_BASIC_HIGH_RISK = {"Unsafe Driving", "Controlled Substances/Alcohol", "Driver Fitness", "Fatigued Driving"}

def _score_inspection(r: DocumentResult) -> DocSeverityScore:
    score = 30
    factors = []
    days_to_respond = 60  # DataQ window is 2 years but response typically 60 days

    driver_oos = _v(r.Driver_OOS__c).lower() == "yes"
    vehicle_oos = _v(r.Vehicle_OOS__c).lower() == "yes"
    basics = [b.strip() for b in _v(r.BASIC_Categories__c).split(",") if b.strip()]
    violation_text = _v(r.Violation_Description__c)

    if driver_oos:
        score += 35
        factors.append("Driver placed Out of Service")
    if vehicle_oos:
        score += 20
        factors.append("Vehicle placed Out of Service")
    for b in basics:
        if b in _BASIC_HIGH_RISK:
            score += 15
            factors.append(f"High-risk BASIC category: {b}")
            break
    if len(basics) >= 3:
        score += 10
        factors.append(f"{len(basics)} BASIC categories affected")
    if violation_text:
        vcount = violation_text.count(";") + 1
        if vcount >= 3:
            score += 10
            factors.append(f"{vcount} violations cited")

    score = min(score, 100)
    severity = _band(score)

    if not factors:
        factors.append("Roadside inspection — BASIC score impact pending")

    return DocSeverityScore(
        doc_type="Inspection Report",
        severity=severity,
        severity_score=score,
        key_factors=factors,
        attorney_recommended=score >= 50 or driver_oos or vehicle_oos,
        action_required="File DataQ challenge with FMCSA within 2 years of inspection date",
        days_to_respond=days_to_respond,
    )


# ── Crash Report ─────────────────────────────────────────────────────────────

def _score_crash(r: DocumentResult) -> DocSeverityScore:
    score = 40
    factors = []

    federal = _v(r.Federal_Recordable__c).lower() == "yes"
    state_rep = _v(r.State_Reportable__c).lower() == "yes"
    fatalities = _v(r.Number_of_Fatalities__c)
    injuries = _v(r.Number_of_Injuries__c)
    towaway = _v(r.Towaway__c).lower() == "yes"
    hm = _v(r.HM_Involved__c).lower() == "yes"
    citation = _v(r.Citation_Issued__c).lower() == "yes"

    if federal:
        score += 30
        factors.append("Federal recordable crash — appears on FMCSA record")
    if fatalities and fatalities not in ("0", ""):
        score += 25
        factors.append(f"Fatalities reported: {fatalities}")
    if injuries and injuries not in ("0", ""):
        score += 15
        factors.append(f"Injuries reported: {injuries}")
    if towaway:
        score += 10
        factors.append("Vehicle towed — property damage crash")
    if hm:
        score += 15
        factors.append("Hazmat cargo involved")
    if citation:
        score += 10
        factors.append("Citation issued at scene")
    if state_rep:
        factors.append("State reportable crash")

    score = min(score, 100)

    if not factors:
        factors.append("Crash report on FMCSA record — affects CSA score")

    return DocSeverityScore(
        doc_type="Crash Report",
        severity=_band(score),
        severity_score=score,
        key_factors=factors,
        attorney_recommended=score >= 55 or federal,
        action_required="Review for DataQ challenge if fault determination is incorrect",
        days_to_respond=730,  # 2-year DataQ window
    )


# ── Warning ───────────────────────────────────────────────────────────────────

_SERIOUS_VIOLATION_CATEGORIES = {
    "Alcohol / Drug related violation",
    "Driver license violation",
    "Reckless Driving",
    "Speeding (15+)",
    "Cell Phone",
    "ELD/Logs",
}

def _score_warning(r: DocumentResult) -> DocSeverityScore:
    score = 20
    factors = ["Officer warning — no fine or court date"]
    cat = _v(r.Violation_Category__c)

    if cat in _SERIOUS_VIOLATION_CATEGORIES:
        score += 30
        factors.append(f"Serious violation category: {cat}")
    elif cat:
        score += 10
        factors.append(f"Violation: {cat}")

    return DocSeverityScore(
        doc_type="Warning",
        severity=_band(score),
        severity_score=score,
        key_factors=factors,
        attorney_recommended=score >= 45,
        action_required="No fine due. Retain for records. Consult attorney if serious violation.",
        days_to_respond=None,
    )


# ── Civil Penalty ─────────────────────────────────────────────────────────────

def _score_civil_penalty(r: DocumentResult) -> DocSeverityScore:
    score = 50
    factors = []

    amount_str = _v(r.Civil_Penalty_Amount__c).replace("$", "").replace(",", "").strip()
    due = _v(r.Civil_Penalty_Due_Date__c)
    basic = _v(r.BASIC_Category__c) or _v(r.BASIC_Categories__c)

    try:
        amount = float(amount_str)
        if amount >= 10000:
            score += 35
            factors.append(f"High penalty amount: ${amount:,.0f}")
        elif amount >= 2500:
            score += 20
            factors.append(f"Penalty amount: ${amount:,.0f}")
        elif amount > 0:
            score += 10
            factors.append(f"Penalty amount: ${amount:,.0f}")
    except (ValueError, TypeError):
        factors.append("Civil penalty — amount not extracted")

    if basic:
        factors.append(f"BASIC category: {basic}")

    if due:
        factors.append(f"Payment due: {due}")

    score = min(score, 100)

    return DocSeverityScore(
        doc_type="Civil Penalty",
        severity=_band(score),
        severity_score=score,
        key_factors=factors,
        attorney_recommended=True,
        action_required="Respond to FMCSA within the notice deadline. Attorney review recommended.",
        days_to_respond=30,
    )


# ── MVR ───────────────────────────────────────────────────────────────────────

_HIGH_RISK_MVR_KEYWORDS = ["dui", "dwi", "reckless", "suspended", "revoked", "alcohol", "drug", "felony"]

def _score_mvr(r: DocumentResult) -> DocSeverityScore:
    score = 20
    factors = []

    points_str = _v(r.MVR_Total_Points__c)
    suspensions_str = _v(r.MVR_Suspension_Count__c)
    summary = _v(r.MVR_Violations_Summary__c).lower()

    try:
        points = float(points_str)
        if points >= 10:
            score += 35
            factors.append(f"High point total: {points:.0f} points")
        elif points >= 5:
            score += 20
            factors.append(f"Elevated points: {points:.0f} points")
        elif points > 0:
            score += 10
            factors.append(f"Points on record: {points:.0f}")
    except (ValueError, TypeError):
        pass

    try:
        suspensions = float(suspensions_str)
        if suspensions >= 1:
            score += 25
            factors.append(f"License suspension(s) on record: {suspensions:.0f}")
    except (ValueError, TypeError):
        pass

    for kw in _HIGH_RISK_MVR_KEYWORDS:
        if kw in summary:
            score += 20
            factors.append(f"High-risk violation found: {kw}")
            break

    if not factors:
        factors.append("MVR on file — no high-risk items detected")

    score = min(score, 100)

    return DocSeverityScore(
        doc_type="MVR",
        severity=_band(score),
        severity_score=score,
        key_factors=factors,
        attorney_recommended=score >= 60,
        action_required="Review violations for CDL disqualification risk.",
        days_to_respond=None,
    )


# ── CDL License ───────────────────────────────────────────────────────────────

def _score_cdl(r: DocumentResult) -> DocSeverityScore:
    """CDL is an identity document — no severity scoring, just flag expiration."""
    factors = []
    expiration = _v(r.CDL_Expiration__c)
    cdl_class = _v(r.CDL_Class__c)
    endorsements = _v(r.CDL_Endorsements__c)

    if expiration:
        factors.append(f"License expires: {expiration}")
    if cdl_class:
        factors.append(f"CDL Class {cdl_class}")
    if endorsements:
        factors.append(f"Endorsements: {endorsements}")
    if not factors:
        factors.append("CDL identity document — license data extracted")

    return DocSeverityScore(
        doc_type="CDL",
        severity="LOW",
        severity_score=0,
        key_factors=factors,
        attorney_recommended=False,
        action_required="Verify license is current and class matches vehicle operation.",
        days_to_respond=None,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _band(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    elif score >= 60:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    return "LOW"
