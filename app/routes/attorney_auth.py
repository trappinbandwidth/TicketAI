"""
Attorney auth + onboarding provisioning.

  Public / authed:
    POST /auth/bootstrap            After Google/Email/Phone signup — ensure attorneys/
                                    doc + attorney role claim; report if email/pw attached.
    POST /profile/firm-lookup       Google Places law-firm lookup (authed).
    GET  /firm-lookup               Same, via ?query=.

  Staff (White Glove):
    POST /admin/attorneys/provision Create an attorney account + doc on their behalf,
                                    optionally auto-filling firm info from Google Places.

  Local development uses the Firebase Auth emulator — there are no dev/test-account
  endpoints in this service.
"""
from __future__ import annotations

import logging
import secrets
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.routes._common import get_db, verify_token, require_staff
from app.services import attorney_dashboard as dash
from app.services import attorney_levels as levels
from app.services import places_lookup

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-auth"])


def _seed_attorney_doc(db, uid: str, *, email: str, full_name: Optional[str],
                       tier: str = "senior", extra: Optional[dict] = None,
                       onboarded: bool = False) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    doc = {
        **levels.default_level_fields(),
        **dash.dashboard_field_defaults(),
        "full_name": full_name,
        "email": email,
        "tier": tier,
        "status": "onboarded" if onboarded else "provisioned",
        "application_status": "approved" if onboarded else None,
        "cases_active": 0,
        "created_at": SERVER_TIMESTAMP,
    }
    if onboarded:
        doc["onboarded_at"] = SERVER_TIMESTAMP
    if extra:
        doc.update({k: v for k, v in extra.items() if v is not None})
    db.collection("attorneys").document(uid).set(doc, merge=True)
    return doc


def _ensure_role(uid: str, role: str = "attorney"):
    try:
        user = fb_auth.get_user(uid)
        claims = user.custom_claims or {}
        if claims.get("role") != role:
            fb_auth.set_custom_user_claims(uid, {**claims, "role": role})
    except Exception as exc:
        logger.warning("[attorney_auth] set role failed uid=%s: %s", uid, exc)


# ── Self-bootstrap after client-side signup ──────────────────────────────────
@router.post("/auth/bootstrap")
def bootstrap(authorization: Optional[str] = Header(None)):
    """
    Called right after a client signs up/in (Google, Email/PW, or Phone). Ensures a
    role claim + attorneys/ doc exist, and reports whether an email/password credential
    is attached (so the UI can prompt to add one — every account must have email+pw).
    """
    decoded = verify_token(authorization)
    uid = decoded["uid"]
    db = get_db()
    _ensure_role(uid)

    snap = db.collection("attorneys").document(uid).get()
    created = False
    if not snap.exists:
        _seed_attorney_doc(db, uid, email=decoded.get("email") or "",
                           full_name=decoded.get("name"))
        created = True

    # Which sign-in providers are on this account?
    providers = []
    has_password = False
    try:
        user = fb_auth.get_user(uid)
        providers = [p.provider_id for p in user.provider_data]
        has_password = "password" in providers
    except Exception:
        pass

    return {
        "uid": uid,
        "created": created,
        "email": decoded.get("email"),
        "providers": providers,
        "has_password": has_password,
        "needs_password": not has_password,   # prompt to attach email+pw
    }


# ── Firm lookup (Google Places) ──────────────────────────────────────────────
class FirmLookup(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    query: Optional[str] = None


@router.post("/profile/firm-lookup")
def firm_lookup(body: FirmLookup, authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    query = body.query or places_lookup.build_query(body.name, body.city, body.state)
    if not query:
        raise HTTPException(status_code=400, detail="Provide a firm name/city/state or query.")
    return places_lookup.lookup_firm(query)


@router.get("/firm-lookup")
def firm_lookup_get(query: str, authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    return places_lookup.lookup_firm(query)


# ── White Glove provisioning (staff) ─────────────────────────────────────────
class ProvisionBody(BaseModel):
    email: str
    full_name: str
    tier: str = "senior"
    phone: Optional[str] = None
    bar_number: Optional[str] = None
    bar_state: Optional[str] = None
    states_covered: Optional[list[str]] = None
    counties_covered: Optional[list[str]] = None
    firm_name: Optional[str] = None
    firm_city: Optional[str] = None
    firm_state: Optional[str] = None
    run_firm_lookup: bool = False


@router.post("/admin/attorneys/provision")
def provision_attorney(body: ProvisionBody, authorization: Optional[str] = Header(None)):
    """White Glove — AAM/staff creates an attorney account and fills the profile."""
    require_staff(authorization)
    db = get_db()
    email = body.email.lower().strip()
    temp_password = secrets.token_urlsafe(12)

    # Create (or reuse) the Firebase Auth user with a temp password.
    try:
        try:
            user = fb_auth.get_user_by_email(email)
        except fb_auth.UserNotFoundError:
            user = fb_auth.create_user(email=email, password=temp_password,
                                       display_name=body.full_name)
        uid = user.uid
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Auth provisioning failed: {exc}")
    _ensure_role(uid)

    # Optionally enrich firm fields from Google Places.
    firm_extra: dict = {}
    firm_lookup_result = None
    if body.run_firm_lookup and (body.firm_name or body.firm_city):
        firm_lookup_result = places_lookup.lookup_firm(
            places_lookup.build_query(body.firm_name, body.firm_city, body.firm_state or body.bar_state)
        )
        best = firm_lookup_result.get("best")
        if best:
            firm_extra = {
                "firm_address": best.get("formatted_address"),
                "firm_phone": best.get("phone"),
                "firm_city": best.get("city"),
                "firm_state": best.get("state"),
                "firm_website": best.get("website"),
                "firm_place_id": best.get("place_id"),
            }

    extra = {
        "phone": body.phone,
        "bar_number": body.bar_number,
        "bar_state": (body.bar_state or "").upper() or None,
        "states_covered": [s.upper() for s in (body.states_covered or [])] or None,
        "counties_covered": body.counties_covered or None,
        "firm_name": body.firm_name,
        "firm_city": body.firm_city,
        "firm_state": (body.firm_state or "").upper() or None,
        "provisioned_by": require_staff(authorization)["uid"],
        "provision_method": "white_glove",
        **firm_extra,
    }
    _seed_attorney_doc(db, uid, email=email, full_name=body.full_name, tier=body.tier,
                       extra=extra, onboarded=True)

    reset_link = None
    try:
        reset_link = fb_auth.generate_password_reset_link(email)
    except Exception:
        pass

    logger.warning("[attorney_auth] white-glove provisioned attorney uid=%s email=%s", uid, email)
    return {
        "ok": True, "attorney_id": uid, "email": email,
        "temp_password": temp_password,          # staff can relay; user should reset
        "password_set_link": reset_link,
        "firm_lookup": firm_lookup_result,
    }


