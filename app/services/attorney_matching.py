"""
Attorney Matching Engine — finds the top 3 best-fit attorneys for a ticket.

Data sources (in priority order):
  1. Firestore `attorneys/` collection — real onboarded attorney profiles
  2. Local SQLite `attorneys` table — seeded fallback when Firestore is empty

Matching strategy:
  1. Find all attorneys covering the ticket's state (licensed_states array_contains).
  2. Prefer county-level match (ticket county in attorney's counties list).
  3. Fall back to state-only if fewer than 3 county matches found.
  4. Rank by: (a) county match before state-only, (b) win_rate desc.
  5. Return top 3. If zero found, return empty list and no_attorney = True.

Results are cached in memory for 4 hours per (state, county) pair.
Cache is cleared on server restart or via invalidate_cache().
"""
from __future__ import annotations
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

from app.services.queue_store import DB_PATH

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 4 * 3600
_cache: dict[str, tuple[float, list]] = {}


@dataclass
class AttorneyMatch:
    attorney_id: str
    name: str
    email: str
    phone: str
    rating: Optional[float]
    win_rate: float
    total_tickets: int
    match_type: str   # "county" | "state"


def _cache_get(key: str) -> list | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(key: str, value: list) -> None:
    _cache[key] = (time.time(), value)


def invalidate_cache() -> None:
    _cache.clear()


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_attorneys_firestore(state: str, county: str) -> list[AttorneyMatch] | None:
    """Query Firestore attorneys/ collection. Returns None if Firestore unavailable."""
    try:
        import firebase_admin
        from firebase_admin import firestore as admin_firestore

        if not firebase_admin._apps:
            return None

        db = admin_firestore.client()
        query = (
            db.collection("attorneys")
            .where("onboarding_complete", "==", True)
            .where("licensed_states", "array_contains", state)
        )
        docs = query.stream()
        results: list[AttorneyMatch] = []
        for doc in docs:
            d = doc.to_dict()
            name = f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or d.get('firm_name', '')
            counties: list = d.get("counties") or []
            match_type = "county" if (county and county.lower() in [c.lower() for c in counties]) else "state"
            results.append(AttorneyMatch(
                attorney_id=doc.id,
                name=name,
                email=d.get("email", ""),
                phone=d.get("phone", "") or d.get("firm_phone", ""),
                rating=None,
                win_rate=0.0,
                total_tickets=0,
                match_type=match_type,
            ))
        return results
    except Exception as exc:
        logger.warning("[attorney] Firestore fetch failed: %s", exc)
        return None


def _fetch_attorneys(state: str, county: str) -> list[AttorneyMatch]:
    """Query local attorneys table. County matches first, then state fallback."""
    candidates: dict[str, dict] = {}

    try:
        with _db() as conn:
            # County-level match
            if county:
                rows = conn.execute(
                    """SELECT id, name, email, phone, rating, win_rate, total_tickets
                       FROM attorneys
                       WHERE state = ? AND (county = ? OR county = '')
                       AND active = 1
                       ORDER BY county DESC LIMIT 50""",
                    (state, county),
                ).fetchall()
                for r in rows:
                    row = dict(r)
                    match_type = "county" if row.get("county") == county else "state"
                    if row["id"] not in candidates:
                        candidates[row["id"]] = {**row, "match_type": match_type}

            # State-level fallback
            if len(candidates) < 3:
                rows = conn.execute(
                    """SELECT id, name, email, phone, rating, win_rate, total_tickets
                       FROM attorneys
                       WHERE state = ? AND active = 1
                       LIMIT 100""",
                    (state,),
                ).fetchall()
                for r in rows:
                    row = dict(r)
                    if row["id"] not in candidates:
                        candidates[row["id"]] = {**row, "match_type": "state"}

    except sqlite3.OperationalError as exc:
        logger.warning("[attorney] DB not ready (%s) — returning no_attorney for state=%r county=%r", exc, state, county)
        return []

    return [
        AttorneyMatch(
            attorney_id=r["id"],
            name=r["name"],
            email=r["email"] or "",
            phone=r["phone"] or "",
            rating=r["rating"],
            win_rate=r["win_rate"] or 0.0,
            total_tickets=r["total_tickets"] or 0,
            match_type=r["match_type"],
        )
        for r in candidates.values()
    ]


def find_attorneys(state: str, county: str) -> tuple[list[AttorneyMatch], bool]:
    """
    Returns (matches, no_attorney_flag).
    matches:          up to 3 AttorneyMatch objects, ranked best-first.
    no_attorney_flag: True when zero attorneys cover the state+county.
    """
    if not state:
        return [], True

    cache_key = f"{state}|{county or ''}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached, len(cached) == 0

    # Try Firestore first (real attorney profiles); fall back to SQLite seed data
    fs_matches = _fetch_attorneys_firestore(state, county or "")
    matches = fs_matches if fs_matches else _fetch_attorneys(state, county or "")
    if fs_matches is not None and not fs_matches:
        # Firestore available but no attorneys in this region — also check SQLite seed
        sqlite_matches = _fetch_attorneys(state, county or "")
        matches = sqlite_matches

    if not matches:
        logger.warning("[attorney] no attorneys found state=%r county=%r", state, county)
        _cache_set(cache_key, [])
        return [], True

    matches.sort(key=lambda m: (
        0 if m.match_type == "county" else 1,
        -m.win_rate,
        -m.total_tickets,
        -(m.rating or 0),
    ))

    top3 = matches[:3]
    logger.warning("[attorney] matched state=%r county=%r — %d candidates → top %d",
                   state, county, len(matches), len(top3))

    _cache_set(cache_key, top3)
    return top3, False
