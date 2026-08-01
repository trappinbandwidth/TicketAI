#!/usr/bin/env python3
"""
Seed the local Firebase emulator with synthetic data (spec doc 11 §3).

Replaces the cloud staging project: gives every portal something real to
render while we build locally. Idempotent — safe to re-run.

    firebase emulators:start          # in one terminal
    python scripts/seed_local.py      # in another

Never point this at a real project: it refuses to run without
FIRESTORE_EMULATOR_HOST set.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

if not os.getenv("FIRESTORE_EMULATOR_HOST"):
    sys.exit("Refusing to seed: FIRESTORE_EMULATOR_HOST is not set (emulator only).")

# Run from anywhere: put the repo root on the path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FIREBASE_PROJECT_ID", "rigresolve-local")

import firebase_admin  # noqa: E402
from firebase_admin import auth as fb_auth, firestore  # noqa: E402

from app.services.firebase_service import _emulator_credential  # noqa: E402
from app.services.driver_profile import PiiCipher  # noqa: E402
from app.platform.service import principal_id_for_uid  # noqa: E402

PROJECT = os.environ["FIREBASE_PROJECT_ID"]
if not firebase_admin._apps:
    firebase_admin.initialize_app(_emulator_credential(), {"projectId": PROJECT})
db = firestore.client()

NOW = datetime.now(timezone.utc)


def days(n: int) -> datetime:
    return NOW + timedelta(days=n)


def upsert_user(uid: str, email: str, claims: dict, password: str = "tipos-local",
                phone_number: str | None = None) -> str:
    """Create (or refresh) an emulator auth user with role claims.

    Drivers get a phone_number so phone-OTP sign-in resolves to this same uid —
    otherwise the driver app would mint a brand-new user and see none of the
    seeded tickets or risk profile.
    """
    kwargs: dict = {"email": email, "password": password}
    if phone_number:
        kwargs["phone_number"] = phone_number
    try:
        fb_auth.get_user(uid)
        fb_auth.update_user(uid, **kwargs)
    except fb_auth.UserNotFoundError:
        fb_auth.create_user(uid=uid, **kwargs)
    fb_auth.set_custom_user_claims(uid, claims)
    return uid


# ── Staff (the three real accounts + role coverage) ──────────────────────────
STAFF = [
    ("staff_quest", "quest@puklabs.com", {"role": "staff", "staff_role": "admin", "mfa_verified": True}),
    ("staff_eniola", "eniola@rigresolve.com", {"role": "staff", "staff_role": "admin", "mfa_verified": True}),
    ("staff_justin", "justin@rigresolve.com", {"role": "staff", "staff_role": "network_lead"}),
    ("staff_reviewer", "reviewer@rigresolve.local", {"role": "staff", "staff_role": "reviewer"}),
    ("staff_aam", "aam@rigresolve.local", {"role": "staff", "staff_role": "attorney_account_manager"}),
]

# ── Drivers ─────────────────────────────────────────────────────────────────
DRIVERS = [
    {
        "uid": "drv_lovelace", "email": "ada@driver.local", "first_name": "Ada", "last_name": "Lovelace",
        "cdl_number": "TX8841203", "cdl_state": "TX", "phone": "+15125550101",
        "plan": "pro", "billing_cycle": "annual", "safe_driver": True, "carrier_id": "car_bigrig",
    },
    {
        "uid": "drv_johnson", "email": "marcus@driver.local", "first_name": "Marcus", "last_name": "Johnson",
        "cdl_number": "OK5520117", "cdl_state": "OK", "phone": "+14055550102",
        "plan": "core", "billing_cycle": "monthly", "safe_driver": False, "carrier_id": "car_bigrig",
    },
    {
        "uid": "drv_delgado", "email": "rosa@driver.local", "first_name": "Rosa", "last_name": "Delgado",
        "cdl_number": "KS3391884", "cdl_state": "KS", "phone": "+13165550103",
        "plan": None, "billing_cycle": None, "safe_driver": False, "carrier_id": None,  # free tier
    },
]

CONNECTED_DRIVER_NAMES = {
    "seed_driver_alicia": ("Alicia", "Brooks"),
    "seed_driver_tom": ("Tom", "Nguyen"),
    "seed_driver_wade": ("Wade", "Carter"),
}

# The rest of a complete driver profile (the onboarding gate collects these).
# ssn_last4 is here only so the seeded, already-onboarded drivers look complete;
# it is sensitive PII and in production must be encrypted at rest / access-gated.
PROFILE_EXTRA = {
    "drv_lovelace": {
        "middle_initial": "M", "dob": "1988-04-12", "cdl_expiration": "2027-09-30",
        "address": {"street": "1420 Rig Way", "city": "San Antonio", "state": "TX", "zip": "78201"},
        "ssn_last4": "4412", "driver_role": "company_driver", "carrier_name": "Big Rig Freight Co",
    },
    "drv_johnson": {
        "middle_initial": "T", "dob": "1979-11-02", "cdl_expiration": "2026-12-15",
        "address": {"street": "88 Prairie Rd", "city": "Oklahoma City", "state": "OK", "zip": "73102"},
        "ssn_last4": "5520", "driver_role": "company_driver", "carrier_name": "Big Rig Freight Co",
    },
    "drv_delgado": {
        "middle_initial": "", "dob": "1990-06-21", "cdl_expiration": "2028-03-31",
        "address": {"street": "312 Sedgwick Ln", "city": "Wichita", "state": "KS", "zip": "67202"},
        "ssn_last4": "3391", "driver_role": "owner_operator", "business_name": "Delgado Hauling LLC",
    },
}

# ── Carriers ────────────────────────────────────────────────────────────────
CARRIERS = [
    {
        "uid": "car_bigrig", "email": "safety@bigrig.local", "company_name": "Big Rig Freight Co",
        # dot_number gets overwritten with the doc id by the CRM endpoints, so the
        # real USDOT is kept in its own field for display.
        "dot_number": "1234567", "usdot": "1234567", "mc_number": "MC-889120", "per_driver_rate_cents": 900,
        "subscription_status": "active", "driver_count": 62,
        "insurance_company": "Great West Casualty", "insurance_type": "primary_liability",
        "insurance_policy_number": "GW-4491203", "insurance_annual_cost_cents": 18400000,
    },
]

# Deterministic public records from the bundled FMCSA motor-carrier authority
# index. These are CRM prospects, not registered users, and never receive
# synthetic CSA BASICs or individual Driver risk data.
FMCSA_SAMPLE_DOTS = [
    "100002", "100011", "1000728", "1001080",
    "1001199", "1001271", "100139", "1001468",
]

# ── Risk / underwriting profiles ────────────────────────────────────────────
# The insurance-adjacent signal the CRM profile drill-down surfaces. In
# production this is populated by the FMCSA/CSA sync + the pipeline; seeded
# here so the "at a glance" underwriting module renders locally. CSA BASICs are
# a direct insurance-risk input; DataQ removals reduce loss-relevant data.
def _basic(code, name, pct, threshold, measure):
    return {"code": code, "name": name, "percentile": pct, "threshold": threshold,
            "alert": pct is not None and pct >= threshold, "measure": measure}

RISK_CARRIER = {
    "car_bigrig": {
        "risk_tier": "Elevated",
        "basics": [
            _basic("unsafe_driving", "Unsafe Driving", 78, 65, 2.41),
            _basic("hos", "Hours-of-Service", 61, 65, 1.88),
            _basic("vehicle_maint", "Vehicle Maintenance", 54, 80, 3.12),
            _basic("driver_fitness", "Driver Fitness", 22, 80, 0.40),
            _basic("controlled_subst", "Controlled Subst./Alcohol", 8, 80, 0.0),
            _basic("hazmat", "HM Compliance", None, 80, None),
            _basic("crash", "Crash Indicator", 69, 65, None),
        ],
        "inspections_24mo": 141, "violations_24mo": 96,
        "driver_oos_count": 7, "vehicle_oos_count": 19,
        "driver_oos_rate": 0.05, "vehicle_oos_rate": 0.13,
        "dataq": {"challengeable": 14, "filed": 9, "removed": 6, "points_removed": 22, "success_rate": 0.67},
        "insurance": {
            "company": "Great West Casualty", "type": "Primary Liability",
            "policy_number": "GW-4491203", "annual_premium_cents": 18400000,
            "per_driver_rate_cents": 900, "attorney_fee_exposure": "none",
            "note": "Recurring compliance SaaS — no claims-linked or attorney-fee exposure. The premium is priced off the same FMCSA BASICs shown here.",
        },
        "underwriting_note": "Unsafe Driving and Crash Indicator are over intervention thresholds — the two BASICs that most move commercial-auto premiums. 6 violations already removed via DataQ (22 points).",
    },
}

RISK_DRIVER = {
    # Owner-operator — carries their own policy; their PSP/MVR + DataQ posture is a direct underwriting input.
    "drv_delgado": {
        "role": "owner_operator", "safety_score": 71, "score_band": "Fair",
        "cdl_points_12mo": 4, "cdl_points_36mo": 7,
        "psp_status": "available", "mvr_status": "current", "mvr_age_days": 88,
        "dataq_opportunities": 2, "dataq_removed": 1,
        "violations_24mo": 3, "inspections_24mo": 5, "oos_events": 1,
        "insurance": {
            "company": "Progressive Commercial", "type": "Owner-Operator (Non-Trucking + Occ/Acc)",
            "policy_number": "PGR-77219", "annual_premium_cents": 1420000, "attorney_fee_exposure": "none",
            "note": "Owner-operator underwrites their own risk — PSP/MVR history and DataQ wins feed the renewal price directly.",
        },
        "underwriting_note": "One inspection violation is DataQ-challengeable; removing it drops the 12-month point count and lifts the risk band.",
    },
    "drv_lovelace": {
        "role": "company_driver", "safety_score": 88, "score_band": "Good",
        "cdl_points_12mo": 0, "cdl_points_36mo": 2,
        "psp_status": "current", "mvr_status": "current", "mvr_age_days": 40,
        "dataq_opportunities": 0, "dataq_removed": 1,
        "violations_24mo": 1, "inspections_24mo": 4, "oos_events": 0,
        "underwriting_note": "Clean recent record — covered under the carrier's policy. No open DataQ opportunities.",
    },
    "drv_johnson": {
        "role": "company_driver", "safety_score": 63, "score_band": "Watch",
        "cdl_points_12mo": 6, "cdl_points_36mo": 9,
        "psp_status": "available", "mvr_status": "stale", "mvr_age_days": 210,
        "dataq_opportunities": 1, "dataq_removed": 0,
        "violations_24mo": 5, "inspections_24mo": 8, "oos_events": 2,
        "underwriting_note": "HOS/logbook violations are driving the score down; MVR is stale (>180d) and one violation is DataQ-challengeable.",
    },
}

TIP_SCORE_RISK = {
    "drv_lovelace": {
        # Golden cross-portal example: 745 Preferred / 90% confidence.
        "unsafeDriving": 0.30, "crash": 0.10, "hoursOfService": 0.40,
        "driverFitness": 0.20, "substanceAlcohol": 0.0, "safetyManagement": 0.25,
    },
    "drv_delgado": {
        "unsafeDriving": 0.31, "crash": 0.18, "hoursOfService": 0.22,
        "driverFitness": 0.16, "substanceAlcohol": 0.0, "safetyManagement": 0.34,
    },
    "drv_johnson": {
        "unsafeDriving": 0.56, "crash": 0.38, "hoursOfService": 0.72,
        "driverFitness": 0.28, "substanceAlcohol": 0.0, "safetyManagement": 0.61,
    },
}

# ── Attorneys (one per network tier — anchor, independent, clinic) ───────────
ATTORNEYS = [
    {
        "uid": "att_anchor", "email": "anchor@firm.local", "full_name": "Dana Whitfield",
        "firm_name": "Whitfield Transportation Law", "tier": "law_firm_partner",
        "bar_state": "TX", "states_covered": ["TX"], "self_approval": True,
        "accepting_cases": True, "rate_model": "tiered",
    },
    {
        "uid": "att_indie", "email": "indie@solo.local", "full_name": "Cyrus Boyd",
        "firm_name": "Boyd Legal", "tier": "independent",
        "bar_state": "OK", "states_covered": ["OK", "KS"], "self_approval": False,
        "accepting_cases": True, "rate_model": "flat",
    },
    {
        "uid": "att_clinic", "email": "clinic@university.local", "full_name": "Prof. Iris Mbeki",
        "firm_name": "State University Transportation Law Clinic", "tier": "legal_clinic",
        "bar_state": "KS", "states_covered": ["KS"], "self_approval": False,
        "accepting_cases": True, "rate_model": "clinic",
    },
    # Real relationship: a Kansas firm licensed to handle both KS and MO.
    {
        "uid": "att_ks_firm", "email": "firm@ksdefense.local", "full_name": "Harlan Reese",
        "firm_name": "Reese & Associates (KS)", "tier": "law_firm_partner",
        "bar_state": "KS", "states_covered": ["KS", "MO"], "self_approval": True,
        "accepting_cases": True, "rate_model": "tiered",
        "anchor_states": ["KS", "MO"],
    },
]

# ── Tickets (one per pass state + one closed, spread across states) ──────────
TICKETS = [
    {
        "id": "TX-2026-441", "driver_id": "drv_lovelace", "carrier_id": "car_bigrig",
        "attorney_status": "AI Review", "pass_status": "yellow",
        "violation_category": "Speeding (15+)", "violation_description": "68 in a 53 zone",
        "ticket_state": "TX", "ticket_county": "Bexar", "ticket_city": "San Antonio",
        "court_date": days(3), "citation_number": "TX-441-2026", "fine_amount_cents": 38500,
        "source": "driver_upload",
    },
    {
        "id": "OK-2026-118", "driver_id": "drv_johnson", "carrier_id": "car_bigrig",
        "attorney_status": "AI Review", "pass_status": "red",
        "violation_category": "Logbook / HOS", "violation_description": "Form and manner violation",
        "ticket_state": "OK", "ticket_county": "Oklahoma", "ticket_city": "Oklahoma City",
        "court_date": days(11), "citation_number": "OK-118-2026", "fine_amount_cents": 27500,
        "source": "carrier_upload",
    },
    {
        "id": "KS-2026-902", "driver_id": "drv_delgado", "carrier_id": None,
        "attorney_status": "New", "pass_status": "green",
        "violation_category": "Improper lane change", "violation_description": "Unsafe lane change, no signal",
        "ticket_state": "KS", "ticket_county": "Sedgwick", "ticket_city": "Wichita",
        "court_date": days(21), "citation_number": "KS-902-2026", "fine_amount_cents": 19000,
        "source": "driver_upload",
    },
    {
        "id": "MO-2026-233", "driver_id": "drv_lovelace", "carrier_id": "car_bigrig",
        "attorney_status": "Ticket Closed", "pass_status": "green",
        "violation_category": "Following too close", "violation_description": "Following distance violation",
        "ticket_state": "MO", "ticket_county": "Jackson", "ticket_city": "Kansas City",
        "court_date": days(-14), "citation_number": "MO-233-2026", "fine_amount_cents": 22500,
        "source": "driver_upload", "assigned_attorney_id": "att_indie", "outcome": "dismissed",
        "selected_fee_cents": 45000, "original_disposition": "citation_filed",
        "final_disposition": "dismissed", "original_points": 3, "final_points": 0,
    },
    {
        "id": "TX-2025-880", "driver_id": "drv_lovelace", "carrier_id": "car_bigrig",
        "attorney_status": "Payout Sent", "pass_status": "green",
        "violation_category": "Speeding", "violation_description": "11–14 mph over",
        "ticket_state": "TX", "ticket_county": "Bexar", "ticket_city": "San Antonio",
        "court_date": days(-90), "citation_number": "TX-880-2025",
        "fine_amount_cents": 32500, "source": "driver_upload",
        "assigned_attorney_id": "att_anchor", "outcome": "dismissed",
        "selected_fee_cents": 58000, "original_disposition": "citation_filed",
        "final_disposition": "dismissed", "original_points": 3, "final_points": 0,
    },
    {
        "id": "TX-2025-902", "driver_id": "drv_johnson", "carrier_id": "car_bigrig",
        "attorney_status": "Payout Sent", "pass_status": "green",
        "violation_category": "Unsafe lane change", "violation_description": "Lane change",
        "ticket_state": "TX", "ticket_county": "Travis", "ticket_city": "Austin",
        "court_date": days(-62), "citation_number": "TX-902-2025",
        "fine_amount_cents": 29000, "source": "carrier_upload",
        "assigned_attorney_id": "att_anchor", "outcome": "fine_reduction",
        "selected_fee_cents": 58000, "original_disposition": "citation_filed",
        "final_disposition": "fine_reduced", "original_fine_cents": 29000,
        "final_fine_cents": 14500, "original_points": 2, "final_points": 1,
    },
]

# Extra fields the DRIVER sees on their own ticket (not the attorney/staff view):
# who's handling it, what we still need from them, and the outcome. Keyed by
# ticket id, merged only into the drivers/{id}/tickets subdoc.
DRIVER_TICKET_EXTRA = {
    "TX-2026-441": {
        "documents_needed": [
            {"label": "Photo of the back of the citation",
             "why": "Some Texas courts print the appearance details on the reverse — we want the whole thing.",
             "status": "requested"},
        ],
    },
    "MO-2026-233": {
        "attorney_name": "Cyrus Boyd", "attorney_firm": "Boyd Legal",
        "attorney_phone": "(405) 555-0170", "outcome": "dismissed",
        "outcome_note": "Dismissed at the pretrial conference — nothing added to your record.",
    },
}

# Seeded attorney↔driver message threads (drivers/{id}/tickets/{tid}/messages).
DRIVER_TICKET_MESSAGES = {
    "MO-2026-233": [
        {"from": "attorney", "author_name": "Cyrus Boyd",
         "body": "Hi Ada — I've picked up your following-too-close citation out of Jackson County. I've handled these in this court before.",
         "days_ago": 30},
        {"from": "driver",
         "body": "Thanks. Do I need to show up to court?",
         "days_ago": 30},
        {"from": "attorney", "author_name": "Cyrus Boyd",
         "body": "No — I'll appear for you. Sit tight and don't pay the ticket.",
         "days_ago": 29},
        {"from": "attorney", "author_name": "Cyrus Boyd",
         "body": "Good news: dismissed at pretrial. Nothing goes on your record. You're all set.",
         "days_ago": 14},
    ],
}



# ── Cases (active work, not just scans) ─────────────────────────────────────
# The marketplace is where a released case collects attorney bids. Each case
# carries a bid_status: "none" (priced, not yet released), "open" (collecting
# bids), "awarded"/"closed" (a bid was selected / case resolved).
CASES = [
    {
        # Ready to price + release — the pricing / release-to-market demo.
        "id": "case_ks902", "ticket_id": "KS-2026-902", "driver_id": "drv_delgado",
        "driver_name": "Rosa Delgado", "state": "KS", "state_name": "Kansas",
        "county": "Sedgwick", "status": "Sourcing", "bid_status": "none",
        "violation_category": "Lane Violation", "court_date_offset": 21,
        "price_low_cents": 45000, "price_high_cents": 90000, "opened_offset": -1,
    },
    {
        # In market, collecting bids — the review + select demo (see BIDS below).
        "id": "case_tx441", "ticket_id": "TX-2026-441", "driver_id": "drv_lovelace",
        "driver_name": "Ada Lovelace", "state": "TX", "state_name": "Texas",
        "county": "Bexar", "status": "In Market", "bid_status": "open",
        "violation_category": "Speeding (15+)", "court_date_offset": 3,
        "price_low_cents": 55000, "price_high_cents": 108000, "opened_offset": 0,
        "bid_requested_offset_hours": -20, "bid_deadline_offset_hours": 28,
        "bid_count": 3,
    },
    {
        # Awarded + resolved — the historical / outcome record.
        "id": "case_mo233", "ticket_id": "MO-2026-233", "driver_id": "drv_lovelace",
        "driver_name": "Ada Lovelace", "state": "MO", "state_name": "Missouri",
        "county": "Jackson", "status": "Closed", "bid_status": "awarded",
        "assigned_attorney_id": "att_ks_firm", "attorney_name": "Reese & Associates (KS)",
        "violation_category": "Following too close", "court_date_offset": -14,
        "price_low_cents": 45000, "price_high_cents": 90000,
        "selected_fee_cents": 45000, "opened_offset": -40, "outcome": "dismissed",
    },
]

# Bids on the in-market case (cases/case_tx441/bids/{bid_id}), cheapest first.
BIDS = {
    "case_tx441": [
        {"id": "bid_boyd", "attorney_id": "att_indie", "attorney_name": "Cyrus Boyd",
         "attorney_firm": "Boyd Legal", "attorney_phone": "(405) 555-0170",
         "fee_amount": 525.0, "fee_structure": "flat", "fee_includes": "Pre-trial resolution only (trial +$300)",
         "fee_notes": "Handles most Bexar matters by remote appearance.", "win_rate": 0.66, "status": "submitted"},
        {"id": "bid_vega", "attorney_id": "att_vega", "attorney_name": "Marisol Vega",
         "attorney_firm": "Vega CDL Defense", "attorney_phone": "(210) 555-0198",
         "fee_amount": 580.0, "fee_structure": "flat", "fee_includes": "Includes trial",
         "fee_notes": "Former Bexar County prosecutor; appears in person.", "win_rate": 0.73, "status": "submitted"},
        {"id": "bid_whitfield", "attorney_id": "att_anchor", "attorney_name": "Dana Whitfield",
         "attorney_firm": "Whitfield Transportation Law", "attorney_phone": "(210) 555-0110",
         "fee_amount": 650.0, "fee_structure": "flat", "fee_includes": "Includes trial + one appeal",
         "fee_notes": "Anchor firm; in Bexar JP courts weekly.", "win_rate": 0.79, "status": "submitted"},
    ],
}


def seed_cases() -> None:
    from datetime import timedelta as _td
    for c in CASES:
        doc = dict(c)
        cid = doc.pop("id")
        doc["court_date"] = days(doc.pop("court_date_offset"))
        doc["opened_at"] = days(doc.pop("opened_offset"))
        if "bid_requested_offset_hours" in doc:
            doc["bid_requested_at"] = (NOW + _td(hours=doc.pop("bid_requested_offset_hours"))).isoformat()
        if "bid_deadline_offset_hours" in doc:
            doc["bid_deadline"] = (NOW + _td(hours=doc.pop("bid_deadline_offset_hours"))).isoformat()
        doc["updated_at"] = NOW
        doc["seeded"] = True
        db.collection("cases").document(cid).set(doc, merge=True)
        # Bids are dual-written (per bids.py): the per-case subcollection the
        # marketplace detail reads, and a top-level bids/ doc the select-bid
        # endpoint updates. Seeding both keeps award/select from 500-ing.
        for b in BIDS.get(cid, []):
            bid = dict(b)
            bid_id = bid.pop("id")
            bid["created_at"] = NOW
            bid["seeded"] = True
            bid["bid_status"] = bid.get("status", "submitted")
            db.collection("cases").document(cid).collection("bids").document(bid_id).set(bid, merge=True)
            db.collection("bids").document(bid_id).set({**bid, "case_id": cid}, merge=True)
    n_bids = sum(len(v) for v in BIDS.values())
    print(f"  cases: {len(CASES)} (1 in-market with {n_bids} bids, 1 ready to price, 1 closed)")


# ── Notifications (staff work-awareness feed) ───────────────────────────────
NOTIFICATIONS = [
    {"id": "ntf_1", "kind": "deadline", "severity": "critical",
     "title": "Court in 3 days — TX-441-2026",
     "body": "Ada Lovelace's speeding case still needs attorney approval.",
     "link": "review", "age_hours": 1},
    {"id": "ntf_2", "kind": "review", "severity": "warning",
     "title": "RED scan needs a human",
     "body": "OK-118-2026 came back low confidence on 5 fields.",
     "link": "review", "age_hours": 5},
    {"id": "ntf_3", "kind": "network", "severity": "info",
     "title": "Reese & Associates accepted a case",
     "body": "KS-902-2026 engaged — Sedgwick County.",
     "link": "cases", "age_hours": 26},
    {"id": "ntf_4", "kind": "outcome", "severity": "success",
     "title": "Case dismissed — MO-233-2026",
     "body": "Following-too-close dismissed. Driver score updated.",
     "link": "cases", "age_hours": 50, "read": True},
]


# ── Payout requests (attorney draw-downs the Captain finance view manages) ──
PAYOUTS = [
    {"id": "payout_indie", "attorney_id": "att_indie", "attorney_name": "Cyrus Boyd · Boyd Legal",
     "ticket_ids": ["MO-2026-233"], "total_amount": 450.0, "status": "requested", "requested_offset": -2},
    {"id": "payout_anchor", "attorney_id": "att_anchor", "attorney_name": "Whitfield Transportation Law",
     "ticket_ids": ["TX-2025-880", "TX-2025-902"], "total_amount": 1160.0, "status": "paid",
     "requested_offset": -12, "paid_offset": -9, "payout_method": "Choice Digital"},
]


def seed_payouts() -> None:
    from datetime import timedelta as _td
    # Remove the superseded inconsistent local-only sample on replay.
    db.collection("payout_requests").document("payout_ks_firm").delete()
    for p in PAYOUTS:
        doc = dict(p)
        pid = doc.pop("id")
        doc["requested_at"] = (NOW + _td(days=doc.pop("requested_offset"))).isoformat()
        if "paid_offset" in doc:
            doc["paid_at"] = (NOW + _td(days=doc.pop("paid_offset"))).isoformat()
        doc.setdefault("paid_at", None)
        doc.setdefault("payout_method", None)
        doc.setdefault("processed_by", None)
        doc["seeded"] = True
        db.collection("payout_requests").document(pid).set(doc, merge=True)
    pending = sum(1 for p in PAYOUTS if p["status"] != "paid")
    print(f"  payouts: {len(PAYOUTS)} ({pending} pending)")


def seed_notifications() -> None:
    from datetime import timedelta as _td
    for n in NOTIFICATIONS:
        doc = dict(n)
        nid = doc.pop("id")
        doc["created_at"] = (NOW - _td(hours=doc.pop("age_hours"))).isoformat()
        doc.setdefault("read", False)
        doc["seeded"] = True
        db.collection("staff_notifications").document(nid).set(doc, merge=True)
    unread = sum(1 for n in NOTIFICATIONS if not n.get("read"))
    print(f"  notifications: {len(NOTIFICATIONS)} ({unread} unread)")


# ── Scan queue (what Overview stats + Scan Feed read) ───────────────────────
def _field(value: str, conf: float, reason: str) -> dict:
    """Shape one extracted field the way the pipeline writes it — value plus the
    reviewer-facing confidence and rationale the Review Detail renders."""
    return {"value": value, "confidence_score": conf, "ai_reason": reason, "raw_evidence": value}


def seed_scans() -> None:
    """scan_queue is a separate collection from tickets — it holds the AI
    pipeline's own record of each scan (extractions, agent events, cost).
    Overview KPIs and the Scan Feed read from here; the Review Detail reads
    process_response.result to render each extracted field with its confidence
    and correct it. Seeding realistic fields (with genuine low-confidence and
    dual-pass conflicts on the two pending scans) is what lets the reviewer
    flow be exercised end-to-end locally."""
    from datetime import timedelta as _td

    # Enrichment the pipeline computes per scan and the Review Detail's
    # Intelligence panel surfaces (charlotte_ray CSA points, madam_walker
    # attorney matches, doc_scoring DataQ eligibility). Mock mode doesn't
    # re-run the graph, so these are seeded to mirror real agent output.
    intel = {
        "scan_tx441": {
            "cdl_point_impact": {
                "violation_category": "Speeding (15+)", "cdl_points": 4, "severity": "serious",
                "csa_category": "Unsafe Driving", "must_appear_in_court": True, "attorney_recommended": True,
            },
            "attorney_matches": [
                {"name": "Dana Whitfield", "firm": "Whitfield Transportation Law", "email": "anchor@firm.local",
                 "phone": "(210) 555-0110", "rating": 4.8, "win_rate": 0.79, "total_tickets": 214, "match_type": "county"},
                {"name": "Cyrus Boyd", "firm": "Boyd Legal", "email": "indie@solo.local",
                 "phone": "(405) 555-0170", "rating": 4.5, "win_rate": 0.66, "total_tickets": 98, "match_type": "state"},
            ],
            "no_attorney_flag": False,
            "dataq_assessment": {
                "eligible": False, "confidence": "low",
                "basis": "Moving citation with no linked FMCSA inspection record. DataQ challenges apply to inspection and crash data on the CSA profile, not to a court citation on its own.",
                "window_days": None, "action": "Defend the citation in court; no DataQ to file unless a roadside inspection is later linked.",
            },
        },
        "scan_ok118": {
            "cdl_point_impact": {
                "violation_category": "ELD/Logs", "cdl_points": 3, "severity": "standard",
                "csa_category": "Hours of Service", "must_appear_in_court": False, "attorney_recommended": True,
            },
            "attorney_matches": [
                {"name": "Cyrus Boyd", "firm": "Boyd Legal", "email": "indie@solo.local",
                 "phone": "(405) 555-0170", "rating": 4.5, "win_rate": 0.66, "total_tickets": 98, "match_type": "county"},
            ],
            "no_attorney_flag": False,
            "dataq_assessment": {
                "eligible": True, "confidence": "medium",
                "basis": "Inspection-based Hours-of-Service / form-and-manner violation with a documentation conflict — the classic DataQ-challengeable record type.",
                "window_days": 730, "action": "File a DataQ challenge with FMCSA within 2 years of the inspection date if the logbook evidence contradicts the citation.",
            },
        },
        "scan_ks902": {
            "cdl_point_impact": {
                "violation_category": "Lane Violation", "cdl_points": 2, "severity": "standard",
                "csa_category": "Unsafe Driving", "must_appear_in_court": False, "attorney_recommended": False,
            },
            "attorney_matches": [
                {"name": "Prof. Iris Mbeki", "firm": "State University Transportation Law Clinic",
                 "email": "clinic@university.local", "phone": "(316) 555-0130", "rating": 4.6,
                 "win_rate": 0.71, "total_tickets": 41, "match_type": "county"},
            ],
            "no_attorney_flag": False,
            "dataq_assessment": {
                "eligible": False, "confidence": "low",
                "basis": "Minor moving citation, no linked inspection record.",
                "window_days": None, "action": "No DataQ applicable.",
            },
        },
        "scan_mo233": {
            "cdl_point_impact": {
                "violation_category": "Following too close", "cdl_points": 3, "severity": "serious",
                "csa_category": "Unsafe Driving", "must_appear_in_court": False, "attorney_recommended": True,
            },
            "attorney_matches": [
                {"name": "Harlan Reese", "firm": "Reese & Associates (KS)", "email": "firm@ksdefense.local",
                 "phone": "(816) 555-0155", "rating": 4.7, "win_rate": 0.74, "total_tickets": 132, "match_type": "state"},
            ],
            "no_attorney_flag": False,
            "dataq_assessment": {
                "eligible": False, "confidence": "low",
                "basis": "Court citation resolved (dismissed); no inspection record to challenge.",
                "window_days": None, "action": "No DataQ applicable.",
            },
        },
    }

    # Two pending scans carry real problems a reviewer must resolve; the two
    # green scans are clean (already approved) so an approved record is viewable.
    scans = [
        {
            "id": "scan_tx441", "ticket": "TX-2026-441", "pass": "yellow", "days_ago": 0,
            "confidence": 0.74, "matched": True, "status": "pending",
            "low": ["Ticket_Court__c", "Court_Phone_Number__c"],
            "conflicts": ["Court_Date__c", "Citation_Number__c"],
            "result": {
                "file_type": "Ticket",
                "document_text_format": "handwritten",
                "file_type_analysis": {"confidence_score": 0.91, "ai_reason": "Uniform traffic citation layout."},
                "Date_of_Ticket__c": _field("07/12/2026", 0.93, "Clearly printed issue date."),
                "Citation_Number__c": _field("TX-441-2026", 0.58, "Pass 1 read TX-441-2026, pass 2 read TX-447-2026 — digit ambiguous."),
                "Ticket_State__c": _field("TX", 0.99, "Pre-printed state header."),
                "Ticket_County__c": _field("Bexar", 0.88, "County box legible."),
                "Ticket_City__c": _field("San Antonio", 0.9, "Municipal court header."),
                "Violation_Description__c": _field("68 in a 53 zone", 0.86, "Speed values written in officer's hand."),
                "Violation_Category__c": _field("Speeding (15+)", 0.82, "15+ over the posted limit."),
                "Court_Date__c": _field("07/23/2026", 0.55, "Pass 1 read 07/23, pass 2 read 07/28 — handwriting unclear."),
                "Ticket_Court__c": _field("Bexar County JP Ct 2", 0.44, "Court name partially obscured by a fold."),
                "Court_Phone_Number__c": _field("(210) 555-0143", 0.4, "Phone digits faint; last group uncertain."),
                "Accident__c": _field("No", 0.95, "No accident box checked."),
                "Drivers_License_Type__c": _field("CDL-A", 0.87, "License type box marked A."),
            },
        },
        {
            "id": "scan_ok118", "ticket": "OK-2026-118", "pass": "red", "days_ago": 1,
            "confidence": 0.41, "matched": False, "status": "pending",
            "low": ["Violation_Description__c", "Ticket_Court__c", "Court_Date__c"],
            "conflicts": ["Citation_Number__c", "Ticket_County__c", "Violation_Category__c",
                          "Date_of_Ticket__c", "Court_Date__c"],
            "result": {
                "file_type": "Ticket",
                "document_text_format": "handwritten",
                "file_type_analysis": {"confidence_score": 0.62, "ai_reason": "Low-contrast phone photo; edges cropped."},
                "Date_of_Ticket__c": _field("06/30/2026", 0.48, "Pass 1 read 06/30, pass 2 read 05/30 — month digit unclear."),
                "Citation_Number__c": _field("OK-118-2026", 0.39, "Two passes disagreed on the middle digits."),
                "Ticket_State__c": _field("OK", 0.97, "State header legible."),
                "Ticket_County__c": _field("Oklahoma", 0.51, "Pass 2 read 'Oklahoma City' as the county — conflicting."),
                "Ticket_City__c": _field("Oklahoma City", 0.72, "City line legible."),
                "Violation_Description__c": _field("Form and manner violation", 0.35, "Officer narrative largely illegible."),
                "Violation_Category__c": _field("ELD/Logs", 0.44, "Pass 1 chose ELD/Logs, pass 2 chose Equipment/Maintenance."),
                "Court_Date__c": _field("07/31/2026", 0.33, "Court date box smudged; both passes low."),
                "Ticket_Court__c": _field("OKC Municipal", 0.42, "Court name abbreviated and faint."),
                "Accident__c": _field("No", 0.9, "No accident indicated."),
                "Drivers_License_Type__c": _field("CDL-A", 0.8, "License class marked."),
            },
        },
        {
            "id": "scan_ks902", "ticket": "KS-2026-902", "pass": "green", "days_ago": 2,
            "confidence": 0.96, "matched": True, "status": "approved",
            "low": [], "conflicts": [],
            "result": {
                "file_type": "Ticket",
                "document_text_format": "printed",
                "file_type_analysis": {"confidence_score": 0.98, "ai_reason": "Clean printed citation."},
                "Date_of_Ticket__c": _field("07/05/2026", 0.98, "Printed date."),
                "Citation_Number__c": _field("KS-902-2026", 0.97, "Printed citation number."),
                "Ticket_State__c": _field("KS", 0.99, "State header."),
                "Ticket_County__c": _field("Sedgwick", 0.96, "County printed."),
                "Ticket_City__c": _field("Wichita", 0.97, "City printed."),
                "Violation_Description__c": _field("Unsafe lane change, no signal", 0.95, "Printed narrative."),
                "Violation_Category__c": _field("Lane Violation", 0.94, "Improper lane change."),
                "Court_Date__c": _field("08/10/2026", 0.96, "Printed appearance date."),
            },
        },
        {
            "id": "scan_mo233", "ticket": "MO-2026-233", "pass": "green", "days_ago": 9,
            "confidence": 0.93, "matched": True, "status": "approved",
            "low": [], "conflicts": [],
            "result": {
                "file_type": "Ticket",
                "document_text_format": "printed",
                "file_type_analysis": {"confidence_score": 0.97, "ai_reason": "Clean printed citation."},
                "Date_of_Ticket__c": _field("06/20/2026", 0.97, "Printed date."),
                "Citation_Number__c": _field("MO-233-2026", 0.96, "Printed citation number."),
                "Ticket_State__c": _field("MO", 0.99, "State header."),
                "Ticket_County__c": _field("Jackson", 0.95, "County printed."),
                "Ticket_City__c": _field("Kansas City", 0.96, "City printed."),
                "Violation_Description__c": _field("Following distance violation", 0.94, "Printed narrative."),
                "Violation_Category__c": _field("Following too close", 0.93, "Following too close."),
                "Court_Date__c": _field("07/06/2026", 0.95, "Printed appearance date."),
            },
        },
    ]
    for s in scans:
        created = (NOW - _td(days=s["days_ago"])).isoformat()
        db.collection("scan_queue").document(s["id"]).set({
            "id": s["id"],
            "filename": f"{s['ticket']}.jpg",
            "pass_status": s["pass"],
            "status": s["status"],
            "created_at": created,
            "updated_at": created,
            "image_paths": [],  # no source image in the local seed — detail degrades gracefully
            "doc_type": "Ticket",
            "prompt_version": "v2",
            "attorney_matched": s["matched"],
            "attorney_match_type": "county" if s["matched"] else None,
            "has_price_estimate": True,
            "price_estimate": {"low": 45000, "high": 95000},
            "process_response": {
                "queue_id": s["id"],
                "pass_status": s["pass"],
                "confidence_score": s["confidence"],
                "result": s["result"],
                "low_confidence_fields": s["low"],
                "dual_conflicts": s["conflicts"],
                "referee_notes": f"{s['pass'].upper()} pass — {len(s['low'])} low-confidence, {len(s['conflicts'])} conflicting field(s).",
                "token_usage": [{"model": "claude-sonnet-4-6", "input_tokens": 4200,
                                 "output_tokens": 900, "cache_read_input_tokens": 0,
                                 "cache_creation_input_tokens": 0}],
                "scan_cost_usd": 0.0261,
                # Intelligence the pipeline computes (surfaced in the Review Detail).
                **intel.get(s["id"], {}),
            },
            "consensus_extraction": {},
            "seeded": True,
        }, merge=True)
        # Deterministic child rows make Captain Agent Health useful immediately
        # while remaining safe to replay on an existing local emulator.
        seeded_agent_events = [
            ("roux", "passed", {}),
            ("document_gate", "ok", {"doc_type": "Ticket"}),
            ("photo_analyst", "complete", {"photo_type": "document"}),
            ("carver", "pass_1_complete", {
                "fields_filled": len(s["result"]),
                "empty_fields": [],
                "low_confidence_fields": s["low"],
                "usage": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 4200,
                    "output_tokens": 900,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            }),
            ("bolin", "scored", {
                "avg_score": s["confidence"],
                "critical_failures": [],
                "low_confidence_fields": s["low"],
            }),
            ("bunche", "merge_complete", {
                "improvements_count": len(s["conflicts"]),
                "dual_conflicts": s["conflicts"],
            }),
            ("ida_wells", "complete", {
                "completeness_score": s["confidence"],
                "missing_fields": s["low"],
            }),
            ("charlotte_ray", "scored", {
                "unknown_category": False,
                "zero_points": False,
                "attorney_recommended": s["matched"],
            }),
            ("jollof", "complete", {"cdl_match": "match"}),
            ("stagecoach_mary", "queued", {}),
            ("bass_reeves", "queued", {}),
            ("banneker", "complete", {"court_found": True, "county_court_found": True}),
            ("madam_walker", "complete", {
                "matches_found": 1 if s["matched"] else 0,
                "no_attorney": not s["matched"],
                "match_types": ["county"] if s["matched"] else [],
            }),
            ("tubman", "complete", {"urgency_level": "MEDIUM", "days_until_court": 20}),
            ("douglass", "complete", {
                "conflict_count": len(s["conflicts"]),
                "evidence_count": 1,
                "uncategorized_evidence": 0,
                "conflict_types": s["conflicts"],
            }),
        ]
        for agent_name, event_name, detail in seeded_agent_events:
            db.collection("scan_queue").document(s["id"]).collection("agent_events").document(
                f"seed-{agent_name}"
            ).set({
                "scan_id": s["id"],
                "agent": agent_name,
                "event": event_name,
                "detail": detail,
                "created_at": created,
                "seeded": True,
            }, merge=True)
    print(f"  scan_queue: {len(scans)} (Overview KPIs + Scan Feed + Review Detail)")


def seed() -> None:
    print(f"Seeding emulator project '{PROJECT}'\n")

    for uid, email, claims in STAFF:
        upsert_user(uid, email, claims)
        db.collection("staff").document(uid).set(
            {"email": email, **claims, "seeded": True}, merge=True
        )
    print(f"  staff: {len(STAFF)}")

    pii_cipher = PiiCipher.from_env()
    for d in DRIVERS:
        upsert_user(d["uid"], d["email"], {"role": "driver"}, phone_number=d.get("phone"))
        extra = PROFILE_EXTRA.get(d["uid"], {})
        doc = {
            key: value for key, value in d.items()
            if key not in {"cdl_number", "cdl_state"}
        }
        doc["principal_id"] = principal_id_for_uid(d["uid"])
        doc["seeded"] = True
        # The carrier roster endpoint reads full_name; compose it so rosters show
        # people rather than driver ids.
        doc["full_name"] = f"{d['first_name']} {d['last_name']}"
        # Existing drivers already completed onboarding — flag them so the app's
        # profile gate lets them straight in, and fill the profile fields.
        doc["profile_complete"] = True
        doc.update({
            key: value for key, value in extra.items()
            if key not in {"address", "dob", "ssn_last4", "cdl_expiration"}
        })
        if d["uid"] in RISK_DRIVER:
            doc["risk_profile"] = RISK_DRIVER[d["uid"]]
        # Replace the public profile so rerunning the seed also removes legacy
        # plaintext verification fields from an existing emulator document.
        db.collection("drivers").document(d["uid"]).set(doc)
        db.collection("driver_private").document(d["uid"]).set({
            "driver_id": d["uid"],
            "dob": extra["dob"],
            "cdl_number": d["cdl_number"],
            "cdl_state": d["cdl_state"],
            "cdl_expiration": extra["cdl_expiration"],
            "address": extra["address"],
            "ssn_last4_encrypted": pii_cipher.encrypt(
                extra["ssn_last4"],
                subject=d["uid"],
                field="ssn_last4",
            ),
            "seeded": True,
        })
    for uid, (first_name, last_name) in CONNECTED_DRIVER_NAMES.items():
        ref = db.collection("drivers").document(uid)
        if ref.get().exists:
            ref.set({
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}",
                "seeded": True,
            }, merge=True)
    print(f"  drivers: {len(DRIVERS)}")

    from app.services.tip_score import (
        ComponentInput,
        ConfidenceInput,
        ScoreCalculationInput,
        TipComponent,
        TipScoreCalculator,
        TipScoreStatus,
    )
    for profile_id, risks in TIP_SCORE_RISK.items():
        driver_id = principal_id_for_uid(profile_id)
        components = {
            TipComponent(component): ComponentInput(
                risk=risk,
                event_count=1 if risk else 0,
                verified_event_count=1 if risk else 0,
                top_factors=(
                    [f"Verified local QA factor for {component}"]
                    if risk else []
                ),
            )
            for component, risk in risks.items()
        }
        snapshot = TipScoreCalculator().calculate(ScoreCalculationInput(
            driver_id=driver_id,
            components=components,
            confidence=(
                ConfidenceInput(
                    source_completeness=0.85,
                    identity_match_quality=1.0,
                    record_freshness=0.90,
                    credential_verification=1.0,
                    exposure_sufficiency=0.75,
                )
                if profile_id == "drv_lovelace"
                else ConfidenceInput(
                    source_completeness=0.82,
                    identity_match_quality=0.96,
                    record_freshness=0.88,
                    credential_verification=0.90,
                    exposure_sufficiency=0.78,
                )
            ),
            status=(
                TipScoreStatus.OFFICIAL
                if profile_id == "drv_lovelace"
                else TipScoreStatus.PROVISIONAL
            ),
            data_as_of=NOW,
            verified_history_months=24,
            verified_inspections=max(
                1, int(RISK_DRIVER[profile_id].get("inspections_24mo") or 0)
            ),
            evidence_ids=[f"seeded-risk-profile:{driver_id}"],
            calculation_reason="local_qa_seed",
        ))
        data = snapshot.model_dump(mode="python")
        db.collection("tip_score_snapshots").document(snapshot.id).set(data)
        db.collection("tip_score_current").document(driver_id).set(data)
        # Remove the pre-principal current pointer created by older local seeds.
        # Immutable history remains available for diagnosis, but no portal may
        # read or advance a score by Firebase uid.
        db.collection("tip_score_current").document(profile_id).delete()
        db.collection("tip_score_lifecycle").document(profile_id).delete()
    print(f"  TIP Score snapshots: {len(TIP_SCORE_RISK)} (shadow QA ranking)")

    for c in CARRIERS:
        upsert_user(c["uid"], c["email"], {"role": "carrier", "carrier_id": c["uid"]})
        cdoc = {**c, "seeded": True}
        if c["uid"] in RISK_CARRIER:
            cdoc["risk_profile"] = RISK_CARRIER[c["uid"]]
        db.collection("carriers").document(c["uid"]).set(cdoc, merge=True)
        # roster entries mirror the drivers above
        roster = db.collection("carriers").document(c["uid"]).collection("drivers")
        for d in DRIVERS:
            if d["carrier_id"] == c["uid"]:
                roster.document(d["uid"]).set(
                    {
                        "first_name": d["first_name"], "last_name": d["last_name"],
                        "cdl_number": d["cdl_number"], "cdl_state": d["cdl_state"],
                        "email": d["email"], "phone": d["phone"],
                        "active": True, "fired_at": None, "seeded": True,
                    },
                    merge=True,
                )
    from app.services.carrier_lookup import carrier_discovery_detail
    fmcsa_count = 0
    for dot_number in FMCSA_SAMPLE_DOTS:
        public = carrier_discovery_detail(dot_number)
        if public is None:
            continue
        db.collection("carriers").document(dot_number).set({
            "company_name": public.get("dba_name") or public.get("legal_name"),
            "legal_name": public.get("legal_name"),
            "dba_name": public.get("dba_name"),
            "dot_number": public["dot_number"],
            "usdot": public["dot_number"],
            "mc_number": public.get("docket_number"),
            "operating_status": public.get("operating_status"),
            "authority_type": public.get("authority_type"),
            "city": public.get("city"),
            "state": public.get("state"),
            "zip": public.get("zip"),
            "phone": public.get("phone"),
            "minimum_coverage": public.get("minimum_coverage"),
            "hazmat": public.get("hazmat"),
            "passenger": public.get("passenger"),
            "carrier_level_crash_context": public.get("carrier_level_crash_context"),
            "fmcsa_provenance": public.get("provenance"),
            "status": "lead",
            "subscription_status": "prospect",
            "driver_count": None,
            "seeded": True,
            "sample_record": True,
        }, merge=True)
        fmcsa_count += 1
    print(f"  carriers: {len(CARRIERS)} enrolled + {fmcsa_count} FMCSA public samples (+ rosters)")

    for a in ATTORNEYS:
        upsert_user(a["uid"], a["email"], {"role": "attorney", "attorney_id": a["uid"]})
        db.collection("attorneys").document(a["uid"]).set({**a, "seeded": True}, merge=True)
    print(f"  attorneys: {len(ATTORNEYS)} (anchor / independent / clinic)")

    # Links each queued ticket to its scan_queue record so the Review Detail can
    # load the extracted fields, confidence, and conflicts for correction.
    scan_for_ticket = {
        "TX-2026-441": "scan_tx441", "OK-2026-118": "scan_ok118",
        "KS-2026-902": "scan_ks902", "MO-2026-233": "scan_mo233",
    }
    for t in TICKETS:
        doc = {**t, "created_at": NOW, "last_modified_date": NOW, "seeded": True}
        tid = doc.pop("id")
        doc.setdefault("ai_scan_id", scan_for_ticket.get(tid))
        db.collection("tickets").document(tid).set(doc, merge=True)
        if t["driver_id"]:
            driver_doc = {**doc, "status": t["attorney_status"], **DRIVER_TICKET_EXTRA.get(tid, {})}
            tref = db.collection("drivers").document(t["driver_id"]).collection("tickets").document(tid)
            tref.set(driver_doc, merge=True)
            # Seed an attorney↔driver thread where an attorney is engaged so the
            # driver app's messaging has real content to show.
            for i, msg in enumerate(DRIVER_TICKET_MESSAGES.get(tid, [])):
                m = dict(msg)
                m["created_at"] = (NOW - timedelta(days=m.pop("days_ago", 0), hours=m.pop("hours_ago", 0)))
                m["seeded"] = True
                tref.collection("messages").document(f"msg_{i}").set(m, merge=True)
    print(f"  tickets: {len(TICKETS)} (dual-written to driver subtrees)")

    # Feature flags ON locally — this is the flags-ON environment that used to
    # require a staging cloud project.
    flags = db.collection("feature_flags")
    for key in [
        "TIP_OS_IDENTITY_ENABLED", "TIP_OS_RECORDS_ENABLED", "TIP_OS_DOCUMENTS_ENABLED",
        "TIP_OS_WORKFLOWS_ENABLED", "TIP_OS_INTELLIGENCE_ENABLED", "TIP_OS_ADMIN_CONSOLE_ENABLED",
        "TIP_OS_CARRIER_RESOLVE_ENABLED", "TIP_OS_FINANCIAL_LEDGER_ENABLED",
        "TIP_OS_ANALYTICS_ENABLED", "TIP_OS_INTEGRATIONS_ENABLED", "TIP_OS_PARTNER_API_ENABLED",
        "TIP_OS_ENTITY_RESOLUTION_ENABLED", "TIP_OS_ATTORNEY_GOVERNANCE_ENABLED",
        "TIP_OS_LAUNCH_ASSESSMENT_ENABLED",
    ]:
        flags.document(key).set(
            {"key": key, "enabled": True, "environment": "development"},
            merge=True,
        )
    print("  feature flags: 14 enabled (local)")

    seed_scans()
    seed_cases()
    seed_payouts()
    seed_notifications()

    print("\nDone. Sign in with any seeded email, password: tipos-local")
    print("Emulator UI: http://localhost:4000")


if __name__ == "__main__":
    seed()
