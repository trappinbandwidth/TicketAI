"""
Attorney Dashboard — Profile + Dashboard home (Dashboard spec Slice 1).

Firebase Bearer token auth. Attorney sees only their own data.

  GET  /profile             Own profile + profile_completion_pct
  PUT  /profile             Manual field updates (recomputes completion + gate)
  GET  /dashboard/summary   Single aggregated payload for the Dashboard home
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services import attorney_dashboard as dash
from app.services import attorney_levels as levels
from app.services import case_lifecycle as _cl

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-profile"])


def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _verify_token(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    try:
        return fb_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _load_attorney(db, uid: str) -> dict:
    snap = db.collection("attorneys").document(uid).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Attorney profile not found.")
    # Merge both specs' defaults so the response shape is always complete.
    return {**levels.default_level_fields(), **dash.dashboard_field_defaults(), **snap.to_dict()}


@router.get("/profile")
def get_profile(authorization: Optional[str] = Header(None)):
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    a = _load_attorney(db, uid)

    return {
        "attorney_id": uid,
        "full_name": a.get("full_name") or a.get("Name") or a.get("name"),
        "email": a.get("email") or decoded.get("email"),
        "phone": a.get("phone"),
        "tier": a.get("tier"),                       # Experience Tier (separate axis)
        "performance_level": a.get("performance_level"),
        "bar_number": a.get("bar_number"),
        "bar_state": a.get("bar_state"),
        "bar_verification_status": a.get("bar_verification_status"),
        "states_covered": a.get("states_covered") or [],
        "counties_covered": a.get("counties_covered") or [],
        "firm_name": a.get("firm_name"),
        "firm_address": a.get("firm_address"),
        "firm_phone": a.get("firm_phone"),
        "bio": a.get("bio"),
        "profile_photo_url": a.get("profile_photo_url"),
        "payout_method": a.get("payout_method"),
        "preferred_contact_method": a.get("preferred_contact_method"),
        "profile_completion_pct": a.get("profile_completion_pct") or 0.0,
        "profile_import_source": a.get("profile_import_source"),
        "self_sourced_enabled": bool(a.get("self_sourced_enabled")),
        "application_status": a.get("application_status"),
        "pricing_mode": a.get("pricing_mode") or "case_by_case",
        "flat_rate_schedule": a.get("flat_rate_schedule"),
    }


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    bar_number: Optional[str] = None
    bar_state: Optional[str] = None
    states_covered: Optional[list[str]] = None
    counties_covered: Optional[list[str]] = None
    firm_name: Optional[str] = None
    firm_address: Optional[str] = None
    firm_phone: Optional[str] = None
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = None
    payout_method: Optional[str] = None
    payout_details: Optional[str] = None
    preferred_contact_method: Optional[str] = None
    pricing_mode: Optional[str] = None                 # "flat" | "case_by_case"
    flat_rate_schedule: Optional[dict] = None          # {"default": n, "<category>": n}


@router.put("/profile")
def update_profile(body: ProfileUpdate, authorization: Optional[str] = Header(None)):
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    a = _load_attorney(db, uid)

    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if "states_covered" in patch:
        patch["states_covered"] = [s.upper() for s in patch["states_covered"]]
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")

    # Recompute completion + self_sourced gate against the post-update state.
    merged = {**a, **patch}
    patch.update(dash.recompute_profile_state(db, merged))
    patch["updated_at"] = datetime.now(timezone.utc)

    db.collection("attorneys").document(uid).set(patch, merge=True)
    logger.warning("[attorney_profile] updated uid=%s fields=%s pct=%.2f self_sourced=%s",
                   uid, [k for k in patch if k not in ("updated_at",)],
                   patch["profile_completion_pct"], patch["self_sourced_enabled"])
    return {
        "ok": True,
        "profile_completion_pct": patch["profile_completion_pct"],
        "self_sourced_enabled": patch["self_sourced_enabled"],
    }


@router.get("/dashboard/summary")
def dashboard_summary(authorization: Optional[str] = Header(None)):
    """
    One aggregated payload for the Dashboard home (§4) — case counts, urgent
    items, level/XP snapshot, earnings summary. Built as a single call so the
    frontend doesn't fire five requests on load.
    """
    decoded = _verify_token(authorization)
    uid = decoded["uid"]
    db = _db()
    a = _load_attorney(db, uid)
    now = datetime.now(timezone.utc)

    # ── Active cases assigned to this attorney ────────────────────────────────
    active_statuses = {"Accepted", "New"}
    active_cases: list[dict] = []
    urgent: list[dict] = []
    pending_payout_value = 0.0
    month_closed_value = 0.0

    tickets = db.collection("tickets").where("closed_by_attorney_id", "==", uid).stream()
    for d in tickets:
        data = d.to_dict()
        fee = float(data.get("attorney_fee") or 0)
        if data.get("attorney_status") == "Ticket Closed":
            closed_at = data.get("closed_at")
            if hasattr(closed_at, "timestamp"):
                cdt = datetime.fromtimestamp(closed_at.timestamp(), tz=timezone.utc)
                if cdt.year == now.year and cdt.month == now.month:
                    month_closed_value += fee
            if not data.get("payout_completed"):
                pending_payout_value += fee

    # Cases currently assigned/active (may not yet have closed_by set) — match on
    # attorney_id too, which the assign flow stamps.
    for field in ("attorney_id", "assigned_attorney_id"):
        try:
            q = db.collection("tickets").where(field, "==", uid)
            for d in q.stream():
                data = d.to_dict()
                if data.get("attorney_status") not in active_statuses:
                    continue
                card = {
                    "ticket_id": d.id,
                    "driver_name": _cl.mask_driver_name(data.get("driver_full_name") or data.get("driver_name")),
                    "violation": data.get("violation_category") or "",
                    "state": data.get("ticket_state") or "",
                    "court_date": data.get("court_date") or "",
                    "urgency_level": data.get("urgency_level") or "LOW",
                    "origin": data.get("origin") or "rr_pipeline",
                    "attorney_status": data.get("attorney_status"),
                }
                if not any(c["ticket_id"] == card["ticket_id"] for c in active_cases):
                    active_cases.append(card)
                    if card["urgency_level"] in ("CRITICAL", "HIGH"):
                        urgent.append(card)
        except Exception as exc:
            logger.warning("[dashboard_summary] active-case query on %s failed: %s", field, exc)

    provisional = bool(a.get("provisional"))
    win_rate = a.get("win_rate")

    return {
        "attorney_id": uid,
        "run_at": now.isoformat(),
        # Top strip — urgent action items
        "urgent_items": sorted(
            urgent,
            key=lambda c: {"CRITICAL": 0, "HIGH": 1}.get(c["urgency_level"], 2),
        ),
        "urgent_count": len(urgent),
        # Middle row — performance snapshot (data owned by levels spec)
        "performance": {
            "performance_level": a.get("performance_level"),
            "provisional": provisional,
            "win_rate": None if provisional else win_rate,
            "win_rate_display": "Provisional" if provisional else (
                f"{win_rate:.0%}" if isinstance(win_rate, (int, float)) else "—"
            ),
            "xp_total": a.get("xp_total") or 0,
            "current_streak_days": a.get("current_streak_days") or 0,
            "badges": a.get("badges") or [],
        },
        # Case counts
        "cases": {
            "active_count": len(active_cases),
            "active": active_cases,
            "cases_completed_lifetime": a.get("cases_completed_lifetime") or 0,
        },
        # Bottom row — earnings snapshot
        "earnings": {
            "pending_payout_value": round(pending_payout_value, 2),
            "month_closed_value": round(month_closed_value, 2),
        },
        # Profile / gate state (drives empty states + BYOC unlock)
        "profile": {
            "completion_pct": a.get("profile_completion_pct") or 0.0,
            "self_sourced_enabled": bool(a.get("self_sourced_enabled")),
        },
    }
