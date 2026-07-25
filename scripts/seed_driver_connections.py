"""Seed Driver ↔ Carrier connections so the Pilot flow can be experienced.

Local/testing only: refuses to run without the Firestore emulator. Creates a few
Driver accounts, has each issue a one-time connection code, has the demo Carrier
consume it, and then leaves the relationships in a realistic mix of states:

  * one **active with safety consent** — the Carrier can see consented detail
  * one **active without consent** — connected, but safety data still withheld
  * one **invited** — waiting on the Driver to accept

That mix is the point: it shows that a connection is not consent, and that each
step is a separate, Driver-controlled action.

    FIRESTORE_EMULATOR_HOST=localhost:8080 \
    FIREBASE_AUTH_EMULATOR_HOST=localhost:9099 \
    FIREBASE_PROJECT_ID=rigresolve-local \
    python scripts/seed_driver_connections.py carrier.pilot@example.com
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

if not os.getenv("FIRESTORE_EMULATOR_HOST"):
    sys.exit("Refusing to seed: FIRESTORE_EMULATOR_HOST is not set (emulator only).")

import firebase_admin
from firebase_admin import auth as fb_auth

from app.services.firebase_service import _emulator_credential

PROJECT = os.environ.get("FIREBASE_PROJECT_ID", "rigresolve-local")
AUTH = f"http://{os.environ.get('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')}"
ENGINE = os.environ.get("ENGINE_URL", "http://localhost:8000")
API_KEY = os.environ.get("FIREBASE_API_KEY", "fake-api-key")

if not firebase_admin._apps:
    firebase_admin.initialize_app(_emulator_credential(), {"projectId": PROJECT})


def _post(url: str, body: dict, token: str | None = None) -> dict:
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        return json.load(urllib.request.urlopen(request))
    except urllib.error.HTTPError as error:
        detail = error.read().decode()
        raise SystemExit(f"{url} failed ({error.code}): {detail}")


def _id_token_for(uid: str) -> str:
    """Exchange an admin-minted custom token for an emulator ID token."""
    custom = fb_auth.create_custom_token(uid).decode()
    result = _post(
        f"{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={API_KEY}",
        {"token": custom, "returnSecureToken": True},
    )
    return result["idToken"]


def _driver(uid: str, phone: str) -> str:
    """Create (or reuse) a Driver account carrying the driver role claim."""
    try:
        fb_auth.get_user(uid)
    except fb_auth.UserNotFoundError:
        fb_auth.create_user(uid=uid, phone_number=phone)
    fb_auth.set_custom_user_claims(uid, {"role": "driver"})
    return _id_token_for(uid)


def seed(carrier_email: str) -> None:
    carrier = fb_auth.get_user_by_email(carrier_email)
    carrier_token = _id_token_for(carrier.uid)

    plan = [
        ("seed_driver_wade", "+15125550301", "employee", "accept_and_consent"),
        ("seed_driver_alicia", "+15125550302", "contractor", "accept_only"),
        ("seed_driver_tom", "+15125550303", "owner_operator", "leave_invited"),
    ]

    for uid, phone, relationship_type, outcome in plan:
        driver_token = _driver(uid, phone)

        code = _post(
            f"{ENGINE}/api/v1/driver/profile/carrier-connection-code", {}, driver_token
        )["code"]
        connected = _post(
            f"{ENGINE}/api/v1/carrier/relationships/connect",
            {"code": code, "relationship_type": relationship_type},
            carrier_token,
        )
        relationship_id = connected["relationship"]["id"]

        if outcome == "leave_invited":
            print(f"  {uid}: invited ({relationship_type}) — awaiting Driver response")
            continue

        _post(
            f"{ENGINE}/api/v1/driver/profile/carrier-relationships/{relationship_id}/respond",
            {"accept": True},
            driver_token,
        )
        if outcome == "accept_only":
            print(f"  {uid}: active ({relationship_type}) — no safety consent granted")
            continue

        _post(
            f"{ENGINE}/api/v1/driver/profile/carrier-relationships/{relationship_id}/safety-consent",
            {"disclosure_version": "carrier-safety-pilot-v1"},
            driver_token,
        )
        print(f"  {uid}: active ({relationship_type}) + safety consent granted")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/seed_driver_connections.py <carrier-email>")
    print("Seeding Driver connections:")
    seed(sys.argv[1])
