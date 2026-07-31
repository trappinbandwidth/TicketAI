"""Fill a registered demo Carrier's empty screens with estimated data.

Local/testing only: it refuses to run without the Firestore emulator. Takes a
verified, already-registered Carrier's email and populates the data the portal
would otherwise show as empty during a pilot demo — an FMCSA SMS safety record
(estimated BASIC percentiles), a small roster, subscription pricing, and billing
contact — so every Carrier screen renders with plausible numbers.

The values are clearly synthetic estimates for local review, not real FMCSA or
payment data. Usage:

    FIRESTORE_EMULATOR_HOST=localhost:8080 \
    FIREBASE_AUTH_EMULATOR_HOST=localhost:9099 \
    FIREBASE_PROJECT_ID=rigresolve-local \
    python scripts/seed_demo_carrier.py carrier.pilot@example.com
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

if not os.getenv("FIRESTORE_EMULATOR_HOST"):
    sys.exit("Refusing to seed: FIRESTORE_EMULATOR_HOST is not set (emulator only).")

import firebase_admin
from firebase_admin import auth as fb_auth, firestore

from app.services.firebase_service import _emulator_credential

PROJECT = os.environ.get("FIREBASE_PROJECT_ID", "rigresolve-local")
if not firebase_admin._apps:
    firebase_admin.initialize_app(_emulator_credential(), {"projectId": PROJECT})
db = firestore.client()

NOW = datetime.now(timezone.utc)


def _basic(code, name, pct, threshold, measure, alert=False):
    return {"code": code, "name": name, "percentile": pct,
            "threshold": threshold, "measure": measure, "alert": alert}


def seed(email: str) -> None:
    user = fb_auth.get_user_by_email(email)
    uid = user.uid
    ref = db.collection("carriers").document(uid)
    snap = ref.get()
    if not snap.exists:
        sys.exit(f"{email} ({uid}) is not a registered Carrier yet — register in the app first.")
    profile = snap.to_dict() or {}
    dot = str(profile.get("dot_number") or "").strip()
    company = profile.get("company_name") or "Demo Carrier"
    if not dot:
        sys.exit(f"{email} has no USDOT on file; select an FMCSA record at signup first.")

    # 1. FMCSA SMS safety record, keyed by USDOT (what /fmcsa/safety reads).
    #    Estimated BASIC percentiles (0 best, 100 worst) — synthetic demo data.
    db.collection("carriers").document(dot).set({
        "dot_number": dot,
        "legal_name": company,
        "operating_status": "Active",
        "safety_rating": "Satisfactory",
        "power_units": 42,
        "driver_count": 51,
        "inspection_count": 188,
        "violation_count": 73,
        "crash_count": 4,
        "oos_status": "None",
        "fmcsa_updated_at": NOW,
        "basics": [
            _basic("unsafe_driving", "Unsafe Driving", 63, 65, 1.94),
            _basic("hos", "Hours-of-Service Compliance", 58, 65, 1.71),
            _basic("vehicle_maint", "Vehicle Maintenance", 71, 80, 3.02, alert=False),
            _basic("driver_fitness", "Driver Fitness", 19, 80, 0.34),
            _basic("controlled_subst", "Controlled Substances/Alcohol", 6, 80, 0.0),
            _basic("hazmat", "HM Compliance", None, 80, None),
            _basic("crash", "Crash Indicator", 47, 65, 0.0),
        ],
        "inspections": [
            {"date": "2026-05-18", "level": "Level II", "state": profile.get("state") or "TX", "oos": False},
            {"date": "2026-03-02", "level": "Level I", "state": profile.get("state") or "TX", "oos": True},
        ],
    }, merge=True)

    # 2. Subscription + billing on the Carrier's own profile.
    ref.set({
        "subscription_status": "active",
        "per_driver_rate_cents": 1200,
        "billing_type": "card",
        "billing_contact_name": "Dispatch Office",
        "billing_email": email,
        "billing_phone": "9565550142",
        "billing_city": profile.get("city") or "Pharr",
        "billing_state": profile.get("state") or "TX",
        "payment_method_brand": "Visa",
        "payment_method_last4": "4242",
        "payment_method_status": "active",
        "updated_at": NOW,
    }, merge=True)

    # 3. A small estimated roster so dashboard counts and roster render.
    roster = ref.collection("drivers")
    demo_drivers = [
        ("Marcus", "Ellison", "marcus.ellison@example.com", "9565550111", "TX", "TX1188420"),
        ("Renee", "Ortega", "renee.ortega@example.com", "9565550112", "TX", "TX2093117"),
        ("Darnell", "Boyd", "darnell.boyd@example.com", "9565550113", "TX", "TX7741905"),
        ("Priya", "Nair", "priya.nair@example.com", "9565550114", "OK", "OK4410228"),
    ]
    created = 0
    for first, last, mail, phone, cdl_state, cdl in demo_drivers:
        doc = roster.document()
        doc.set({
            "first_name": first, "last_name": last, "full_name": f"{first} {last}",
            "email": mail, "phone": phone, "cdl_state": cdl_state, "cdl_number": cdl,
            "active": True, "created_at": NOW, "updated_at": NOW,
        })
        created += 1

    print(f"Seeded demo data for {company} (USDOT {dot}, uid {uid}):")
    print(f"  FMCSA safety record with 7 estimated BASIC percentiles")
    print(f"  subscription active @ $12.00/driver, billing contact + Visa •4242")
    print(f"  {created} roster Drivers")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/seed_demo_carrier.py <carrier-email>")
    seed(sys.argv[1])
