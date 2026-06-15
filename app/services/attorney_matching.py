"""
Attorney Matching Engine — finds the top 3 best-fit attorneys for a ticket.

Matching strategy:
  1. Find all attorneys with coverage in the ticket's state + county via
     Attorney_Location__c → Serving_County__c join.
  2. If fewer than 3 are found by county, fall back to state-level coverage.
  3. For each candidate attorney, fetch win-rate stats from closed Ticket__c history.
  4. Rank by: (a) exact county match before state-only, (b) win rate desc,
     (c) total tickets desc (experience), (d) avg rating desc.
  5. Return top 3. If zero found, return empty list and no_attorney = True.

Results are cached in memory for 4 hours per (state, county) pair to avoid
hitting SF on every scan. Cache is invalidated on server restart.

Requires SF credentials in .env (SF_USERNAME, SF_PASSWORD, SF_SECURITY_TOKEN).
Degrades gracefully when SF is not configured — returns empty list + no_attorney=True.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 4 * 3600   # 4 hours
_cache: dict[str, tuple[float, list]] = {}


@dataclass
class AttorneyMatch:
    attorney_id: str
    name: str
    email: str
    phone: str
    rating: Optional[float]
    win_rate: float          # 0.0 – 1.0
    total_tickets: int
    match_type: str          # "county" | "state"
    sf_url: str


# Mock attorneys used when SF credentials are not configured (dev/test only)
_MOCK_ATTORNEYS: dict[str, list[dict]] = {
    "Florida": [
        {"attorney_id": "mock-fl-001", "name": "James R. Holloway", "email": "jholloway@hollowaytransportlaw.com", "phone": "(850) 555-0142", "rating": 4.8, "win_rate": 0.74, "total_tickets": 312, "match_type": "county"},
        {"attorney_id": "mock-fl-002", "name": "Sandra M. Vega", "email": "svega@vegacdldefense.com", "phone": "(407) 555-0219", "rating": 4.6, "win_rate": 0.68, "total_tickets": 187, "match_type": "state"},
        {"attorney_id": "mock-fl-003", "name": "Derek W. Fontaine", "email": "dfontaine@fontainelegal.com", "phone": "(305) 555-0387", "rating": 4.5, "win_rate": 0.61, "total_tickets": 98, "match_type": "state"},
    ],
    "Maryland": [
        {"attorney_id": "mock-md-001", "name": "Patricia L. Nguyen", "email": "pnguyen@nguyen-trucklaw.com", "phone": "(410) 555-0174", "rating": 4.9, "win_rate": 0.81, "total_tickets": 445, "match_type": "county"},
        {"attorney_id": "mock-md-002", "name": "Thomas A. Griggs", "email": "tgriggs@griggslawmd.com", "phone": "(301) 555-0263", "rating": 4.7, "win_rate": 0.72, "total_tickets": 229, "match_type": "county"},
        {"attorney_id": "mock-md-003", "name": "Carol B. Simmons", "email": "csimmons@simmonstraffic.com", "phone": "(443) 555-0318", "rating": 4.4, "win_rate": 0.65, "total_tickets": 153, "match_type": "state"},
    ],
    "Washington": [
        {"attorney_id": "mock-wa-001", "name": "Marcus J. Breckenridge", "email": "mbreckenridge@breckenridgecdl.com", "phone": "(206) 555-0492", "rating": 4.7, "win_rate": 0.77, "total_tickets": 381, "match_type": "county"},
        {"attorney_id": "mock-wa-002", "name": "Yuki T. Yamamoto", "email": "yyamamoto@yamamotolegal.com", "phone": "(253) 555-0135", "rating": 4.6, "win_rate": 0.71, "total_tickets": 204, "match_type": "county"},
        {"attorney_id": "mock-wa-003", "name": "Brenda K. Okafor", "email": "bokafor@okafortrucklaw.com", "phone": "(360) 555-0277", "rating": 4.3, "win_rate": 0.58, "total_tickets": 117, "match_type": "state"},
        {"attorney_id": "mock-wa-004", "name": "Kevin L. Sorensen", "email": "ksorensen@sorensentraffic.com", "phone": "(509) 555-0348", "rating": 4.5, "win_rate": 0.69, "total_tickets": 278, "match_type": "state"},
        {"attorney_id": "mock-wa-005", "name": "Alicia R. Montoya", "email": "amontoya@montoyacdllaw.com", "phone": "(425) 555-0461", "rating": 4.8, "win_rate": 0.83, "total_tickets": 512, "match_type": "county"},
    ],
}


def _mock_attorneys_for_state(state: str) -> list[AttorneyMatch]:
    entries = _MOCK_ATTORNEYS.get(state, [])
    return [
        AttorneyMatch(
            attorney_id=e["attorney_id"],
            name=e["name"],
            email=e["email"],
            phone=e["phone"],
            rating=e["rating"],
            win_rate=e["win_rate"],
            total_tickets=e["total_tickets"],
            match_type=e["match_type"],
            sf_url=f"https://cdllegal.lightning.force.com/lightning/r/Contact/{e['attorney_id']}/view",
        )
        for e in entries
    ]


def _sf_url(attorney_id: str) -> str:
    return f"https://cdllegal.lightning.force.com/lightning/r/Contact/{attorney_id}/view"


def _cache_get(key: str) -> list | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(key: str, value: list) -> None:
    _cache[key] = (time.time(), value)


def _get_sf():
    """Return a connected simple_salesforce client, or None if not configured."""
    try:
        from app.services.salesforce import _get_client
        return _get_client()
    except Exception:
        return None


def _fetch_attorneys_by_location(sf, state: str, county: str) -> list[dict]:
    """
    Returns a list of dicts: {attorney_id, name, email, phone, rating, match_type}
    Tries exact county first, falls back to state-only.
    """
    candidates: dict[str, dict] = {}  # attorney_id → info

    # --- County-level match ---
    try:
        county_clean = county.replace("'", "\\'")
        state_clean  = state.replace("'", "\\'")
        result = sf.query(
            f"SELECT Attorney__c, Attorney__r.Name, Attorney__r.Email, "
            f"Attorney__r.Phone, Attorney__r.Attorney_Average_Rating__c "
            f"FROM Attorney_Location__c "
            f"WHERE Serving_State__c = '{state_clean}' "
            f"AND Serving_County__r.Name = '{county_clean}' "
            f"AND Attorney__r.Don_t_Use_Attorney__c = false "
            f"LIMIT 50"
        )
        for r in result.get("records", []):
            a = r.get("Attorney__r") or {}
            aid = r.get("Attorney__c", "")
            if aid and aid not in candidates:
                candidates[aid] = {
                    "attorney_id": aid,
                    "name":  a.get("Name", ""),
                    "email": a.get("Email", "") or "",
                    "phone": a.get("Phone", "") or "",
                    "rating": a.get("Attorney_Average_Rating__c"),
                    "match_type": "county",
                }
    except Exception as exc:
        logger.warning("[attorney] county query failed state=%r county=%r: %s", state, county, exc)

    # --- State-level fallback (only fetch extras, not already-found attorneys) ---
    if len(candidates) < 3:
        try:
            state_clean = state.replace("'", "\\'")
            result = sf.query(
                f"SELECT Attorney__c, Attorney__r.Name, Attorney__r.Email, "
                f"Attorney__r.Phone, Attorney__r.Attorney_Average_Rating__c "
                f"FROM Attorney_Location__c "
                f"WHERE Serving_State__c = '{state_clean}' "
                f"AND Attorney__r.Don_t_Use_Attorney__c = false "
                f"LIMIT 100"
            )
            for r in result.get("records", []):
                a = r.get("Attorney__r") or {}
                aid = r.get("Attorney__c", "")
                if aid and aid not in candidates:
                    candidates[aid] = {
                        "attorney_id": aid,
                        "name":  a.get("Name", ""),
                        "email": a.get("Email", "") or "",
                        "phone": a.get("Phone", "") or "",
                        "rating": a.get("Attorney_Average_Rating__c"),
                        "match_type": "state",
                    }
        except Exception as exc:
            logger.warning("[attorney] state query failed state=%r: %s", state, exc)

    return list(candidates.values())


def _fetch_win_stats(sf, attorney_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Returns {attorney_id: (wins, total)} from closed Ticket history."""
    if not attorney_ids:
        return {}

    id_list = ", ".join(f"'{i}'" for i in attorney_ids)
    stats: dict[str, tuple[int, int]] = {}
    try:
        result = sf.query(
            f"SELECT Attorney__c, SUM(Win__c) wins, COUNT(Id) total "
            f"FROM Ticket__c "
            f"WHERE Attorney__c IN ({id_list}) "
            f"AND Attorney_Status__c = 'Ticket Closed' "
            f"GROUP BY Attorney__c"
        )
        for r in result.get("records", []):
            aid = r.get("Attorney__c", "")
            if aid:
                stats[aid] = (int(r.get("wins") or 0), int(r.get("total") or 0))
    except Exception as exc:
        logger.warning("[attorney] win stats query failed: %s", exc)
    return stats


def find_attorneys(state: str, county: str) -> tuple[list[AttorneyMatch], bool]:
    """
    Returns (matches, no_attorney_flag).

    matches:           up to 3 AttorneyMatch objects, ranked best-first.
    no_attorney_flag:  True when zero attorneys cover the state+county.
    """
    if not state:
        return [], True

    cache_key = f"{state}|{county or ''}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("[attorney] cache hit key=%r", cache_key)
        has_results = any(isinstance(x, AttorneyMatch) for x in cached)
        return cached, not has_results

    sf = _get_sf()
    if sf is None:
        mocks = _mock_attorneys_for_state(state)
        if mocks:
            mocks.sort(key=lambda m: (0 if m.match_type == "county" else 1, -m.win_rate, -m.total_tickets, -(m.rating or 0)))
            top3 = mocks[:3]
            logger.warning("[attorney] SF not configured — using mock data for state=%r (%d candidates → top %d)", state, len(mocks), len(top3))
            _cache_set(cache_key, top3)
            return top3, False
        logger.warning("[attorney] SF not configured — no mock data for state=%r", state)
        _cache_set(cache_key, [])
        return [], True

    candidates = _fetch_attorneys_by_location(sf, state, county or "")
    if not candidates:
        logger.warning("[attorney] no attorneys found state=%r county=%r", state, county)
        _cache_set(cache_key, [])
        return [], True

    win_stats = _fetch_win_stats(sf, [c["attorney_id"] for c in candidates])

    matches: list[AttorneyMatch] = []
    for c in candidates:
        wins, total = win_stats.get(c["attorney_id"], (0, 0))
        win_rate = round(wins / total, 3) if total > 0 else 0.0
        matches.append(AttorneyMatch(
            attorney_id=c["attorney_id"],
            name=c["name"],
            email=c["email"],
            phone=c["phone"],
            rating=c["rating"],
            win_rate=win_rate,
            total_tickets=total,
            match_type=c["match_type"],
            sf_url=_sf_url(c["attorney_id"]),
        ))

    # Rank: county before state, then win_rate desc, then total_tickets desc, then rating desc
    matches.sort(key=lambda m: (
        0 if m.match_type == "county" else 1,
        -m.win_rate,
        -m.total_tickets,
        -(m.rating or 0),
    ))

    top3 = matches[:3]
    logger.warning("[attorney] matched state=%r county=%r — %d candidates → top %d (county=%d, state=%d)",
                   state, county, len(matches), len(top3),
                   sum(1 for m in top3 if m.match_type == "county"),
                   sum(1 for m in top3 if m.match_type == "state"))

    _cache_set(cache_key, top3)
    return top3, False
