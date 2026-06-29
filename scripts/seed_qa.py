"""
Rig Resolve QA Seed Script
Idempotent — safe to run multiple times.

Creates:
  Firebase Auth accounts: Quest, Eniola, Justin + 3 test portal users
  Firestore collections:
    staff/          3 admin docs (Quest, Eniola, Justin)
    plans/          2 docs (Core, Pro)
    attorneys/      5 CDL defense attorneys across key states
    carriers/       1 test carrier
    drivers/        3 test drivers (1 carrier, 1 independent, 1 owner-operator)

Run:
  cd /Users/digitalmercenary/CDL_Defense/AI_Ticket_Scanner/ai-ticket-engine-main
  source .venv/bin/activate
  python3 scripts/seed_qa.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import firebase_admin
from firebase_admin import auth, credentials, firestore

if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"projectId": os.getenv("FIREBASE_PROJECT_ID", "rigresolve")})

db = firestore.client()
now = datetime.now(timezone.utc)

def upsert_auth(email: str, password: str, display_name: str) -> str:
    try:
        user = auth.get_user_by_email(email)
        auth.update_user(user.uid, password=password, display_name=display_name)
        print(f"  UPDATE  {email} → uid={user.uid}")
        return user.uid
    except auth.UserNotFoundError:
        user = auth.create_user(
            email=email, password=password,
            display_name=display_name, email_verified=True,
        )
        print(f"  CREATE  {email} → uid={user.uid}")
        return user.uid

def upsert_doc(collection: str, doc_id: str, data: dict):
    db.collection(collection).document(doc_id).set(data, merge=True)
    print(f"  DOC     {collection}/{doc_id}")


# ── Staff / Admins ────────────────────────────────────────────────────────────

print("\n=== Staff accounts ===")

STAFF = [
    {
        "email": "quest@puklabs.com",
        "password": "RigResolve2024!",
        "display_name": "Quest",
        "profile": {
            "full_name": "Quest",
            "email": "quest@puklabs.com",
            "role": "super_admin",
            "can_assign_cases": True,
            "can_approve_tickets": True,
            "can_process_payouts": True,
            "status": "active",
            "created_at": now,
        },
    },
    {
        "email": "eniola@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Eniola Dove",
        "profile": {
            "full_name": "Eniola Dove",
            "email": "eniola@rigresolve.com",
            "role": "super_admin",
            "can_assign_cases": True,
            "can_approve_tickets": True,
            "can_process_payouts": True,
            "status": "active",
            "created_at": now,
        },
    },
    {
        "email": "justin@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Justin",
        "profile": {
            "full_name": "Justin",
            "email": "justin@rigresolve.com",
            "role": "admin",
            "can_assign_cases": True,
            "can_approve_tickets": True,
            "can_process_payouts": False,
            "status": "active",
            "created_at": now,
        },
    },
]

for s in STAFF:
    uid = upsert_auth(s["email"], s["password"], s["display_name"])
    upsert_doc("staff", uid, {"firebase_uid": uid, **s["profile"]})


# ── Plans ─────────────────────────────────────────────────────────────────────

print("\n=== Plans ===")

upsert_doc("plans", "core", {
    "name": "RigResolve Core",
    "tag": "$0 DEDUCTIBLE",
    "monthly_price": 14.99,
    "safe_driver_price": 11.99,
    "tickets_per_year": 1,
    "features": [
        "1 ticket/year covered",
        "Licensed CDL defense attorney",
        "Court representation",
        "Case status tracking",
        "$0 out-of-pocket deductible",
    ],
    "eligible_driver_types": ["carrier", "independent", "owner_operator"],
    "featured": False,
    "active": True,
    "created_at": now,
})

upsert_doc("plans", "pro", {
    "name": "RigResolve Pro",
    "tag": "MOST COVERAGE",
    "monthly_price": 24.99,
    "safe_driver_price": 19.99,
    "tickets_per_year": 999,
    "features": [
        "Unlimited tickets/year",
        "Priority attorney assignment",
        "Same-day response guarantee",
        "Court representation",
        "Case status tracking",
        "$0 out-of-pocket deductible",
        "Safe Driver discount eligible",
    ],
    "eligible_driver_types": ["carrier", "independent", "owner_operator"],
    "featured": True,
    "active": True,
    "created_at": now,
})


# ── Test Carrier ──────────────────────────────────────────────────────────────

print("\n=== Carrier ===")

upsert_doc("carriers", "carrier-test-001", {
    "company_name": "Lone Star Freight LLC",
    "dot_number": "DOT-1234567",
    "mc_number": "MC-987654",
    "billing_contact_name": "Mike Hernandez",
    "billing_contact_email": "billing@lonestarfreight.com",
    "billing_type": "invoice",
    "active_driver_count": 12,
    "per_driver_rate": 11.99,
    "status": "active",
    "created_at": now,
    "created_by": "seed",
})


# ── Attorneys ─────────────────────────────────────────────────────────────────

print("\n=== Attorneys ===")

ATTORNEYS = [
    {
        "id": "atty-001",
        "firebase_uid": None,
        "application_id": None,
        "full_name": "Marcus T. Williams",
        "bar_number": "TX24601",
        "bar_state": "TX",
        "firm_name": "Williams CDL Defense Group",
        "institution": None,
        "phone": "+17135550101",
        "email": "mwilliams@cdldefense.com",
        "states_licensed": ["TX", "LA", "OK"],
        "counties_covered": ["TX:Harris", "TX:Dallas", "TX:Tarrant", "TX:Bexar"],
        "years_experience": 11,
        "tier": "senior",
        "supervising_attorney_id": None,
        "nonprofit_eligible": False,
        "max_active_cases": 999,
        "cases_active": 0,
        "cases_total": 47,
        "win_rate": 0.81,
        "preferred_contact_method": "phone",
        "payout_method": "ach",
        "payout_details": "Routing on file",
        "verified_at": now,
        "verified_by": "seed",
        "status": "active",
        "created_at": now,
    },
    {
        "id": "atty-002",
        "firebase_uid": None,
        "application_id": None,
        "full_name": "Sandra J. Flores",
        "bar_number": "FL50023",
        "bar_state": "FL",
        "firm_name": "Flores & Associates",
        "institution": None,
        "phone": "+13055550202",
        "email": "sflores@floreslaw.com",
        "states_licensed": ["FL", "GA", "SC"],
        "counties_covered": ["FL:Miami-Dade", "FL:Broward", "FL:Orange", "GA:Fulton"],
        "years_experience": 8,
        "tier": "senior",
        "supervising_attorney_id": None,
        "nonprofit_eligible": False,
        "max_active_cases": 999,
        "cases_active": 0,
        "cases_total": 31,
        "win_rate": 0.77,
        "preferred_contact_method": "email",
        "payout_method": "zelle",
        "payout_details": "sflores@floreslaw.com",
        "verified_at": now,
        "verified_by": "seed",
        "status": "active",
        "created_at": now,
    },
    {
        "id": "atty-003",
        "firebase_uid": None,
        "application_id": None,
        "full_name": "David R. Nguyen",
        "bar_number": "CA77412",
        "bar_state": "CA",
        "firm_name": "Nguyen Transportation Law",
        "institution": None,
        "phone": "+12135550303",
        "email": "dnguyen@ntlaw.com",
        "states_licensed": ["CA", "NV", "AZ"],
        "counties_covered": ["CA:Los Angeles", "CA:San Bernardino", "CA:Riverside", "NV:Clark"],
        "years_experience": 6,
        "tier": "junior",
        "supervising_attorney_id": None,
        "nonprofit_eligible": False,
        "max_active_cases": 5,
        "cases_active": 0,
        "cases_total": 18,
        "win_rate": 0.72,
        "preferred_contact_method": "phone",
        "payout_method": "venmo",
        "payout_details": "@dnguyen-law",
        "verified_at": now,
        "verified_by": "seed",
        "status": "active",
        "created_at": now,
    },
    {
        "id": "atty-004",
        "firebase_uid": None,
        "application_id": None,
        "full_name": "Patricia A. Okafor",
        "bar_number": "IL39201",
        "bar_state": "IL",
        "firm_name": "Okafor CDL Law",
        "institution": None,
        "phone": "+13125550404",
        "email": "pokafor@okaforlaw.com",
        "states_licensed": ["IL", "IN", "WI", "MO"],
        "counties_covered": ["IL:Cook", "IL:DuPage", "IN:Lake", "IN:Marion"],
        "years_experience": 14,
        "tier": "senior",
        "supervising_attorney_id": None,
        "nonprofit_eligible": False,
        "max_active_cases": 999,
        "cases_active": 0,
        "cases_total": 82,
        "win_rate": 0.85,
        "preferred_contact_method": "phone",
        "payout_method": "ach",
        "payout_details": "Routing on file",
        "verified_at": now,
        "verified_by": "seed",
        "status": "active",
        "created_at": now,
    },
    {
        "id": "atty-005",
        "firebase_uid": None,
        "application_id": None,
        "full_name": "James E. Carter",
        "bar_number": "TN10045",
        "bar_state": "TN",
        "firm_name": "Carter Trucking Defense",
        "institution": None,
        "phone": "+16155550505",
        "email": "jcarter@cartertruckinglaw.com",
        "states_licensed": ["TN", "KY", "MS", "AL", "AR"],
        "counties_covered": ["TN:Shelby", "TN:Davidson", "KY:Jefferson", "MS:Hinds"],
        "years_experience": 9,
        "tier": "senior",
        "supervising_attorney_id": None,
        "nonprofit_eligible": False,
        "max_active_cases": 999,
        "cases_active": 0,
        "cases_total": 55,
        "win_rate": 0.79,
        "preferred_contact_method": "text",
        "payout_method": "check",
        "payout_details": "PO Box 4412, Nashville TN 37201",
        "verified_at": now,
        "verified_by": "seed",
        "status": "active",
        "created_at": now,
    },
]

for a in ATTORNEYS:
    doc_id = a.pop("id")
    upsert_doc("attorneys", doc_id, a)


# ── Test Drivers ──────────────────────────────────────────────────────────────

print("\n=== Test portal users + drivers ===")

TEST_PORTAL_USERS = [
    {
        "email": "driver@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "James R. Booker",
        "driver_profile": {
            "full_name": "James R. Booker",
            "email": "driver@rigresolve.com",
            "phone": "+15125550001",
            "cdl_number": "TX-CDL-881234",
            "cdl_state": "TX",
            "dob": "04/12/1982",
            "driver_type": "carrier",
            "carrier_id": "carrier-test-001",
            "billing_type": "carrier",
            "subscription_status": "active",
            "subscription_end_date": now + timedelta(days=30),
            "plan_id": "core",
            "safe_driver_verified": False,
            "safe_driver_rate_applied": False,
            "tickets_used_this_year": 0,
            "tickets_allowed_per_year": 1,
            "status": "active",
            "created_at": now,
            "created_by": "seed",
        },
    },
    {
        "email": "driver2@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Maria E. Gutierrez",
        "driver_profile": {
            "full_name": "Maria E. Gutierrez",
            "email": "driver2@rigresolve.com",
            "phone": "+18325550002",
            "cdl_number": "TX-CDL-445567",
            "cdl_state": "TX",
            "dob": "09/28/1990",
            "driver_type": "independent",
            "carrier_id": None,
            "billing_type": "self",
            "subscription_status": "active",
            "subscription_end_date": now + timedelta(days=22),
            "plan_id": "pro",
            "safe_driver_verified": True,
            "safe_driver_rate_applied": True,
            "tickets_used_this_year": 0,
            "tickets_allowed_per_year": 999,
            "status": "active",
            "created_at": now,
            "created_by": "seed",
        },
    },
    {
        "email": "driver3@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Terrell D. Washington",
        "driver_profile": {
            "full_name": "Terrell D. Washington",
            "email": "driver3@rigresolve.com",
            "phone": "+14045550003",
            "cdl_number": "GA-CDL-773321",
            "cdl_state": "GA",
            "dob": "06/15/1978",
            "driver_type": "owner_operator",
            "carrier_id": None,
            "billing_type": "self",
            "oo_dot_number": "DOT-9988776",
            "oo_mc_number": "MC-112233",
            "oo_company_name": "Washington Freight LLC",
            "oo_num_trucks": 2,
            "subscription_status": "active",
            "subscription_end_date": now + timedelta(days=15),
            "plan_id": "pro",
            "safe_driver_verified": False,
            "safe_driver_rate_applied": False,
            "tickets_used_this_year": 1,
            "tickets_allowed_per_year": 999,
            "status": "active",
            "created_at": now,
            "created_by": "seed",
        },
    },
]

for u in TEST_PORTAL_USERS:
    uid = upsert_auth(u["email"], u["password"], u["display_name"])
    profile = {"firebase_uid": uid, **u["driver_profile"]}
    upsert_doc("drivers", uid, profile)


# ── Test attorney portal user ─────────────────────────────────────────────────

print("\n=== Test attorney portal user ===")

atty_uid = upsert_auth("attorney@rigresolve.com", "RigResolve2024!", "Test Attorney")
# Link test attorney portal login to atty-001
db.collection("attorneys").document("atty-001").update({"firebase_uid": atty_uid})
print(f"  LINKED attorney@rigresolve.com → attorneys/atty-001")


# ── Summary ───────────────────────────────────────────────────────────────────

print("""
=== SEED COMPLETE ===

Admin accounts (Firebase Auth + staff/ Firestore):
  quest@puklabs.com       super_admin
  eniola@rigresolve.com   super_admin
  justin@rigresolve.com   admin

Test portal accounts:
  driver@rigresolve.com    → drivers/  (carrier driver, Core plan)
  driver2@rigresolve.com   → drivers/  (independent, Pro + safe driver)
  driver3@rigresolve.com   → drivers/  (owner-operator, Pro)
  attorney@rigresolve.com  → attorneys/atty-001

All passwords: RigResolve2024!

Plans seeded:   plans/core ($14.99/$11.99)  plans/pro ($24.99/$19.99)
Attorneys:      5 active CDL defense attorneys (TX, FL, CA, IL, TN)
Carriers:       1 (Lone Star Freight LLC)
""")
