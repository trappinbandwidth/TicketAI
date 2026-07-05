"""
Attorney-facing Performance Level routes — Slice 1.

Firebase Bearer token auth (same pattern as attorney_bids.py). An attorney only
ever sees their OWN performance — never another attorney's numbers or identity.

  GET /performance          Own level, trailing stats, XP, streak, badges
  GET /performance/history  Own attorney_level_changes audit log
"""
from __future__ import annotations

import logging
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException

from app.services import attorney_levels as levels

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-performance"])


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


@router.get("/performance")
def get_my_performance(authorization: Optional[str] = Header(None)):
    """The logged-in attorney's own performance summary."""
    decoded = _verify_token(authorization)
    attorney_uid = decoded["uid"]
    db = _db()

    snap = db.collection("attorneys").document(attorney_uid).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Attorney profile not found.")

    a = {**levels.default_level_fields(), **snap.to_dict()}
    config = levels.get_level_config(db)
    provisional = bool(a.get("provisional"))

    # While provisional, the UI shows "Provisional", never a raw percentage (§3.1).
    win_rate = a.get("win_rate")
    win_rate_display = "Provisional" if provisional else (
        f"{win_rate:.0%}" if isinstance(win_rate, (int, float)) else "—"
    )

    # "Why" breakdown — what the next level up requires (transparency).
    next_level = _next_level(a.get("performance_level") or "bronze")
    next_requirements = None
    if next_level:
        cfg = config[next_level]
        next_requirements = {
            "level": next_level,
            "min_lifetime_cases": cfg["min_lifetime_cases"],
            "min_win_rate": cfg["min_win_rate"],
            "cases_to_go": max(0, cfg["min_lifetime_cases"] - (a.get("cases_completed_lifetime") or 0)),
        }

    return {
        "attorney_id": attorney_uid,
        "performance_level": a.get("performance_level"),
        "provisional": provisional,
        "experience_tier": a.get("tier"),   # the SEPARATE axis, surfaced read-only
        "win_rate": None if provisional else win_rate,
        "win_rate_display": win_rate_display,
        "cases_completed_lifetime": a.get("cases_completed_lifetime") or 0,
        "cases_won_lifetime": a.get("cases_won_lifetime") or 0,
        "cases_active": a.get("cases_active") or 0,
        "trailing_window_cases": a.get("trailing_window_cases") or 0,
        "sla_compliance_rate": a.get("sla_compliance_rate"),
        "no_show_count_trailing": a.get("no_show_count_trailing") or 0,
        # Slice 4 fields (defaulted; not yet earned)
        "xp_total": a.get("xp_total") or 0,
        "current_streak_days": a.get("current_streak_days") or 0,
        "badges": a.get("badges") or [],
        "next_level": next_requirements,
    }


@router.get("/performance/history")
def get_my_level_history(
    limit: int = 25,
    authorization: Optional[str] = Header(None),
):
    """The attorney's own promotion/demotion history."""
    decoded = _verify_token(authorization)
    attorney_uid = decoded["uid"]
    db = _db()

    docs = (
        db.collection("attorney_level_changes")
        .where("attorney_id", "==", attorney_uid)
        .limit(limit)
        .stream()
    )
    changes = []
    for d in docs:
        data = d.to_dict()
        changes.append({
            "change_id": d.id,
            "from_level": data.get("from_level"),
            "to_level": data.get("to_level"),
            "reason": data.get("reason"),
            "triggered_at": _iso(data.get("triggered_at")),
        })
    changes.sort(key=lambda c: c.get("triggered_at") or "", reverse=True)
    return {"changes": changes, "count": len(changes)}


def _next_level(current: str) -> Optional[str]:
    order = levels.ALL_LEVELS
    idx = order.index(current) if current in order else 0
    return order[idx + 1] if idx + 1 < len(order) else None
