"""
Case lifecycle — AAM-mediated quote-and-assignment engine (Attorney Dashboard
Engineering Spec v2, §1/§3/§4).

Supersedes the v1 self-service claim + reverse-auction bid model. Selection is
NEVER automatic: attorneys quote (or get a flat-rate auto-quote), the Attorney
Account Manager (AAM) reviews, sends assignment offer(s) to one or many attorneys,
and makes the final pick even against a single acceptance.

Actors are modeled as {type: "staff" | "ai_agent", id} so an AI AAM can slot in
later with no migration (§0).

This module owns the business logic; routes in app/routes/quote_engine.py stay thin.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Ticket status vocabulary (§1) ─────────────────────────────────────────────
# Internal (attorney/admin-facing) statuses. The Driver App maps these down to its
# own badge set via DRIVER_BADGE (never surface RFQ mechanics to drivers).
S_AI_REVIEW = "AI Review"
S_NEW = "New"
S_QUOTE_REQUESTED = "Quote Requested"
S_QUOTES_UNDER_REVIEW = "Quotes Under Review"
S_ASSIGNMENT_OFFERED = "Assignment Offered"
S_ADMIN_ASSIGNED = "Admin Assigned"
S_ACCEPTED = "Accepted"
S_ACTIVE = "Active"
S_OUTCOME_LOGGED = "Outcome Logged"
S_PAYOUT_REQUESTED = "Payout Requested"
S_PAYOUT_SENT = "Payout Sent"
S_CLOSED = "Closed"
S_REJECTED = "Rejected"

# Statuses that represent live, in-flight work — the set work-queue/monitor queries
# should filter on. Centralized here so every caller stays in sync (my review flag #2:
# hardcoded status lists in operations.py etc. must include the new intermediate states).
OPEN_WORK_STATUSES = [
    S_NEW, S_QUOTE_REQUESTED, S_QUOTES_UNDER_REVIEW, S_ASSIGNMENT_OFFERED,
    S_ADMIN_ASSIGNED, S_ACCEPTED, S_ACTIVE,
]
CLOSED_STATUSES = [S_OUTCOME_LOGGED, S_PAYOUT_REQUESTED, S_PAYOUT_SENT, S_CLOSED]

# Everything a work-queue / monitor should still surface, including pre-approval
# AI Review. Use this instead of hardcoded lists so new statuses never silently
# drop cases out of the case manager's queue. (8 values — within Firestore's
# 10-item `in` limit.)
WORK_QUEUE_STATUSES = [S_AI_REVIEW] + OPEN_WORK_STATUSES

# Internal status → Driver App badge (§1 mapping table).
DRIVER_BADGE = {
    S_AI_REVIEW: "Submitted — Under Review",
    S_NEW: "Processing",
    S_QUOTE_REQUESTED: "Processing",
    S_QUOTES_UNDER_REVIEW: "Processing",
    S_ASSIGNMENT_OFFERED: "Attorney Matched",
    S_ADMIN_ASSIGNED: "Attorney Matched",
    S_ACCEPTED: "Attorney Accepted",
    S_ACTIVE: "Attorney Accepted",
    S_OUTCOME_LOGGED: "Case Closed",
    S_PAYOUT_REQUESTED: "Case Closed",
    S_PAYOUT_SENT: "Case Closed",
    S_CLOSED: "Case Closed",
    S_REJECTED: "Unable to Process",
    # "Atty Declined" is transient/internal — deliberately not shown to drivers.
}

def driver_badge(internal_status: Optional[str]) -> str:
    return DRIVER_BADGE.get(internal_status or "", "Processing")


# ── Driver-PII protection (anti-disintermediation) ───────────────────────────
# Attorneys evaluate and work cases on the merits; they must NEVER see driver
# contact info, so no one can go around the platform. Charges/violation/court info
# is always visible; the driver's name is masked to "First L." once assigned, and
# hidden entirely at the quote stage.
_DRIVER_PII_FIELDS = {
    "driver_phone", "driver_mobile", "driver_email", "driver_s_email", "driver_address",
    "driver_cdl", "driver_dob", "cdl_license_number", "driver_id", "driver_full_name",
    "driver_name", "driver_first_name", "driver_last_name", "external_client_id",
    "attorney_phone", "attorney_email",
}


def mask_driver_name(full: Optional[str]) -> str:
    if not full or not str(full).strip():
        return "Client"
    parts = str(full).split()
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][:1]}."


def charges_view(ticket: dict) -> dict:
    """PII-safe ticket detail for the quote stage — charges only, no driver identity."""
    return {
        "violation_category": ticket.get("violation_category"),
        "violation_description": ticket.get("violation_description"),
        "statute_code": ticket.get("statute_code"),
        "ticket_state": ticket.get("ticket_state"),
        "ticket_county": ticket.get("ticket_county"),
        "ticket_city": ticket.get("ticket_city"),
        "court_date": ticket.get("court_date"),
        "date_of_ticket": ticket.get("date_of_ticket"),
        "citation_number": ticket.get("citation_number"),
        "fine_amount": ticket.get("fine_amount"),
        "penalty_amount": ticket.get("penalty_amount"),
        "urgency_level": ticket.get("urgency_level"),
        "cdl_case": bool(ticket.get("driver_cdl") or ticket.get("cdl_license_number")),
        "origin": ticket.get("origin") or "rr_pipeline",
        "accident": ticket.get("accident"),
    }


def strip_driver_pii(ticket: dict, keep_masked_name: bool = True) -> dict:
    """Copy of a ticket with all driver PII removed; optional masked display name."""
    safe = {k: v for k, v in ticket.items() if k not in _DRIVER_PII_FIELDS}
    if keep_masked_name:
        safe["driver_display"] = mask_driver_name(
            ticket.get("driver_full_name") or ticket.get("driver_name"))
    return safe

# ── Response-deadline by urgency (§4.2) — business days, tunable ──────────────
DEADLINE_BUSINESS_DAYS = {"CRITICAL": 1, "HIGH": 2, "STANDARD": 3, "LOW": 3}

# ── Decline reason taxonomy seed (§3.4) — config-driven, editable w/o deploy ──
DEFAULT_DECLINE_REASONS = [
    {"code": "court_date_too_close", "label": "Court date is too close to prepare"},
    {"code": "low_dismissal_likelihood", "label": "Charges are unlikely to be dismissed or reduced"},
    {"code": "anti_masking_state", "label": "State prohibits masking for CDL holders"},
    {"code": "judge_relationship_unfavorable", "label": "Assigned judge is a poor fit for this case"},
    {"code": "schedule_conflict", "label": "Scheduling conflict"},
    {"code": "outside_practice_area", "label": "Outside my practice area / experience"},
    {"code": "other", "label": "Other (requires notes)"},
]


# ── Firestore + time helpers ──────────────────────────────────────────────────
def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    return _firestore_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def add_business_days(start: datetime, n: int) -> datetime:
    d = start
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:  # Mon–Fri
            added += 1
    return d


def actor(kind: str, ident: str) -> dict:
    """Build a {type, id} actor. kind is 'staff' or 'ai_agent'."""
    return {"type": kind if kind in ("staff", "ai_agent") else "staff", "id": ident}


def notify_attorney(db, attorney_uid: str, ntype: str, title: str, body: str, **extra) -> None:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    doc = {
        "attorney_uid": attorney_uid, "type": ntype, "title": title, "body": body,
        "read": False, "created_at": SERVER_TIMESTAMP,
    }
    doc.update(extra)
    db.collection("attorney_notifications").add(doc)


# ── decline_reasons config ────────────────────────────────────────────────────
def seed_decline_reasons(db) -> list[str]:
    written = []
    for r in DEFAULT_DECLINE_REASONS:
        ref = db.collection("decline_reasons").document(r["code"])
        if not ref.get().exists:
            ref.set({**r, "description": r["label"], "active": True})
            written.append(r["code"])
    return written


def get_decline_reasons(db) -> list[dict]:
    docs = list(db.collection("decline_reasons").stream())
    if not docs:
        seed_decline_reasons(db)
        return [{**r, "active": True} for r in DEFAULT_DECLINE_REASONS]
    return [{**d.to_dict(), "code": d.id} for d in docs]


def valid_decline_code(db, code: str) -> bool:
    return any(r.get("code") == code and r.get("active", True) for r in get_decline_reasons(db))


# ── Attorney matching (reuses the Madam Walker pattern, agents.md §12) ──────────
def match_attorneys(db, state: str, county: Optional[str], exclude: Optional[set[str]] = None) -> list[tuple[str, dict]]:
    """
    Onboarded attorneys covering this state (county matches ranked first).
    Returns [(attorney_id, data)] excluding any ids in `exclude`.
    """
    exclude = exclude or set()
    state = (state or "").upper()
    if not state:
        return []
    county_hits: list[tuple[str, dict]] = []
    state_hits: list[tuple[str, dict]] = []
    q = (db.collection("attorneys")
           .where("status", "==", "onboarded")
           .where("states_covered", "array_contains", state))
    for d in q.stream():
        if d.id in exclude:
            continue
        data = d.to_dict()
        if county and county in (data.get("counties_covered") or []):
            county_hits.append((d.id, data))
        else:
            state_hits.append((d.id, data))
    return county_hits + state_hits


# ── Flat-rate resolution (§3.6 / §9.1) ────────────────────────────────────────
# flat_rate_schedule shape is an OPEN founder decision. Interim-flexible resolver:
# accepts a plain number, or a dict keyed by violation_category with a "default"
# fallback. Works regardless of the final decision; swap the resolver when settled.
def resolve_flat_rate(schedule, violation_category: Optional[str]) -> Optional[float]:
    if schedule is None:
        return None
    if isinstance(schedule, (int, float)):
        return float(schedule)
    if isinstance(schedule, dict):
        if violation_category and violation_category in schedule:
            return float(schedule[violation_category])
        if "default" in schedule:
            return float(schedule["default"])
    return None


# ── §4.1 Open a quote request ────────────────────────────────────────────────
def open_quote_request(db, ticket_id: str, initiated_by: dict) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    tref = db.collection("tickets").document(ticket_id)
    tsnap = tref.get()
    if not tsnap.exists:
        raise ValueError("ticket_not_found")
    ticket = tsnap.to_dict()
    state = ticket.get("ticket_state") or ticket.get("region") or ""
    county = ticket.get("ticket_county")
    violation = ticket.get("violation_category")

    matches = match_attorneys(db, state, county)
    request_id = str(uuid.uuid4())
    attorney_ids = [aid for aid, _ in matches]

    # 3-day quote window (business days) by default.
    window_close = add_business_days(_now(), 3)
    db.collection("case_quote_requests").document(request_id).set({
        "ticket_id": ticket_id,
        "requested_by": initiated_by,
        "requested_at": SERVER_TIMESTAMP,
        "attorneys_notified": attorney_ids,
        "quote_window_closes_at": window_close,
        "status": "open",
    })

    auto_quotes = 0
    invited = 0
    for aid, data in matches:
        if data.get("pricing_mode") == "flat":
            rate = resolve_flat_rate(data.get("flat_rate_schedule"), violation)
            if rate is not None:
                # Flat-rate schedule is a single number per category; use it for the
                # no-trial fee and default the trial fee to the same until tuned.
                _create_quote(db, request_id, ticket_id, aid, rate, rate, "flat_rate_applied", None)
                auto_quotes += 1
                continue  # no attorney action needed
        # case-by-case (or flat w/o a resolvable rate): invite to quote in First View
        notify_attorney(db, aid, "quote_opportunity",
                        "New case open for your quote",
                        f"A {violation or 'case'} in {state} is open for quoting.",
                        ticket_id=ticket_id, request_id=request_id)
        invited += 1

    tref.update({
        "attorney_status": S_QUOTE_REQUESTED,
        "quote_request_id": request_id,
        "last_modified_date": SERVER_TIMESTAMP,
    })
    _refresh_quote_summary(db, ticket_id, request_id)
    logger.warning("[case_lifecycle] quote request opened ticket=%s matches=%d auto=%d invited=%d",
                   ticket_id, len(matches), auto_quotes, invited)
    return {"request_id": request_id, "attorneys_notified": attorney_ids,
            "auto_quotes": auto_quotes, "invited": invited}


def _create_quote(db, request_id, ticket_id, attorney_id, fee_no_trial, fee_trial,
                  quote_type, notes) -> str:
    """A quote carries two prices: fee_no_trial (resolve without trial) and fee_trial."""
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    atty = db.collection("attorneys").document(attorney_id).get()
    a = atty.to_dict() if atty.exists else {}
    quote_id = str(uuid.uuid4())
    db.collection("case_quotes").document(quote_id).set({
        "request_id": request_id, "ticket_id": ticket_id, "attorney_id": attorney_id,
        "attorney_name": a.get("full_name") or a.get("Name") or "",
        "fee_no_trial": float(fee_no_trial),
        "fee_trial": float(fee_trial) if fee_trial is not None else None,
        "quote_amount": float(fee_no_trial),   # back-compat: base fee = no-trial price
        "quote_type": quote_type, "notes": notes,
        "submitted_at": SERVER_TIMESTAMP, "status": "submitted",
    })
    return quote_id


def submit_quote(db, request_id: str, attorney_id: str,
                 fee_no_trial: float, fee_trial: Optional[float], notes: Optional[str]) -> str:
    """Attorney (case-by-case) submits a two-price quote in First View."""
    req = db.collection("case_quote_requests").document(request_id).get()
    if not req.exists:
        raise ValueError("request_not_found")
    rd = req.to_dict()
    if rd.get("status") != "open":
        raise ValueError("request_closed")
    if attorney_id not in (rd.get("attorneys_notified") or []):
        raise ValueError("not_invited")
    existing = list(db.collection("case_quotes")
                      .where("request_id", "==", request_id)
                      .where("attorney_id", "==", attorney_id).limit(1).stream())
    if existing:
        raise ValueError("already_quoted")
    qid = _create_quote(db, request_id, rd["ticket_id"], attorney_id,
                        fee_no_trial, fee_trial, "case_reviewed", notes)
    _refresh_quote_summary(db, rd["ticket_id"], request_id)
    return qid


def _refresh_quote_summary(db, ticket_id: str, request_id: str) -> None:
    """Denormalize {quote_count, low, high} onto the ticket for AAM dashboard sort (§3.10)."""
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    quotes = [q.to_dict() for q in db.collection("case_quotes").where("request_id", "==", request_id).stream()]
    amounts = [q["quote_amount"] for q in quotes if q.get("quote_amount") is not None]
    summary = {
        "quote_count": len(quotes),
        "low": min(amounts) if amounts else None,
        "high": max(amounts) if amounts else None,
    }
    update = {"quote_summary": summary, "last_modified_date": SERVER_TIMESTAMP}
    # Once any quote exists, surface the case as under review for the AAM.
    if quotes:
        update["attorney_status"] = S_QUOTES_UNDER_REVIEW
    db.collection("tickets").document(ticket_id).update(update)


# ── §4.1/§6.2 AAM review payload ─────────────────────────────────────────────
def review_payload(db, request_id: str) -> dict:
    req = db.collection("case_quote_requests").document(request_id).get()
    if not req.exists:
        raise ValueError("request_not_found")
    rd = req.to_dict()
    ticket_id = rd["ticket_id"]
    tsnap = db.collection("tickets").document(ticket_id).get()
    ticket = tsnap.to_dict() if tsnap.exists else {}
    county = ticket.get("ticket_county")

    quotes = []
    for q in db.collection("case_quotes").where("request_id", "==", request_id).stream():
        qd = q.to_dict()
        aid = qd.get("attorney_id")
        a = db.collection("attorneys").document(aid).get()
        ad = a.to_dict() if a.exists else {}
        # Judge-relationship notes for this county (staff-only, §3.5).
        judge_notes = []
        if county:
            jr = (db.collection("attorney_judge_relationships")
                    .where("attorney_id", "==", aid)
                    .where("county", "==", county).stream())
            judge_notes = [{"judge_name": j.to_dict().get("judge_name"),
                            "notes": j.to_dict().get("relationship_notes")} for j in jr]
        quotes.append({
            "quote_id": q.id,
            "attorney_id": aid,
            "attorney_name": qd.get("attorney_name"),
            "fee_no_trial": qd.get("fee_no_trial", qd.get("quote_amount")),
            "fee_trial": qd.get("fee_trial"),
            "quote_amount": qd.get("quote_amount"),
            "quote_type": qd.get("quote_type"),
            "notes": qd.get("notes"),
            # Performance context (owned by attorney_levels, read-only here).
            "win_rate": ad.get("win_rate"),
            "performance_level": ad.get("performance_level"),
            "no_show_count_trailing": ad.get("no_show_count_trailing"),
            "aam_relationship_notes": ad.get("aam_relationship_notes"),
            "judge_relationships": judge_notes,
        })
    return {"request_id": request_id, "ticket_id": ticket_id,
            "ticket": {"violation_category": ticket.get("violation_category"),
                       "ticket_state": ticket.get("ticket_state"),
                       "ticket_county": county,
                       "court_date": ticket.get("court_date")},
            "quotes": quotes}


# ── AAM console: queue views ──────────────────────────────────────────────────
def list_quote_requests(db, status: Optional[str] = None) -> list[dict]:
    """Open/under-review quote requests for the AAM console's review queue."""
    q = db.collection("case_quote_requests")
    if status:
        q = q.where("status", "==", status)
    out = []
    for r in q.stream():
        rd = r.to_dict()
        tsnap = db.collection("tickets").document(rd["ticket_id"]).get()
        t = tsnap.to_dict() if tsnap.exists else {}
        wc = rd.get("quote_window_closes_at")
        out.append({
            "request_id": r.id, "ticket_id": rd["ticket_id"], "status": rd.get("status"),
            "violation": t.get("violation_category"), "state": t.get("ticket_state"),
            "county": t.get("ticket_county"), "court_date": t.get("court_date"),
            "urgency_level": t.get("urgency_level"),
            "attorneys_notified": len(rd.get("attorneys_notified") or []),
            "quote_summary": t.get("quote_summary"),
            "quote_window_closes_at": wc.isoformat() if hasattr(wc, "isoformat") else wc,
        })
    out.sort(key=lambda c: {"CRITICAL": 0, "HIGH": 1}.get(c.get("urgency_level"), 2))
    return out


def list_broadcasts_pending_finalization(db) -> list[dict]:
    """Broadcast groups with at least one accepted offer, awaiting the AAM's final pick."""
    by_group: dict[str, list[dict]] = {}
    for o in db.collection("case_assignment_offers").stream():
        od = o.to_dict()
        by_group.setdefault(od["broadcast_group_id"], []).append({**od, "offer_id": o.id})

    out = []
    for gid, offers in by_group.items():
        if not any(o.get("status") == "accepted" for o in offers):
            continue
        ticket_id = offers[0]["ticket_id"]
        tsnap = db.collection("tickets").document(ticket_id).get()
        t = tsnap.to_dict() if tsnap.exists else {}
        if t.get("attorney_status") != S_ASSIGNMENT_OFFERED:
            continue  # already finalized
        responses = []
        for o in offers:
            aid = o.get("attorney_id")
            a = db.collection("attorneys").document(aid).get()
            ad = a.to_dict() if a.exists else {}
            responses.append({
                "offer_id": o["offer_id"], "attorney_id": aid,
                "attorney_name": ad.get("full_name") or ad.get("Name") or aid,
                "status": o.get("status"),
                "performance_level": ad.get("performance_level"),
            })
        out.append({
            "broadcast_group_id": gid, "ticket_id": ticket_id,
            "violation": t.get("violation_category"), "state": t.get("ticket_state"),
            "county": t.get("ticket_county"), "court_date": t.get("court_date"),
            "urgency_level": t.get("urgency_level"),
            "quote_summary": t.get("quote_summary"),
            "responses": responses,
        })
    return out


# ── §4.1 Send assignment offer(s) — single or broadcast ──────────────────────
def send_assignment_offers(db, request_id: str, attorney_ids: list[str], decided_by: dict) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    req = db.collection("case_quote_requests").document(request_id).get()
    if not req.exists:
        raise ValueError("request_not_found")
    rd = req.to_dict()
    ticket_id = rd["ticket_id"]
    tsnap = db.collection("tickets").document(ticket_id).get()
    urgency = (tsnap.to_dict() or {}).get("urgency_level") or "STANDARD"
    days = DEADLINE_BUSINESS_DAYS.get(urgency, 3)
    deadline = add_business_days(_now(), days)

    broadcast_id = str(uuid.uuid4())
    for aid in attorney_ids:
        oid = str(uuid.uuid4())
        db.collection("case_assignment_offers").document(oid).set({
            "ticket_id": ticket_id, "attorney_id": aid,
            "broadcast_group_id": broadcast_id,
            "offered_at": SERVER_TIMESTAMP, "response_deadline": deadline,
            "status": "pending", "responded_at": None,
            "decline_reason_code": None, "decline_reason_notes": None,
        })
        notify_attorney(db, aid, "assignment_offer", "You've been offered a case",
                        f"Respond by {deadline.strftime('%b %d')}.",
                        ticket_id=ticket_id, offer_id=oid, broadcast_group_id=broadcast_id)

    db.collection("case_quote_requests").document(request_id).update({"status": "under_review"})
    db.collection("tickets").document(ticket_id).update({
        "attorney_status": S_ASSIGNMENT_OFFERED,
        "current_assignment_offer_broadcast_id": broadcast_id,
        "last_modified_date": SERVER_TIMESTAMP,
    })
    return {"broadcast_group_id": broadcast_id, "offered_to": attorney_ids, "response_deadline": deadline.isoformat()}


# ── §4.3 Accept / decline + re-broadcast ─────────────────────────────────────
def accept_offer(db, offer_id: str, attorney_id: str) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    ref = db.collection("case_assignment_offers").document(offer_id)
    snap = ref.get()
    if not snap.exists:
        raise ValueError("offer_not_found")
    o = snap.to_dict()
    if o.get("attorney_id") != attorney_id:
        raise ValueError("not_your_offer")
    if o.get("status") != "pending":
        raise ValueError("offer_not_pending")
    ref.update({"status": "accepted", "responded_at": SERVER_TIMESTAMP})
    # Acceptance does NOT auto-assign — held for AAM finalization (§4.4).
    return {"ok": True, "held_for_finalization": True}


def decline_offer(db, offer_id: str, attorney_id: str, reason_code: str, notes: Optional[str]) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    ref = db.collection("case_assignment_offers").document(offer_id)
    snap = ref.get()
    if not snap.exists:
        raise ValueError("offer_not_found")
    o = snap.to_dict()
    if o.get("attorney_id") != attorney_id:
        raise ValueError("not_your_offer")
    if o.get("status") != "pending":
        raise ValueError("offer_not_pending")
    ref.update({"status": "declined", "responded_at": SERVER_TIMESTAMP,
                "decline_reason_code": reason_code, "decline_reason_notes": notes})
    _log_decline_analytics(db, o["ticket_id"], reason_code)
    _maybe_rebroadcast(db, o["broadcast_group_id"], o["ticket_id"])
    return {"ok": True}


def _log_decline_analytics(db, ticket_id: str, reason_code: str) -> None:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    db.collection("decline_analytics").add({
        "ticket_id": ticket_id, "reason_code": reason_code, "at": SERVER_TIMESTAMP,
    })


def _offered_attorney_ids(db, ticket_id: str) -> set[str]:
    ids = set()
    for o in db.collection("case_assignment_offers").where("ticket_id", "==", ticket_id).stream():
        ids.add(o.to_dict().get("attorney_id"))
    return ids


def _maybe_rebroadcast(db, broadcast_group_id: str, ticket_id: str) -> None:
    """§4.3 — if no pending offers remain in the group, re-broadcast to next-best."""
    pending = [o for o in db.collection("case_assignment_offers")
                 .where("broadcast_group_id", "==", broadcast_group_id).stream()
               if o.to_dict().get("status") == "pending"]
    if pending:
        return
    tsnap = db.collection("tickets").document(ticket_id).get()
    ticket = tsnap.to_dict() if tsnap.exists else {}
    state = ticket.get("ticket_state") or ticket.get("region") or ""
    county = ticket.get("ticket_county")
    already = _offered_attorney_ids(db, ticket_id)
    nxt = match_attorneys(db, state, county, exclude=already)
    if nxt:
        request_id = ticket.get("quote_request_id")
        # Re-broadcast a fresh round to the next-best attorneys.
        send_assignment_offers(db, request_id, [aid for aid, _ in nxt],
                               decided_by=actor("ai_agent", "rebroadcast"))
        logger.warning("[case_lifecycle] re-broadcast ticket=%s to %d attorneys", ticket_id, len(nxt))
    else:
        db.collection("tickets").document(ticket_id).update({"no_attorney_flag": True})
        logger.warning("[case_lifecycle] no attorneys left ticket=%s — flagged", ticket_id)


# ── §4.4 Finalize (AAM's final pick) ─────────────────────────────────────────
def finalize_assignment(db, broadcast_group_id: str, selected_attorney_id: str, decided_by: dict) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    offers = list(db.collection("case_assignment_offers")
                    .where("broadcast_group_id", "==", broadcast_group_id).stream())
    if not offers:
        raise ValueError("broadcast_not_found")
    ticket_id = offers[0].to_dict()["ticket_id"]
    selected_found = False
    not_selected = []
    for o in offers:
        od = o.to_dict()
        if od.get("attorney_id") == selected_attorney_id:
            o.reference.update({"status": "accepted"})
            selected_found = True
        elif od.get("status") == "accepted":
            o.reference.update({"status": "not_selected"})
            not_selected.append(od.get("attorney_id"))
    if not selected_found:
        raise ValueError("selected_attorney_not_in_broadcast")

    db.collection("tickets").document(ticket_id).update({
        "attorney_status": S_ADMIN_ASSIGNED,
        "attorney_id": selected_attorney_id,
        "assigned_attorney_id": selected_attorney_id,
        "assigned_by": decided_by,
        "assigned_at": SERVER_TIMESTAMP,
        "last_modified_date": SERVER_TIMESTAMP,
    })
    # Mark the winning quote selected, others not — and stamp the agreed fee onto
    # the ticket so the wallet/payout slice can sum it once the case is Outcome Logged.
    req = db.collection("tickets").document(ticket_id).get().to_dict().get("quote_request_id")
    if req:
        for q in db.collection("case_quotes").where("request_id", "==", req).stream():
            qd = q.to_dict()
            won = qd.get("attorney_id") == selected_attorney_id
            q.reference.update({"status": "selected" if won else "not_selected"})
            if won and qd.get("quote_amount") is not None:
                # Stamp both agreed prices; attorney_fee (no-trial) is the default the
                # wallet sums, attorney_fee_trial applies if the case goes to trial.
                db.collection("tickets").document(ticket_id).update({
                    "attorney_fee": qd.get("fee_no_trial", qd["quote_amount"]),
                    "attorney_fee_trial": qd.get("fee_trial"),
                })
        db.collection("case_quote_requests").document(req).update({"status": "closed"})

    notify_attorney(db, selected_attorney_id, "assignment_selected",
                    "You've been assigned this case", "Confirm to begin.", ticket_id=ticket_id)
    for aid in not_selected:
        # §7.3 — states plainly that another attorney was chosen, no reasons disclosed.
        notify_attorney(db, aid, "assignment_not_selected",
                        "Another attorney was selected",
                        "Thanks for accepting — this one went to another attorney.", ticket_id=ticket_id)
    return {"ok": True, "ticket_id": ticket_id, "assigned_attorney_id": selected_attorney_id,
            "not_selected": not_selected}


def list_pending_offers_for_attorney(db, attorney_id: str) -> list[dict]:
    out = []
    for o in db.collection("case_assignment_offers").where("attorney_id", "==", attorney_id).stream():
        od = o.to_dict()
        if od.get("status") != "pending":
            continue
        tsnap = db.collection("tickets").document(od["ticket_id"]).get()
        t = tsnap.to_dict() if tsnap.exists else {}
        dl = od.get("response_deadline")
        out.append({
            "offer_id": o.id, "ticket_id": od["ticket_id"],
            "broadcast_group_id": od.get("broadcast_group_id"),
            "response_deadline": dl.isoformat() if hasattr(dl, "isoformat") else dl,
            "violation": t.get("violation_category"), "state": t.get("ticket_state"),
            "county": t.get("ticket_county"), "court_date": t.get("court_date"),
        })
    return out


# ── §4.5 Wallet + payout (Slice 5, manual-payout MVP) ────────────────────────
def _month_key(dt: datetime) -> tuple[int, int]:
    return (dt.year, dt.month)


def wallet_summary(db, attorney_id: str) -> dict:
    """Available balance = agreed fees on this attorney's Outcome-Logged cases not
    yet cashed out; plus pending payout total and this-month earnings."""
    now = _now()
    available = 0.0
    month_earned = 0.0
    available_cases = []
    q = (db.collection("tickets")
           .where("assigned_attorney_id", "==", attorney_id)
           .where("attorney_status", "==", S_OUTCOME_LOGGED))
    for d in q.stream():
        t = d.to_dict()
        fee = float(t.get("attorney_fee") or 0)
        available += fee
        available_cases.append({
            "ticket_id": d.id, "fee": fee,
            "driver_name": t.get("driver_full_name") or t.get("driver_name") or "",
            "violation": t.get("violation_category") or "",
            "outcome": t.get("outcome"),
        })
        oat = t.get("outcome_logged_at") or t.get("closed_at")
        if hasattr(oat, "timestamp"):
            odt = datetime.fromtimestamp(oat.timestamp(), tz=timezone.utc)
            if _month_key(odt) == _month_key(now):
                month_earned += fee

    pending = 0.0
    history = []
    for p in db.collection("payout_requests").where("attorney_id", "==", attorney_id).stream():
        pd = p.to_dict()
        if pd.get("status") in ("requested", "processing"):
            pending += float(pd.get("total_amount") or 0)
        elif pd.get("status") == "paid":
            ra = pd.get("paid_at") or pd.get("requested_at")
            history.append({
                "payout_id": p.id, "total_amount": pd.get("total_amount"),
                "payout_method": pd.get("payout_method"),
                "ticket_ids": pd.get("ticket_ids") or [],
                "paid_at": ra.isoformat() if hasattr(ra, "isoformat") else ra,
            })
    history.sort(key=lambda h: h.get("paid_at") or "", reverse=True)
    return {
        "available_balance": round(available, 2),
        "available_cases": available_cases,
        "pending_payout": round(pending, 2),
        "this_month_earned": round(month_earned, 2),
        "payout_history": history,
    }


def create_payout_request(db, attorney_id: str) -> dict:
    """'Checkout' — bundles all Outcome-Logged cases into one payout request and
    moves them to Payout Requested."""
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    summary = wallet_summary(db, attorney_id)
    cases = summary["available_cases"]
    if not cases:
        raise ValueError("no_balance")
    ticket_ids = [c["ticket_id"] for c in cases]
    total = summary["available_balance"]
    payout_id = str(uuid.uuid4())
    db.collection("payout_requests").document(payout_id).set({
        "attorney_id": attorney_id, "ticket_ids": ticket_ids, "total_amount": total,
        "status": "requested", "requested_at": SERVER_TIMESTAMP,
        "paid_at": None, "payout_method": None, "processed_by": None,
    })
    for tid in ticket_ids:
        db.collection("tickets").document(tid).update({
            "attorney_status": S_PAYOUT_REQUESTED, "payout_request_id": payout_id,
            "last_modified_date": SERVER_TIMESTAMP,
        })
    logger.warning("[case_lifecycle] payout requested attorney=%s cases=%d total=%.2f",
                   attorney_id, len(ticket_ids), total)
    return {"payout_id": payout_id, "total_amount": total, "ticket_ids": ticket_ids}


def list_payout_requests(db, status: Optional[str] = None) -> list[dict]:
    q = db.collection("payout_requests")
    if status:
        q = q.where("status", "==", status)
    out = []
    for p in q.stream():
        pd = p.to_dict()
        ra = pd.get("requested_at")
        out.append({"payout_id": p.id, **{k: v for k, v in pd.items() if not hasattr(v, "timestamp")},
                    "requested_at": ra.isoformat() if hasattr(ra, "isoformat") else ra})
    out.sort(key=lambda x: x.get("requested_at") or "", reverse=True)
    return out


def mark_payout_paid(db, payout_id: str, method: str, staff_id: str) -> dict:
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    ref = db.collection("payout_requests").document(payout_id)
    snap = ref.get()
    if not snap.exists:
        raise ValueError("payout_not_found")
    pd = snap.to_dict()
    if pd.get("status") == "paid":
        raise ValueError("already_paid")
    ref.update({"status": "paid", "payout_method": method,
                "processed_by": staff_id, "paid_at": SERVER_TIMESTAMP})
    for tid in pd.get("ticket_ids") or []:
        db.collection("tickets").document(tid).update({
            "attorney_status": S_PAYOUT_SENT, "last_modified_date": SERVER_TIMESTAMP,
        })
        notify_attorney(db, pd["attorney_id"], "payout_sent", "Payout sent",
                        f"Your payout was sent via {method}.", ticket_id=tid)
    return {"ok": True, "payout_id": payout_id}


def first_view_for_attorney(db, attorney_id: str) -> list[dict]:
    """Cases this attorney was invited to quote on and hasn't quoted yet (§6.4)."""
    out = []
    reqs = db.collection("case_quote_requests").where("status", "==", "open").stream()
    for r in reqs:
        rd = r.to_dict()
        if attorney_id not in (rd.get("attorneys_notified") or []):
            continue
        already = list(db.collection("case_quotes")
                         .where("request_id", "==", r.id)
                         .where("attorney_id", "==", attorney_id).limit(1).stream())
        tsnap = db.collection("tickets").document(rd["ticket_id"]).get()
        t = tsnap.to_dict() if tsnap.exists else {}
        dl = rd.get("quote_window_closes_at")
        out.append({
            "request_id": r.id, "ticket_id": rd["ticket_id"],
            "violation": t.get("violation_category"), "state": t.get("ticket_state"),
            "county": t.get("ticket_county"), "court_date": t.get("court_date"),
            "quote_window_closes_at": dl.isoformat() if hasattr(dl, "isoformat") else dl,
            "already_quoted": bool(already),
        })
    return out
