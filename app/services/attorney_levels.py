"""
Attorney Performance Level system — Slice 1 (Foundation).

Companion to the engineering spec at
Specs/Attorney_Levels/attorney_levels_engineering_spec.md (v1) and the design doc
attorney_levels.md (v0.3).

Two SEPARATE axes — do not collapse them:
  • Experience Tier  → existing `tier` field (senior|junior|law_student), set at
                       onboarding from credentials. This module never touches it.
  • Performance Level → new `performance_level` field (bronze..diamond), earned
                       entirely from platform behavior. Everything here.

Slice 1 delivers: schema fields, lifetime case counting, provisional period,
smoothed/trailing win-rate calc, top-down level evaluation, audit log, and the
nightly recalculator. No bidding, no auto-privileges, no cap scaling (those are
Slice 2/3).

Every threshold lives in Firestore `level_config/{level}` — never hardcode a gate.
The constants below are the *seed* values only, written once if config is missing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Level ladder ──────────────────────────────────────────────────────────────
# Evaluated top-down so an attorney lands at the HIGHEST level they qualify for.
LEVELS_HIGH_TO_LOW = ["diamond", "platinum", "gold", "silver"]
ALL_LEVELS = ["bronze", "silver", "gold", "platinum", "diamond"]
ENTRY_LEVEL = "bronze"

# ── Bayesian smoothing prior (§3.1) ───────────────────────────────────────────
# 3/4 = a 75% "virtual" starting record shared by everyone entering scored status.
# Its influence shrinks automatically as real case volume grows.
PRIOR_WINS = 3
PRIOR_CASES = 4

# Trailing window minimums (§3.2): score on the WIDER of N days or M decided cases.
TRAILING_MIN_CASES = 30

# A "win" = any resolution better than a guilty conviction (product decision,
# 2026-07-01): dismissed, points/fine reduced (the engine collapses both into the
# single "reduced" outcome), or an outright win. "lost" (guilty) is the only loss.
# "transferred" is not a merits decision — excluded from the win-rate denominator
# entirely so it neither helps nor hurts the rate.
WIN_OUTCOMES = {"won", "dismissed", "reduced"}
LOSS_OUTCOMES = {"lost"}
DECIDED_OUTCOMES = WIN_OUTCOMES | LOSS_OUTCOMES   # transferred deliberately excluded
CLOSED_STATUS = "Ticket Closed"

# ── Seed config (§2.6) — placeholders pending real outcome data ───────────────
# Written to level_config/{level} only if that doc does not already exist.
DEFAULT_LEVEL_CONFIG: dict[str, dict] = {
    "silver": {
        "level": "silver",
        "min_lifetime_cases": 10,
        "min_win_rate": 0.60,
        "min_sla_compliance": 0.90,
        "max_no_shows_trailing": 9999,   # no no-show floor below Gold
        "trailing_window_days": 90,
        "bid_floor_pct": 0.55,           # Slice 3
        "quality_discount_pct": 0.00,    # Slice 3
        "self_sourced_maintenance_min": 0,
        "requires_nomination": False,
    },
    "gold": {
        "level": "gold",
        "min_lifetime_cases": 25,
        "min_win_rate": 0.70,
        "min_sla_compliance": 0.90,
        "max_no_shows_trailing": 0,      # 0 no-shows trailing 90 days
        "trailing_window_days": 90,
        "bid_floor_pct": 0.60,
        "quality_discount_pct": 0.05,
        "self_sourced_maintenance_min": 0,
        "requires_nomination": False,
    },
    "platinum": {
        "level": "platinum",
        "min_lifetime_cases": 50,
        "min_win_rate": 0.85,
        "min_sla_compliance": 0.95,
        "max_no_shows_trailing": 0,      # 0 no-shows trailing 180 days
        "trailing_window_days": 180,
        "bid_floor_pct": None,           # bypasses bid pool
        "quality_discount_pct": None,
        "self_sourced_maintenance_min": 1,
        "requires_nomination": False,
    },
    "diamond": {
        "level": "diamond",
        "min_lifetime_cases": 100,
        "min_win_rate": 0.90,
        "min_sla_compliance": 0.95,
        "max_no_shows_trailing": 0,
        "trailing_window_days": 180,
        "bid_floor_pct": None,
        "quality_discount_pct": None,
        "self_sourced_maintenance_min": 3,
        "requires_nomination": True,     # metrics AND an account-manager nomination
    },
}

# The provisional window ends at Silver's lifetime-case threshold.
def _provisional_case_count(config: dict) -> int:
    return int(config.get("silver", {}).get("min_lifetime_cases", 10))

# ── New attorney fields with defaults (§2.1) — used for backfill ──────────────
def default_level_fields() -> dict:
    """Default values for every field this system adds to attorneys/{id}."""
    return {
        "performance_level": ENTRY_LEVEL,
        "provisional": True,
        "cases_completed_lifetime": 0,
        "cases_won_lifetime": 0,
        "win_rate": None,                    # smoothed trailing (redefined per §2.1)
        "raw_lifetime_win_rate": None,       # admin/debug only, never gates
        "trailing_window_cases": 0,
        "trailing_window_wins": 0,
        "sla_compliance_rate": None,
        "no_show_count_trailing": 0,
        "activity_log_compliance_rate": None,
        "self_sourced_count_trailing_30d": 0,
        "self_sourced_count_lifetime": 0,
        # Slice 4 gamification — defaulted now so the API contract is stable
        "xp_total": 0,
        "current_streak_days": 0,
        "streak_freeze_used_this_month": False,
        "badges": [],
        # Diamond nomination
        "diamond_nominated_by": None,
        "diamond_nominated_at": None,
    }


# ── Firestore helpers ─────────────────────────────────────────────────────────
def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    return _firestore_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_level_config(db, seed_if_missing: bool = True) -> dict[str, dict]:
    """
    Read level_config/{level} into a dict keyed by level name.
    Seeds the collection with DEFAULT_LEVEL_CONFIG the first time if empty.
    """
    config: dict[str, dict] = {}
    for doc in db.collection("level_config").stream():
        config[doc.id] = doc.to_dict()

    if not config and seed_if_missing:
        seed_level_config(db)
        return {k: dict(v) for k, v in DEFAULT_LEVEL_CONFIG.items()}

    # Fill any missing level with its default so evaluation never KeyErrors.
    for level, default in DEFAULT_LEVEL_CONFIG.items():
        config.setdefault(level, dict(default))
    return config


def seed_level_config(db) -> list[str]:
    """Write default thresholds for any level_config doc that doesn't exist yet."""
    written = []
    for level, cfg in DEFAULT_LEVEL_CONFIG.items():
        ref = db.collection("level_config").document(level)
        if not ref.get().exists:
            ref.set(cfg)
            written.append(level)
    if written:
        logger.warning("[attorney_levels] seeded level_config: %s", written)
    return written


# ── §3.1 Smoothed win rate ────────────────────────────────────────────────────
def smoothed_win_rate(wins: int, cases: int) -> float:
    """Bayesian-smoothed win rate. Never gate a decision on raw wins/cases."""
    return (wins + PRIOR_WINS) / (cases + PRIOR_CASES)


# ── §3.2 Rolling trailing window ──────────────────────────────────────────────
def _get_closed_cases(db, attorney_id: str) -> list[dict]:
    """
    All of an attorney's closed cases, newest first.

    Source of truth is the tickets/ collection (closed via
    operations.record-outcome), not a subcollection — each closed ticket carries
    `closed_by_attorney_id`, `outcome`, and `closed_at`. Filtered/sorted in Python
    to avoid requiring a composite index at this scale.
    """
    docs = (
        db.collection("tickets")
        .where("closed_by_attorney_id", "==", attorney_id)
        .stream()
    )
    cases = []
    for d in docs:
        data = d.to_dict()
        if data.get("attorney_status") != CLOSED_STATUS:
            continue
        cases.append({
            "ticket_id": d.id,
            "outcome": data.get("outcome"),
            "closed_at": data.get("closed_at"),
        })

    def _key(c):
        ts = c.get("closed_at")
        return ts if hasattr(ts, "timestamp") else _now()

    cases.sort(key=_key, reverse=True)
    return cases


def compute_trailing_window(
    db, attorney_id: str, window_days: int, min_cases: int = TRAILING_MIN_CASES
) -> tuple[float, int, int]:
    """
    Return (smoothed_rate, window_cases, window_wins) over the wider of
    `window_days` or `min_cases` decided cases (§3.2).
    """
    all_cases = _get_closed_cases(db, attorney_id)
    cutoff = _now() - timedelta(days=window_days)

    def _in_window(c) -> bool:
        ts = c.get("closed_at")
        if not hasattr(ts, "timestamp"):
            return True  # undated closed case counts rather than silently dropping
        dt = ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff

    windowed = [c for c in all_cases if _in_window(c)]
    if len(windowed) < min_cases:
        windowed = all_cases[:min_cases]  # widen by count instead of by time

    # Only decided cases (win or loss) count toward the rate — transferred cases
    # are work done but not a merits result, so they don't dilute the denominator.
    decided = [c for c in windowed if c.get("outcome") in DECIDED_OUTCOMES]
    wins = sum(1 for c in decided if c.get("outcome") in WIN_OUTCOMES)
    return smoothed_win_rate(wins, len(decided)), len(decided), wins


# ── §3.3 Level evaluation (promotion/demotion) ────────────────────────────────
def evaluate_level(attorney: dict, config: dict[str, dict]) -> str:
    """
    Highest level the attorney currently qualifies for, checked top-down.
    Missing SLA/no-show data is treated as non-blocking in Slice 1 (those event
    sources land in Slice 2) — win-rate + lifetime volume drive leveling for now.
    """
    lifetime = attorney.get("cases_completed_lifetime") or 0
    win_rate = attorney.get("win_rate")
    sla = attorney.get("sla_compliance_rate")
    no_shows = attorney.get("no_show_count_trailing") or 0

    for level in LEVELS_HIGH_TO_LOW:
        cfg = config[level]
        if lifetime < cfg["min_lifetime_cases"]:
            continue
        if win_rate is None or win_rate < cfg["min_win_rate"]:
            continue
        # SLA data may not exist yet — only block if we actually have a rate.
        if sla is not None and sla < cfg.get("min_sla_compliance", 0):
            continue
        if no_shows > cfg.get("max_no_shows_trailing", 9999):
            continue
        if level == "diamond" and not attorney.get("diamond_nominated_by"):
            continue
        return level
    return ENTRY_LEVEL


def _demotion_reason(attorney: dict, to_level: str, config: dict) -> str:
    """Human-readable reason quoting the actual metric (transparency, §3.3)."""
    win_rate = attorney.get("win_rate")
    lifetime = attorney.get("cases_completed_lifetime") or 0
    # Find the first gate the attorney fails for the next level up from to_level.
    idx = ALL_LEVELS.index(to_level)
    next_up = ALL_LEVELS[idx + 1] if idx + 1 < len(ALL_LEVELS) else None
    if next_up:
        cfg = config[next_up]
        if lifetime < cfg["min_lifetime_cases"]:
            return (f"{lifetime} lifetime cases — {next_up.title()} requires "
                    f"{cfg['min_lifetime_cases']}.")
        if win_rate is not None and win_rate < cfg["min_win_rate"]:
            return (f"Trailing win rate {win_rate:.0%} — {next_up.title()} requires "
                    f"{cfg['min_win_rate']:.0%}.")
    return f"Now at {to_level.title()}."


# ── Recalculator (§4 Performance Level Recalculator) ──────────────────────────
def recalculate_attorney(db, attorney_id: str) -> Optional[dict]:
    """
    Recompute one attorney's trailing window + performance level, write changes,
    append an audit log entry on any level change, and notify the attorney.
    Returns a summary dict, or None if the attorney doc doesn't exist.
    """
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    ref = db.collection("attorneys").document(attorney_id)
    snap = ref.get()
    if not snap.exists:
        return None

    attorney = {**default_level_fields(), **snap.to_dict()}
    config = get_level_config(db)
    provisional_cutoff = _provisional_case_count(config)

    lifetime = attorney.get("cases_completed_lifetime") or 0
    won = attorney.get("cases_won_lifetime") or 0

    update: dict = {}
    # Raw lifetime rate — admin visibility only, never gates.
    update["raw_lifetime_win_rate"] = (won / lifetime) if lifetime else None

    provisional = lifetime < provisional_cutoff
    update["provisional"] = provisional

    if provisional:
        # §3.1 — not scored while provisional; stays bronze regardless of early luck.
        # win_rate still populated (prior-dominated) so Team Quest's ORDER BY
        # win_rate DESC keeps working; the API renders "Provisional" for the UI.
        rate, wcases, wwins = compute_trailing_window(
            db, attorney_id, config["silver"]["trailing_window_days"]
        )
        update.update({
            "win_rate": rate,
            "trailing_window_cases": wcases,
            "trailing_window_wins": wwins,
        })
        new_level = ENTRY_LEVEL
    else:
        # Use the widest trailing window across levels so the number is stable
        # regardless of which level we're testing against.
        window_days = max(c["trailing_window_days"] for c in config.values())
        rate, wcases, wwins = compute_trailing_window(db, attorney_id, window_days)
        attorney["win_rate"] = rate
        update.update({
            "win_rate": rate,
            "trailing_window_cases": wcases,
            "trailing_window_wins": wwins,
        })
        new_level = evaluate_level(attorney, config)

    old_level = attorney.get("performance_level") or ENTRY_LEVEL
    level_changed = new_level != old_level

    update["performance_level"] = new_level
    if level_changed:
        update["performance_level_updated_at"] = SERVER_TIMESTAMP

    ref.update(update)

    if level_changed:
        direction = (
            "promoted"
            if ALL_LEVELS.index(new_level) > ALL_LEVELS.index(old_level)
            else "demoted"
        )
        reason = _demotion_reason({**attorney, **update}, new_level, config)
        _write_level_change(db, attorney_id, old_level, new_level, reason)
        _notify_attorney_level_change(db, attorney_id, old_level, new_level, direction, reason)
        logger.warning(
            "[attorney_levels] attorney=%s %s %s→%s (%s)",
            attorney_id, direction, old_level, new_level, reason,
        )

    return {
        "attorney_id": attorney_id,
        "performance_level": new_level,
        "previous_level": old_level,
        "level_changed": level_changed,
        "provisional": update.get("provisional"),
        "win_rate": update.get("win_rate"),
        "trailing_window_cases": update.get("trailing_window_cases"),
        "cases_completed_lifetime": lifetime,
    }


def recalculate_all(db) -> dict:
    """Nightly job body — recompute every attorney. Returns a run summary."""
    seed_level_config(db)
    changed = 0
    total = 0
    errors = 0
    for doc in db.collection("attorneys").stream():
        total += 1
        try:
            res = recalculate_attorney(db, doc.id)
            if res and res.get("level_changed"):
                changed += 1
        except Exception as exc:  # never let one bad doc kill the run
            errors += 1
            logger.error("[attorney_levels] recalc failed attorney=%s: %s", doc.id, exc)
    logger.warning(
        "[attorney_levels] recalc run: total=%d changed=%d errors=%d", total, changed, errors
    )
    return {"total": total, "level_changes": changed, "errors": errors}


# ── §4 record-outcome hook ────────────────────────────────────────────────────
def apply_case_outcome(db, attorney_id: str, outcome: str) -> None:
    """
    Called from operations.record-outcome when a case closes.
    Decrements active caseload, increments lifetime counters, and enqueues the
    attorney for the next recalculation run. Does NOT itself re-level (that's the
    nightly job's responsibility per §4) — but is safe to pair with an immediate
    recalculate_attorney() call if we want instant feedback.
    """
    from google.cloud.firestore_v1 import Increment, SERVER_TIMESTAMP

    if not attorney_id:
        return
    ref = db.collection("attorneys").document(attorney_id)
    if not ref.get().exists:
        logger.warning("[attorney_levels] outcome for unknown attorney=%s — skipped", attorney_id)
        return

    update = {
        "cases_active": Increment(-1),
        "cases_completed_lifetime": Increment(1),
        "pending_level_recalc": True,
        "last_outcome_at": SERVER_TIMESTAMP,
    }
    if outcome in WIN_OUTCOMES:
        update["cases_won_lifetime"] = Increment(1)
    ref.update(update)
    logger.warning(
        "[attorney_levels] outcome recorded attorney=%s outcome=%s win=%s",
        attorney_id, outcome, outcome in WIN_OUTCOMES,
    )


def log_self_sourced(db, attorney_id: str) -> None:
    """
    Record a Bring-Your-Own-Case submission (Dashboard spec §3.1). Levels owns
    the self_sourced counters (§2.1) and the XP event log (§2.4); the Dashboard
    self-sourced flow calls this so ownership stays in one place.

    Counters increment but self-sourced volume deliberately does NOT feed the
    win-rate / case-volume level gates (design doc: keep it a bonus track, not a
    way to skip the line). XP awarding stays inert until Slice 4 wires payouts;
    the event is logged now so the history exists when Slice 4 lands.
    """
    from google.cloud.firestore_v1 import Increment, SERVER_TIMESTAMP

    if not attorney_id:
        return
    ref = db.collection("attorneys").document(attorney_id)
    if not ref.get().exists:
        return
    ref.update({
        "self_sourced_count_lifetime": Increment(1),
        "self_sourced_count_trailing_30d": Increment(1),
    })
    db.collection("attorney_xp_events").add({
        "attorney_id": attorney_id,
        "event_type": "self_sourced_ticket",
        "xp_awarded": 0,          # Slice 4 assigns real XP values
        "created_at": SERVER_TIMESTAMP,
        "metadata": {},
    })
    logger.warning("[attorney_levels] self-sourced ticket logged attorney=%s", attorney_id)


# ── Audit log (§2.5) + attorney notification (§3.3) ───────────────────────────
def _write_level_change(db, attorney_id: str, from_level: str, to_level: str, reason: str) -> None:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    db.collection("attorney_level_changes").add({
        "attorney_id": attorney_id,
        "from_level": from_level,
        "to_level": to_level,
        "reason": reason,
        "triggered_at": SERVER_TIMESTAMP,
    })


def _notify_attorney_level_change(
    db, attorney_id: str, from_level: str, to_level: str, direction: str, reason: str
) -> None:
    """
    Write an attorney-facing notification. Brand voice: state the actual number
    and requirement, never a vague 'your performance changed' (§3.3, §7).
    """
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    if direction == "promoted":
        title = f"You've reached {to_level.title()}"
        body = f"Nice work — you're now {to_level.title()}. {reason}"
    else:
        title = f"Your level changed to {to_level.title()}"
        body = reason
    db.collection("attorney_notifications").add({
        "attorney_uid": attorney_id,
        "type": "level_change",
        "title": title,
        "body": body,
        "from_level": from_level,
        "to_level": to_level,
        "read": False,
        "created_at": SERVER_TIMESTAMP,
    })


# ── Backfill (Slice 1 acceptance) ─────────────────────────────────────────────
def backfill_attorney_fields(db) -> dict:
    """
    Merge default level fields onto every existing attorney doc without clobbering
    values that are already set. Also seeds level_config. Idempotent.
    """
    seeded = seed_level_config(db)
    defaults = default_level_fields()
    touched = 0
    for doc in db.collection("attorneys").stream():
        data = doc.to_dict()
        patch = {k: v for k, v in defaults.items() if k not in data}
        if patch:
            doc.reference.set(patch, merge=True)
            touched += 1
    logger.warning(
        "[attorney_levels] backfill: attorneys_touched=%d config_seeded=%s", touched, seeded
    )
    return {"attorneys_touched": touched, "config_seeded": seeded}
