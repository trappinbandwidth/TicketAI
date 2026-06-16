"""
Attorney Matching Engine — finds the top 3 best-fit attorneys for a ticket.

Data source: local SQLite `attorneys` table (no Salesforce dependency).

Matching strategy:
  1. Find all attorneys covering the ticket's state + county.
  2. Fall back to state-level coverage if fewer than 3 county matches found.
  3. Rank by: (a) county match before state-only, (b) win_rate desc,
     (c) total_tickets desc, (d) avg_rating desc.
  4. Return top 3. If zero found, return empty list and no_attorney = True.

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


def _fetch_attorneys(state: str, county: str) -> list[AttorneyMatch]:
    """Query local attorneys table. County matches first, then state fallback."""
    candidates: dict[str, dict] = {}

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

    matches = _fetch_attorneys(state, county or "")

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
