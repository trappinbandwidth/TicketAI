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

  Dev only (gated by DEV_AUTH_ENABLED=true AND x-api-key) — OTP bypass + test accounts:
    POST /auth/dev/test-account     Create a ready-to-use test attorney; returns a custom token.
    POST /auth/dev/login            Mint a custom token for any email/uid (skip OTP entirely).
"""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
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


def _custom_token(uid: str) -> Optional[str]:
    """Best-effort — custom-token signing needs a service account (fails on local ADC).
    Primary dev login path is email/password, so a None here is fine."""
    try:
        tok = fb_auth.create_custom_token(uid)
        return tok.decode() if isinstance(tok, (bytes, bytearray)) else str(tok)
    except Exception as exc:
        logger.warning("[attorney_auth] custom token unavailable (needs service account): %s", exc)
        return None


def _dev_guard(x_api_key: Optional[str]):
    """Dev endpoints require the env flag AND the API key — off and locked in prod."""
    if os.getenv("DEV_AUTH_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Dev auth disabled (set DEV_AUTH_ENABLED=true).")
    if x_api_key != os.getenv("API_KEY", "cdl-local-dev"):
        raise HTTPException(status_code=401, detail="Invalid API key.")


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


# ── Dev: test account + OTP-bypass login ─────────────────────────────────────
class TestAccountBody(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = "Test Attorney"
    tier: str = "senior"
    state: Optional[str] = "TX"
    county: Optional[str] = None
    self_sourced_enabled: bool = True


@router.post("/auth/dev/test-account")
def dev_test_account(body: TestAccountBody, x_api_key: Optional[str] = Header(None)):
    """DEV ONLY — create a ready-to-use test attorney and return a custom token."""
    _dev_guard(x_api_key)
    db = get_db()
    email = (body.email or f"test-attorney-{secrets.token_hex(3)}@rigresolve.test").lower()
    password = "test1234"
    try:
        try:
            user = fb_auth.get_user_by_email(email)
        except fb_auth.UserNotFoundError:
            user = fb_auth.create_user(email=email, password=password,
                                       display_name=body.full_name)
        uid = user.uid
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Test account creation failed: {exc}")
    _ensure_role(uid)

    _seed_attorney_doc(
        db, uid, email=email, full_name=body.full_name, tier=body.tier, onboarded=True,
        extra={
            "states_covered": [(body.state or "TX").upper()],
            "counties_covered": [body.county] if body.county else [],
            "self_sourced_enabled": body.self_sourced_enabled,
            "profile_completion_pct": 1.0 if body.self_sourced_enabled else 0.5,
            "firm_name": "Test Defense Firm",
            "bar_number": "TEST-0001",
            "bar_state": (body.state or "TX").upper(),
            "is_test_account": True,
        },
    )
    logger.warning("[attorney_auth] DEV test account uid=%s email=%s", uid, email)
    return {
        "ok": True, "attorney_id": uid, "email": email, "password": password,
        "custom_token": _custom_token(uid),   # frontend: signInWithCustomToken(...)
    }


class SeedBody(BaseModel):
    attorney_email: Optional[str] = None
    attorney_uid: Optional[str] = None


@router.post("/auth/dev/seed-demo")
def dev_seed_demo(body: SeedBody, x_api_key: Optional[str] = Header(None)):
    """
    DEV ONLY — populate a realistic demo set for one attorney so the existing screens
    (First View, My Cases, Wallet) and the AAM console show data. Every record is
    tagged seed=True; POST /auth/dev/clear-seed removes them all.
    """
    _dev_guard(x_api_key)
    db = get_db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    # Resolve the target attorney.
    if body.attorney_uid:
        uid = body.attorney_uid
    elif body.attorney_email:
        try:
            uid = fb_auth.get_user_by_email(body.attorney_email.lower()).uid
        except Exception:
            raise HTTPException(status_code=404, detail="Attorney email not found.")
    else:
        raise HTTPException(status_code=400, detail="Provide attorney_email or attorney_uid.")

    now = datetime.now(timezone.utc)
    def court_in(days: int) -> str:
        return (now + timedelta(days=days)).strftime("%m/%d/%Y")

    SEED = {"seed": True}
    made = {"tickets": 0, "quote_requests": 0, "quotes": 0, "offers": 0,
            "payouts": 0, "attorneys": 0, "document_requests": 0}

    # A couple of "peer" attorneys so quotes/offers have other names.
    peers = [("seed_atty_a", "Dana Reyes"), ("seed_atty_b", "Marcus Cole")]
    for aid, name in peers:
        db.collection("attorneys").document(aid).set({
            **levels.default_level_fields(), **dash.dashboard_field_defaults(),
            "full_name": name, "email": f"{aid}@rigresolve.test", "tier": "senior",
            "status": "onboarded", "states_covered": ["TX"], "counties_covered": ["Harris"],
            "win_rate": 0.72, "performance_level": "gold", "no_show_count_trailing": 0,
            **SEED,
        }, merge=True)
        made["attorneys"] += 1

    def mk_ticket(tid, driver, violation, county, days, status, extra=None):
        doc = {
            "driver_full_name": driver, "driver_name": driver,
            "violation_category": violation, "violation_description": violation,
            "ticket_state": "TX", "region": "TX", "ticket_county": county,
            "court_date": court_in(days), "attorney_status": status,
            "citation_number": f"TX-2026-{tid[-4:].upper()}",
            "urgency_level": "CRITICAL" if days <= 7 else "HIGH" if days <= 21 else "STANDARD",
            "created_at": SERVER_TIMESTAMP, "last_modified_date": SERVER_TIMESTAMP,
            **SEED,
        }
        if extra:
            doc.update(extra)
        db.collection("tickets").document(tid).set(doc, merge=True)
        made["tickets"] += 1

    # ── My Cases: 3 active assigned to this attorney ─────────────────────────
    mk_ticket("seed_tkt_active1", "John Martinez", "Speeding 15+", "Harris", 12, "Accepted",
              {"assigned_attorney_id": uid, "attorney_id": uid})
    mk_ticket("seed_tkt_active2", "Sarah Chen", "Equipment / Maintenance", "Dallas", 18, "Active",
              {"assigned_attorney_id": uid})
    mk_ticket("seed_tkt_active3", "Mike Johnson", "Hours of Service (ELD)", "Tarrant", 25, "Active",
              {"assigned_attorney_id": uid})

    # ── Wallet: 2 Outcome-Logged (available balance) + history ───────────────
    mk_ticket("seed_tkt_paidready1", "Ella Brooks", "Following Too Close", "Harris", -5, "Outcome Logged",
              {"assigned_attorney_id": uid, "attorney_fee": 650, "outcome": "dismissed",
               "outcome_logged_at": SERVER_TIMESTAMP})
    mk_ticket("seed_tkt_paidready2", "Leo Park", "Lane Violation", "Bexar", -9, "Outcome Logged",
              {"assigned_attorney_id": uid, "attorney_fee": 425, "outcome": "reduced",
               "outcome_logged_at": SERVER_TIMESTAMP})
    db.collection("payout_requests").document("seed_pr_paid").set({
        "attorney_id": uid, "ticket_ids": ["seed_tkt_hist1"], "total_amount": 275.0,
        "status": "paid", "payout_method": "Zelle", "requested_at": SERVER_TIMESTAMP,
        "paid_at": SERVER_TIMESTAMP, **SEED,
    })
    made["payouts"] += 1

    # ── First View: 2 open quote requests inviting this attorney ─────────────
    for i, (tid, viol, county, days) in enumerate([
        ("seed_tkt_quote1", "Reckless Driving", "Harris", 9),
        ("seed_tkt_quote2", "Speeding 1-14", "Montgomery", 30),
    ]):
        mk_ticket(tid, "Prospective Client", viol, county, days, "Quote Requested")
        rid = f"seed_qr_{i}"
        db.collection("case_quote_requests").document(rid).set({
            "ticket_id": tid, "requested_by": {"type": "staff", "id": "seed"},
            "requested_at": SERVER_TIMESTAMP, "attorneys_notified": [uid, "seed_atty_a"],
            "quote_window_closes_at": now + timedelta(days=3), "status": "open", **SEED,
        })
        db.collection("tickets").document(tid).update({"quote_request_id": rid})
        made["quote_requests"] += 1

    # ── First View: 1 pending assignment offer to this attorney ──────────────
    mk_ticket("seed_tkt_offer1", "Priya Nair", "Speeding 15+", "Harris", 6, "Assignment Offered")
    db.collection("case_assignment_offers").document("seed_offer_1").set({
        "ticket_id": "seed_tkt_offer1", "attorney_id": uid,
        "broadcast_group_id": "seed_bg_1", "offered_at": SERVER_TIMESTAMP,
        "response_deadline": now + timedelta(days=1), "status": "pending",
        "responded_at": None, "decline_reason_code": None, **SEED,
    })
    made["offers"] += 1

    # ── AAM console: a quote request WITH quotes to review ───────────────────
    mk_ticket("seed_tkt_aam", "Carlos Diaz", "Alcohol / Drug (DUI)", "Harris", 14, "Quotes Under Review")
    db.collection("case_quote_requests").document("seed_qr_aam").set({
        "ticket_id": "seed_tkt_aam", "requested_by": {"type": "staff", "id": "seed"},
        "requested_at": SERVER_TIMESTAMP, "attorneys_notified": [uid, "seed_atty_a", "seed_atty_b"],
        "quote_window_closes_at": now + timedelta(days=2), "status": "open", **SEED,
    })
    db.collection("tickets").document("seed_tkt_aam").update({"quote_request_id": "seed_qr_aam"})
    made["quote_requests"] += 1
    for j, (aid, name, amt, note) in enumerate([
        (uid, "You", 1200, "Handled 3 similar DUIs in Harris this year."),
        ("seed_atty_a", "Dana Reyes", 1400, "Available, no local court history."),
        ("seed_atty_b", "Marcus Cole", 1100, "Aggressive on DUI; knows the ADA."),
    ]):
        db.collection("case_quotes").document(f"seed_q_{j}").set({
            "request_id": "seed_qr_aam", "ticket_id": "seed_tkt_aam", "attorney_id": aid,
            "attorney_name": name, "quote_amount": amt,
            "fee_no_trial": amt, "fee_trial": round(amt * 1.4),
            "quote_type": "case_reviewed",
            "notes": note, "submitted_at": SERVER_TIMESTAMP, "status": "submitted", **SEED,
        })
        made["quotes"] += 1
    # Judge-relationship note (staff-only) for the AAM screen
    db.collection("attorney_judge_relationships").document("seed_jr_1").set({
        "attorney_id": "seed_atty_b", "county": "Harris", "judge_name": "Hon. R. Alvarez",
        "relationship_notes": "Lenient on first-offense; responds well to early plea.",
        "updated_by": "seed", "updated_at": SERVER_TIMESTAMP, **SEED,
    })
    db.collection("tickets").document("seed_tkt_aam").update(
        {"quote_summary": {"quote_count": 3, "low": 1100, "high": 1400}})

    logger.warning("[attorney_auth] DEV seeded demo for attorney=%s: %s", uid, made)
    return {"ok": True, "attorney_id": uid, "seeded": made,
            "note": "All records tagged seed=true. Clear with POST /auth/dev/clear-seed."}


@router.post("/auth/dev/clear-seed")
def dev_clear_seed(x_api_key: Optional[str] = Header(None)):
    """DEV ONLY — delete every record tagged seed=true across demo collections."""
    _dev_guard(x_api_key)
    db = get_db()
    collections = ["tickets", "attorneys", "case_quote_requests", "case_quotes",
                   "case_assignment_offers", "payout_requests", "document_requests",
                   "attorney_judge_relationships"]
    deleted = {}
    for coll in collections:
        n = 0
        for d in db.collection(coll).where("seed", "==", True).stream():
            d.reference.delete()
            n += 1
        if n:
            deleted[coll] = n
    return {"ok": True, "deleted": deleted}


class DevLoginBody(BaseModel):
    email: Optional[str] = None
    uid: Optional[str] = None


@router.post("/auth/dev/login")
def dev_login(body: DevLoginBody, x_api_key: Optional[str] = Header(None)):
    """
    DEV ONLY — OTP bypass. Resets the account's password to a known dev value and
    returns it so the client can signInWithEmailAndPassword (no SMS, no service-account
    signing needed). Also returns a custom token when a service account is available.
    """
    _dev_guard(x_api_key)
    if not body.email and not body.uid:
        raise HTTPException(status_code=400, detail="Provide email or uid.")
    try:
        user = fb_auth.get_user(body.uid) if body.uid else fb_auth.get_user_by_email(body.email.lower())
    except fb_auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="No such user.")
    password = "devlogin-" + secrets.token_hex(3)
    try:
        fb_auth.update_user(user.uid, password=password)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Password reset failed: {exc}")
    return {"ok": True, "uid": user.uid, "email": user.email,
            "password": password, "custom_token": _custom_token(user.uid)}
