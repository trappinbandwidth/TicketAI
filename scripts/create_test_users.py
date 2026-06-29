"""
Create test Firebase Auth users + Firestore profiles for all three portals.

Run once:
  cd /Users/digitalmercenary/CDL_Defense/AI_Ticket_Scanner/ai-ticket-engine-main
  source .venv/bin/activate
  python3 scripts/create_test_users.py
"""
import os
import sys
from pathlib import Path

# Load env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import firebase_admin
from firebase_admin import auth, credentials, firestore
from datetime import datetime, timezone, timedelta

# Init Firebase with ADC
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"projectId": os.getenv("FIREBASE_PROJECT_ID", "rigresolve")})

db = firestore.client()

USERS = [
    {
        "email": "driver@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Test Driver",
        "role": "driver",
        "portal": "Driver App",
        "firestore_collection": "drivers",
        "firestore_profile": {
            "full_name": "Test Driver",
            "email": "driver@rigresolve.com",
            "phone": "+15555550001",
            "cdl_number": "TX-CDL-123456",
            "cdl_class": "A",
            "cdl_state": "TX",
            "subscription_status": "active",
            "plan": "monthly",
            "subscription_end_date": datetime.now(timezone.utc) + timedelta(days=30),
            "created_at": datetime.now(timezone.utc),
        },
    },
    {
        "email": "attorney@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Test Attorney",
        "role": "attorney",
        "portal": "Attorney Portal",
        "firestore_collection": "attorneys",
        "firestore_profile": {
            "name": "Test Attorney",
            "email": "attorney@rigresolve.com",
            "phone": "+15555550002",
            "bar_number": "TX-BAR-98765",
            "states": ["TX", "FL", "GA"],
            "counties": ["Harris", "Dallas", "Miami-Dade", "Fulton"],
            "win_rate": 0.78,
            "total_tickets": 42,
            "rating": 4.8,
            "active": True,
            "created_at": datetime.now(timezone.utc),
        },
    },
    {
        "email": "carrier@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Test Carrier",
        "role": "carrier",
        "portal": "Carrier Portal",
        "firestore_collection": "carriers",
        "firestore_profile": {
            "company_name": "Test Trucking LLC",
            "email": "carrier@rigresolve.com",
            "phone": "+15555550003",
            "dot_number": "DOT-1234567",
            "fleet_size": 12,
            "state": "TX",
            "active": True,
            "created_at": datetime.now(timezone.utc),
        },
    },
    {
        "email": "admin@rigresolve.com",
        "password": "RigResolve2024!",
        "display_name": "Rig Resolve Admin",
        "role": "admin",
        "portal": "Admin / Reviewer",
        "firestore_collection": "admins",
        "firestore_profile": {
            "name": "Rig Resolve Admin",
            "email": "admin@rigresolve.com",
            "role": "reviewer",
            "created_at": datetime.now(timezone.utc),
        },
    },
]


def create_or_update_user(user: dict) -> str:
    email = user["email"]
    try:
        fb_user = auth.get_user_by_email(email)
        print(f"  EXISTS  {email} (uid={fb_user.uid})")
        # Update password in case it changed
        auth.update_user(fb_user.uid, password=user["password"], display_name=user["display_name"])
        return fb_user.uid
    except auth.UserNotFoundError:
        fb_user = auth.create_user(
            email=email,
            password=user["password"],
            display_name=user["display_name"],
            email_verified=True,
        )
        print(f"  CREATED {email} (uid={fb_user.uid})")
        return fb_user.uid


def write_firestore_profile(uid: str, user: dict):
    collection = user["firestore_collection"]
    profile = {**user["firestore_profile"], "uid": uid}
    db.collection(collection).document(uid).set(profile, merge=True)

    # Drivers also need an entry in the drivers collection keyed by uid
    # so the enrollment verifier can find them
    if user["role"] == "driver":
        db.collection("drivers").document(uid).set(profile, merge=True)

    print(f"  PROFILE → {collection}/{uid}")


print("\n=== Creating Firebase Auth users + Firestore profiles ===\n")
created = []
for user in USERS:
    print(f"[{user['portal']}]")
    try:
        uid = create_or_update_user(user)
        write_firestore_profile(uid, user)
        created.append({"portal": user["portal"], "email": user["email"], "uid": uid})
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

print("=== Done ===\n")
print(f"{'Portal':<20} {'Email':<35} {'UID'}")
print("-" * 90)
for c in created:
    print(f"{c['portal']:<20} {c['email']:<35} {c['uid']}")

print("\nCredentials for all portals:")
print("  Password: RigResolve2024!")
print("  Driver:   driver@rigresolve.com")
print("  Attorney: attorney@rigresolve.com")
print("  Carrier:  carrier@rigresolve.com")
print("  Admin:    admin@rigresolve.com")
