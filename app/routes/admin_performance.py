"""
Admin / staff Performance Level routes — Slice 1.

Staff Firebase Bearer token auth for the AM/staff tuning and monitoring surfaces.
The nightly recalculator cron keeps x-api-key auth since Cloud Scheduler invokes
it directly with no per-staff Firebase login.

  GET  /admin/attorneys/{id}/performance   Full detail incl raw_lifetime_win_rate (staff-only)
  POST /admin/attorneys/{id}/nominate-diamond
  GET  /admin/level-config                 Read thresholds
  PUT  /admin/level-config                 Tune thresholds (no deploy needed)
  GET  /admin/stats/performance-levels      Distribution across levels
  POST /admin/attorneys/backfill-levels     One-time backfill of new fields + config seed
  POST /operations/recalculate-levels       Performance Level Recalculator (cron: daily 6am, x-api-key)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.routes._common import require_staff
from app.services import attorney_levels as levels

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-performance"])


def _check_auth(x_api_key: Optional[str]):
    if x_api_key != os.getenv("API_KEY", "cdl-local-dev"):
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# ── GET full attorney performance (staff view) ────────────────────────────────
@router.get("/admin/attorneys/{attorney_id}/performance")
def admin_get_performance(attorney_id: str, authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    snap = db.collection("attorneys").document(attorney_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Attorney not found.")

    a = {**levels.default_level_fields(), **snap.to_dict()}
    # Staff sees the raw lifetime rate too (never shown to the attorney).
    return {
        "attorney_id": attorney_id,
        "name": a.get("full_name") or a.get("Name") or a.get("name"),
        "performance_level": a.get("performance_level"),
        "provisional": a.get("provisional"),
        "experience_tier": a.get("tier"),
        "win_rate": a.get("win_rate"),
        "raw_lifetime_win_rate": a.get("raw_lifetime_win_rate"),  # staff-only
        "cases_completed_lifetime": a.get("cases_completed_lifetime") or 0,
        "cases_won_lifetime": a.get("cases_won_lifetime") or 0,
        "cases_active": a.get("cases_active") or 0,
        "trailing_window_cases": a.get("trailing_window_cases") or 0,
        "trailing_window_wins": a.get("trailing_window_wins") or 0,
        "sla_compliance_rate": a.get("sla_compliance_rate"),
        "no_show_count_trailing": a.get("no_show_count_trailing") or 0,
        "self_sourced_count_lifetime": a.get("self_sourced_count_lifetime") or 0,
        "diamond_nominated_by": a.get("diamond_nominated_by"),
        "diamond_nominated_at": _iso(a.get("diamond_nominated_at")),
        "performance_level_updated_at": _iso(a.get("performance_level_updated_at")),
    }


# ── Diamond nomination ────────────────────────────────────────────────────────
class DiamondNomination(BaseModel):
    nominated_by: str          # admin/AM user id
    note: Optional[str] = None


@router.post("/admin/attorneys/{attorney_id}/nominate-diamond")
def nominate_diamond(
    attorney_id: str,
    body: DiamondNomination,
    authorization: Optional[str] = Header(None),
):
    """Set the AM nomination that Diamond requires alongside its metrics."""
    require_staff(authorization)
    db = _db()
    ref = db.collection("attorneys").document(attorney_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Attorney not found.")

    ref.update({
        "diamond_nominated_by": body.nominated_by,
        "diamond_nominated_at": datetime.now(timezone.utc),
        "diamond_nomination_note": body.note,
    })
    # Re-run this attorney immediately so the nomination can take effect if the
    # numbers already qualify.
    result = levels.recalculate_attorney(db, attorney_id)
    return {"ok": True, "attorney_id": attorney_id, "recalc": result}


# ── Level config (the tuning surface) ─────────────────────────────────────────
@router.get("/admin/level-config")
def get_level_config(authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    return {"config": levels.get_level_config(db)}


class LevelConfigUpdate(BaseModel):
    # Any subset of thresholds for a single level. Only provided fields change.
    min_lifetime_cases: Optional[int] = None
    min_win_rate: Optional[float] = None
    min_sla_compliance: Optional[float] = None
    max_no_shows_trailing: Optional[int] = None
    trailing_window_days: Optional[int] = None
    bid_floor_pct: Optional[float] = None
    quality_discount_pct: Optional[float] = None
    self_sourced_maintenance_min: Optional[int] = None
    requires_nomination: Optional[bool] = None


@router.put("/admin/level-config/{level}")
def update_level_config(
    level: str,
    body: LevelConfigUpdate,
    authorization: Optional[str] = Header(None),
):
    """Tune one level's thresholds without a deploy. Seeds config first if empty."""
    require_staff(authorization)
    if level not in levels.DEFAULT_LEVEL_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown level '{level}'. Valid: {list(levels.DEFAULT_LEVEL_CONFIG)}",
        )
    db = _db()
    levels.seed_level_config(db)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    db.collection("level_config").document(level).set(patch, merge=True)
    logger.warning("[admin_performance] level_config %s updated: %s", level, list(patch))
    return {"ok": True, "level": level, "updated": list(patch)}


# ── Distribution stats ────────────────────────────────────────────────────────
@router.get("/admin/stats/performance-levels")
def performance_level_stats(authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    dist = {lvl: 0 for lvl in levels.ALL_LEVELS}
    provisional = 0
    total = 0
    for doc in db.collection("attorneys").stream():
        d = doc.to_dict()
        total += 1
        lvl = d.get("performance_level") or "bronze"
        dist[lvl] = dist.get(lvl, 0) + 1
        if d.get("provisional"):
            provisional += 1
    return {"total": total, "provisional": provisional, "by_level": dist}


# ── Backfill (one-time / idempotent) ──────────────────────────────────────────
@router.post("/admin/attorneys/backfill-levels")
def backfill_levels(authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    return levels.backfill_attorney_fields(db)


# ── Performance Level Recalculator (cron: daily ~6am, before Court Deadline 8am) ─
@router.post("/operations/recalculate-levels")
def recalculate_levels(
    attorney_id: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """
    Nightly recalculator (§4). Runs the trailing-window + level evaluation for
    every attorney (or just one if ?attorney_id= is given), writes level changes,
    and notifies affected attorneys.
    """
    _check_auth(x_api_key)
    db = _db()
    if attorney_id:
        result = levels.recalculate_attorney(db, attorney_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Attorney not found.")
        return {"run_at": datetime.now(timezone.utc).isoformat(), "single": result}
    summary = levels.recalculate_all(db)
    return {"run_at": datetime.now(timezone.utc).isoformat(), **summary}
