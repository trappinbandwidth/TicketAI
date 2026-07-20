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

PROJECT = os.environ["FIREBASE_PROJECT_ID"]
if not firebase_admin._apps:
    firebase_admin.initialize_app(_emulator_credential(), {"projectId": PROJECT})
db = firestore.client()

NOW = datetime.now(timezone.utc)


def days(n: int) -> datetime:
    return NOW + timedelta(days=n)


def upsert_user(uid: str, email: str, claims: dict, password: str = "tipos-local") -> str:
    """Create (or refresh) an emulator auth user with role claims."""
    try:
        fb_auth.get_user(uid)
        fb_auth.update_user(uid, email=email, password=password)
    except fb_auth.UserNotFoundError:
        fb_auth.create_user(uid=uid, email=email, password=password)
    fb_auth.set_custom_user_claims(uid, claims)
    return uid


# ── Staff (the three real accounts + role coverage) ──────────────────────────
STAFF = [
    ("staff_quest", "quest@puklabs.com", {"role": "staff", "staff_role": "admin"}),
    ("staff_eniola", "eniola@rigresolve.com", {"role": "staff", "staff_role": "admin"}),
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

# ── Carriers ────────────────────────────────────────────────────────────────
CARRIERS = [
    {
        "uid": "car_bigrig", "email": "safety@bigrig.local", "company_name": "Big Rig Freight Co",
        "dot_number": "1234567", "mc_number": "MC-889120", "per_driver_rate_cents": 900,
        "subscription_status": "active", "driver_count": 62,
        "insurance_company": "Great West Casualty", "insurance_type": "primary_liability",
        "insurance_policy_number": "GW-4491203", "insurance_annual_cost_cents": 18400000,
    },
]

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
    },
]


def seed() -> None:
    print(f"Seeding emulator project '{PROJECT}'\n")

    for uid, email, claims in STAFF:
        upsert_user(uid, email, claims)
        db.collection("staff").document(uid).set(
            {"email": email, **claims, "seeded": True}, merge=True
        )
    print(f"  staff: {len(STAFF)}")

    for d in DRIVERS:
        upsert_user(d["uid"], d["email"], {"role": "driver"})
        db.collection("drivers").document(d["uid"]).set({**d, "seeded": True}, merge=True)
    print(f"  drivers: {len(DRIVERS)}")

    for c in CARRIERS:
        upsert_user(c["uid"], c["email"], {"role": "carrier", "carrier_id": c["uid"]})
        db.collection("carriers").document(c["uid"]).set({**c, "seeded": True}, merge=True)
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
    print(f"  carriers: {len(CARRIERS)} (+ rosters)")

    for a in ATTORNEYS:
        upsert_user(a["uid"], a["email"], {"role": "attorney", "attorney_id": a["uid"]})
        db.collection("attorneys").document(a["uid"]).set({**a, "seeded": True}, merge=True)
    print(f"  attorneys: {len(ATTORNEYS)} (anchor / independent / clinic)")

    for t in TICKETS:
        doc = {**t, "created_at": NOW, "last_modified_date": NOW, "seeded": True}
        tid = doc.pop("id")
        db.collection("tickets").document(tid).set(doc, merge=True)
        if t["driver_id"]:
            db.collection("drivers").document(t["driver_id"]).collection("tickets").document(tid).set(
                {**doc, "status": t["attorney_status"]}, merge=True
            )
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
        flags.document(key).set({"key": key, "enabled": True, "environment": "local"}, merge=True)
    print("  feature flags: 14 enabled (local)")

    print("\nDone. Sign in with any seeded email, password: tipos-local")
    print("Emulator UI: http://localhost:4000")


if __name__ == "__main__":
    seed()
