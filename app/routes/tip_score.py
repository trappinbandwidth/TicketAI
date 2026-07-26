"""Role-filtered API projections for the authoritative TIP Score service."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.platform.service import (
    PlatformService,
    organization_id_for_profile,
    principal_id_for_uid,
)
from app.routes._common import get_db, verify_token
from app.services.auth_rbac import STAFF_ROLES
from app.services.carrier_resolve import CarrierResolveService
from app.services.tip_score import (
    ScoreCalculationInput,
    TipScoreCalculator,
    TipScoreSnapshot,
    TipScoreStatus,
    thin_file_input,
)


router = APIRouter(prefix="/tip-score", tags=["tip-score"])


def _enabled() -> None:
    if os.getenv("TIP_SCORE_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="TIP Score APIs are not enabled.")


def _claims(authorization: Optional[str]) -> dict:
    _enabled()
    return verify_token(authorization)


def _actor_id(claims: dict) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _snapshot(driver_id: str) -> TipScoreSnapshot:
    """Read an immutable snapshot or return the governed thin-file projection.

    A GET never persists a synthetic score. Ingestion/recalculation will own
    snapshot writes; until verified evidence exists, all portals see the same
    deterministic 700 developing-profile projection.
    """
    db = get_db()
    current = db.collection("tip_score_current").document(driver_id).get()
    snapshot = (
        TipScoreSnapshot.model_validate(current.to_dict())
        if current.exists
        else TipScoreCalculator().calculate(
            thin_file_input(driver_id, data_as_of=datetime.now(timezone.utc))
        )
    )
    lifecycle = db.collection("tip_score_lifecycle").document(driver_id).get()
    if not lifecycle.exists:
        return snapshot
    value = lifecycle.to_dict() or {}
    updates = {}
    if value.get("snapshot_id") == snapshot.id:
        if value.get("publication_state") in {"shadow", "human_review", "withdrawn"}:
            updates["publication_state"] = value["publication_state"]
        if value.get("score_status") in {item.value for item in TipScoreStatus}:
            updates["status"] = TipScoreStatus(value["score_status"])
    return snapshot.model_copy(update=updates)


def _public_projection(snapshot: TipScoreSnapshot) -> dict:
    return snapshot.model_dump(mode="json")


def _authorize_driver_or_staff(claims: dict, driver_id: str) -> str:
    actor_id = _actor_id(claims)
    role = str(claims.get("role") or "")
    staff_role = str(claims.get("staff_role") or "")
    if actor_id == driver_id or role in STAFF_ROLES or staff_role in STAFF_ROLES:
        return "captain" if role in STAFF_ROLES or staff_role in STAFF_ROLES else "driver"
    raise HTTPException(status_code=403, detail="TIP Score access denied.")


def _authorize_carrier(claims: dict, driver_id: str) -> None:
    if claims.get("role") != "carrier":
        raise HTTPException(status_code=403, detail="Carrier role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    organization_id = organization_id_for_profile("carrier", uid)
    CarrierResolveService(db)._authorize(
        principal_id_for_uid(uid), organization_id, driver_id
    )


def _carrier_context(claims: dict):
    if claims.get("role") != "carrier":
        raise HTTPException(status_code=403, detail="Carrier role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    actor_id = principal_id_for_uid(uid)
    organization_id = organization_id_for_profile("carrier", uid)
    return db, actor_id, organization_id


def _authorize_attorney(claims: dict, driver_id: str) -> None:
    if claims.get("role") != "attorney":
        raise HTTPException(status_code=403, detail="Attorney role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    attorney_id = claims.get("attorney_id") or uid
    # Attorney access follows the canonical ticket/case assignment used by the
    # Attorney portal. Score sharing is a separate, explicit client consent;
    # assignment alone is never enough.
    identifiers = {driver_id}
    principal = db.collection("principals").document(driver_id).get()
    if principal.exists:
        firebase_uid = (principal.to_dict() or {}).get("firebase_uid")
        if isinstance(firebase_uid, str):
            identifiers.add(firebase_uid)
    terminal = {"ticket closed", "outcome logged", "payout sent", "closed", "cancelled"}
    allowed = False
    for identifier in identifiers:
        matches = db.collection("tickets").where("driver_id", "==", identifier).limit(20).stream()
        for document in matches:
            case = document.to_dict() or {}
            owns_case = attorney_id in {
                case.get("assigned_attorney_id"),
                case.get("claimed_by"),
                case.get("closed_by_attorney_id"),
            }
            active = str(case.get("attorney_status") or case.get("status") or "").lower() not in terminal
            if owns_case and active and case.get("tip_score_consent_on_file") is True:
                allowed = True
                break
        if allowed:
            break
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Active client case and score-sharing consent required.",
        )


def _attorney_case(claims: dict, ticket_id: str) -> tuple[dict, str]:
    if claims.get("role") != "attorney":
        raise HTTPException(status_code=403, detail="Attorney role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    attorney_id = claims.get("attorney_id") or uid
    snapshot = db.collection("tickets").document(ticket_id).get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Case not found.")
    case = snapshot.to_dict() or {}
    if attorney_id not in {
        case.get("assigned_attorney_id"),
        case.get("claimed_by"),
        case.get("closed_by_attorney_id"),
    }:
        raise HTTPException(status_code=404, detail="Case not found.")
    terminal = {"ticket closed", "outcome logged", "payout sent", "closed", "cancelled"}
    if str(case.get("attorney_status") or case.get("status") or "").lower() in terminal:
        raise HTTPException(status_code=409, detail="The case is no longer active.")
    if case.get("tip_score_consent_on_file") is not True:
        raise HTTPException(
            status_code=403,
            detail="Client TIP Score sharing consent required.",
        )
    driver_uid = case.get("driver_id")
    if not isinstance(driver_uid, str) or not driver_uid:
        raise HTTPException(status_code=409, detail="Case Driver identity is unavailable.")
    principal_id = (
        driver_uid if driver_uid.startswith("prn_") else principal_id_for_uid(driver_uid)
    )
    return case, principal_id


class AttorneySimulationRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=80)
    event_ids: list[str] = Field(default_factory=list, max_length=50)


@router.get("/me")
def get_my_score(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    driver_id = _actor_id(claims)
    if claims.get("role") not in {None, "", "driver"}:
        raise HTTPException(status_code=403, detail="Driver role required.")
    return _public_projection(_snapshot(driver_id))


@router.get("/drivers/{driver_id}")
def get_score_for_driver(
    driver_id: str,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    role = str(claims.get("role") or "")
    staff_role = str(claims.get("staff_role") or "")
    if role == "carrier":
        _authorize_carrier(claims, driver_id)
        projection = "carrier"
    elif role == "attorney":
        _authorize_attorney(claims, driver_id)
        projection = "attorney"
    else:
        projection = _authorize_driver_or_staff(claims, driver_id)
    result = _public_projection(_snapshot(driver_id))
    result["projection"] = projection
    if projection in {"carrier", "attorney"}:
        # Summaries do not grant access to restricted source artifacts.
        result["components"].pop("substanceAlcohol", None)
        result["restricted_components"] = ["substanceAlcohol"]
    return result


@router.get("/drivers/{driver_id}/components")
def get_score_components(
    driver_id: str,
    authorization: Optional[str] = Header(None),
):
    result = get_score_for_driver(driver_id, authorization)
    return {
        "driver_id": driver_id,
        "components": result["components"],
        "restricted_components": result.get("restricted_components", []),
        "algorithm_version": result["algorithm_version"],
        "ruleset_version": result["ruleset_version"],
    }


@router.get("/carrier/summary")
def get_carrier_score_summary(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    db, actor_id, organization_id = _carrier_context(claims)
    platform = PlatformService(db)
    memberships = platform.list_memberships(actor_id)
    if not any(
        item.organization_id == organization_id and item.status.value == "active"
        for item in memberships
    ):
        raise HTTPException(status_code=403, detail="Active Carrier membership required.")
    relationships = platform.list_organization_relationships(organization_id)
    visible: list[TipScoreSnapshot] = []
    for relationship in relationships:
        if relationship.status.value != "active":
            continue
        try:
            CarrierResolveService(db)._authorize(
                actor_id, organization_id, relationship.driver_principal_id
            )
        except PermissionError:
            continue
        visible.append(_snapshot(relationship.driver_principal_id))
    scores = sorted(item.score for item in visible)
    tiers = {tier: 0 for tier in ("ELITE", "PREFERRED", "STANDARD", "ELEVATED", "CRITICAL")}
    for item in visible:
        tiers[item.tier.value] += 1
    average = round(sum(scores) / len(scores)) if scores else None
    median = (
        scores[len(scores) // 2]
        if len(scores) % 2
        else round((scores[len(scores) // 2 - 1] + scores[len(scores) // 2]) / 2)
    ) if scores else None
    deltas = [
        item.score_delta for item in visible if item.score_delta is not None
    ]
    return {
        "organization_id": organization_id,
        "driver_count": len(visible),
        "average_score": average,
        "median_score": median,
        "tier_distribution": tiers,
        "low_confidence_count": sum(item.confidence_percent < 60 for item in visible),
        "critical_condition_count": sum(item.active_ceiling is not None for item in visible),
        "fleet_score_delta": (
            round(sum(deltas) / len(deltas)) if deltas else None
        ),
        "trend_driver_count": len(deltas),
        "drivers": [
            {
                "driver_id": item.driver_id,
                "score": item.score,
                "tier": item.tier.value,
                "status": item.status.value,
                "confidence_percent": item.confidence_percent,
                "confidence_label": item.confidence_label,
                "score_delta": item.score_delta,
                "data_as_of": item.data_as_of.isoformat(),
                "critical_condition": item.active_ceiling is not None,
            }
            for item in sorted(visible, key=lambda snapshot: snapshot.score)
        ],
        "publication_state": "shadow",
        "proprietary_notice": (
            "TIP Score is a proprietary Rig Resolve score, not an official FMCSA score."
        ),
    }


@router.get("/attorney/cases")
def list_attorney_score_cases(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    if claims.get("role") != "attorney":
        raise HTTPException(status_code=403, detail="Attorney role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    attorney_id = claims.get("attorney_id") or uid
    documents: dict[str, dict] = {}
    for field in ("assigned_attorney_id", "claimed_by"):
        for document in db.collection("tickets").where(field, "==", attorney_id).limit(100).stream():
            documents[document.id] = document.to_dict() or {}
    from app.services.case_lifecycle import mask_driver_name
    cases = []
    for ticket_id, case in documents.items():
        if case.get("tip_score_consent_on_file") is not True:
            continue
        status = str(case.get("attorney_status") or case.get("status") or "")
        if status.lower() in {"ticket closed", "outcome logged", "payout sent", "closed", "cancelled"}:
            continue
        cases.append({
            "ticket_id": ticket_id,
            "driver_name": mask_driver_name(
                case.get("driver_full_name") or case.get("driver_name")
            ),
            "violation": case.get("violation_category") or "Citation",
            "state": case.get("ticket_state"),
            "county": case.get("ticket_county"),
            "court_date": case.get("court_date"),
            "attorney_status": status or "Active",
            "tip_score_consent": True,
        })
    cases.sort(key=lambda item: str(item.get("court_date") or ""))
    return {"cases": cases, "count": len(cases)}


@router.get("/attorney/cases/{ticket_id}")
def get_attorney_case_score(
    ticket_id: str,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    _, driver_id = _attorney_case(claims, ticket_id)
    result = _public_projection(_snapshot(driver_id))
    result["projection"] = "attorney"
    result["components"].pop("substanceAlcohol", None)
    result["restricted_components"] = ["substanceAlcohol"]
    result["case_id"] = ticket_id
    return result


@router.post("/attorney/cases/{ticket_id}/simulations")
def simulate_attorney_case_score(
    ticket_id: str,
    body: AttorneySimulationRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    _, driver_id = _attorney_case(claims, ticket_id)
    current = _snapshot(driver_id)
    return {
        "case_id": ticket_id,
        "current_score": current.score,
        "projected_score": current.score,
        "estimated_delta": 0,
        "projection_status": "ESTIMATE",
        "scenario": body.scenario,
        "event_ids": body.event_ids,
        "assumptions": [
            "No verified disposition has been recorded for this simulation.",
            "Projected score—not guaranteed.",
        ],
    }


@router.get("/drivers/{driver_id}/history")
def get_score_history(
    driver_id: str,
    authorization: Optional[str] = Header(None),
):
    result = get_score_for_driver(driver_id, authorization)
    db = get_db()
    rows = (
        db.collection("tip_score_snapshots")
        .where("driver_id", "==", driver_id)
        .limit(100)
        .stream()
    )
    history = [TipScoreSnapshot.model_validate(row.to_dict()).model_dump(mode="json") for row in rows]
    if not history:
        history = [result]
    history.sort(key=lambda item: item["calculated_at"], reverse=True)
    return {"driver_id": driver_id, "history": history}


@router.post("/drivers/{driver_id}/recalculate", status_code=201)
def recalculate_score(
    driver_id: str,
    body: ScoreCalculationInput,
    authorization: Optional[str] = Header(None),
):
    """Create an immutable governed snapshot and advance the current pointer.

    Staff cannot directly edit a score. They provide the verified calculation
    inputs and evidence references; the authoritative calculator determines the
    result. Replaying identical inputs is idempotent.
    """
    claims = _claims(authorization)
    role = str(claims.get("role") or "")
    staff_role = str(claims.get("staff_role") or "")
    if role not in STAFF_ROLES and staff_role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    if body.driver_id != driver_id:
        raise HTTPException(status_code=422, detail="Driver ID does not match route.")
    if not body.evidence_ids:
        raise HTTPException(
            status_code=422,
            detail="At least one verified evidence reference is required.",
        )

    db = get_db()
    current_ref = db.collection("tip_score_current").document(driver_id)
    current_doc = current_ref.get()
    previous = (
        TipScoreSnapshot.model_validate(current_doc.to_dict())
        if current_doc.exists
        else None
    )
    governed_input = body.model_copy(
        update={"previous_score": previous.score if previous else body.previous_score}
    )
    snapshot = TipScoreCalculator().calculate(
        governed_input,
        supersedes_snapshot_id=previous.id if previous else None,
        calculated_by=_actor_id(claims),
    )
    payload = snapshot.model_dump(mode="python")
    snapshot_ref = db.collection("tip_score_snapshots").document(snapshot.id)
    existing = snapshot_ref.get()
    if existing.exists:
        stored = TipScoreSnapshot.model_validate(existing.to_dict())
        if stored.input_hash != snapshot.input_hash:
            raise HTTPException(status_code=409, detail="Snapshot identifier collision.")
        snapshot = stored
        payload = stored.model_dump(mode="python")
    else:
        snapshot_ref.create(payload)
    current_ref.set(payload)
    db.collection("tip_score_lifecycle").document(driver_id).set({
        "driver_id": driver_id,
        "snapshot_id": snapshot.id,
        "publication_state": "shadow",
        "score_status": snapshot.status.value,
        "reason": body.calculation_reason,
        "changed_by": _actor_id(claims),
        "updated_at": datetime.now(timezone.utc),
    })
    return snapshot.model_dump(mode="json")


class LifecycleRequest(BaseModel):
    target_state: Literal["shadow", "human_review", "published", "withdrawn"]
    reason: str = Field(min_length=10, max_length=2000)


@router.post("/drivers/{driver_id}/lifecycle")
def change_score_lifecycle(
    driver_id: str,
    body: LifecycleRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    role = str(claims.get("role") or "")
    staff_role = str(claims.get("staff_role") or "")
    if role not in STAFF_ROLES and staff_role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    if body.target_state == "published":
        raise HTTPException(
            status_code=409,
            detail="TIP Score publication is not authorized in this release.",
        )
    db = get_db()
    snapshot = _snapshot(driver_id)
    lifecycle_ref = db.collection("tip_score_lifecycle").document(driver_id)
    lifecycle_doc = lifecycle_ref.get()
    current_state = (
        (lifecycle_doc.to_dict() or {}).get("publication_state")
        if lifecycle_doc.exists
        else snapshot.publication_state
    )
    allowed = {
        "shadow": {"human_review", "withdrawn"},
        "human_review": {"shadow", "withdrawn"},
        "withdrawn": {"shadow", "human_review"},
    }
    if body.target_state != current_state and body.target_state not in allowed.get(current_state, set()):
        raise HTTPException(status_code=409, detail="Invalid TIP Score lifecycle transition.")
    actor_id = _actor_id(claims)
    now = datetime.now(timezone.utc)
    payload = {
        "driver_id": driver_id,
        "snapshot_id": snapshot.id,
        "publication_state": body.target_state,
        "score_status": snapshot.status.value,
        "reason": body.reason,
        "changed_by": actor_id,
        "updated_at": now,
    }
    lifecycle_ref.set(payload)
    db.collection("tip_score_lifecycle_events").document().set({
        **payload,
        "from_state": current_state,
        "to_state": body.target_state,
        "created_at": now,
    })
    return payload


class RollbackRequest(BaseModel):
    target_snapshot_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=10, max_length=2000)


@router.post("/drivers/{driver_id}/rollback")
def rollback_score(
    driver_id: str,
    body: RollbackRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    role = str(claims.get("role") or "")
    staff_role = str(claims.get("staff_role") or "")
    if role not in STAFF_ROLES and staff_role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    db = get_db()
    target_doc = db.collection("tip_score_snapshots").document(body.target_snapshot_id).get()
    if not target_doc.exists:
        raise HTTPException(status_code=404, detail="Score snapshot not found.")
    target = TipScoreSnapshot.model_validate(target_doc.to_dict())
    if target.driver_id != driver_id:
        raise HTTPException(status_code=404, detail="Score snapshot not found.")
    prior = _snapshot(driver_id)
    db.collection("tip_score_current").document(driver_id).set(
        target.model_dump(mode="python")
    )
    actor_id = _actor_id(claims)
    now = datetime.now(timezone.utc)
    lifecycle = {
        "driver_id": driver_id,
        "snapshot_id": target.id,
        "publication_state": "shadow",
        "score_status": target.status.value,
        "reason": body.reason,
        "changed_by": actor_id,
        "updated_at": now,
    }
    db.collection("tip_score_lifecycle").document(driver_id).set(lifecycle)
    db.collection("tip_score_rollback_events").document().set({
        **lifecycle,
        "from_snapshot_id": prior.id,
        "to_snapshot_id": target.id,
        "created_at": now,
    })
    return {
        "driver_id": driver_id,
        "from_snapshot_id": prior.id,
        "current_snapshot_id": target.id,
        "publication_state": "shadow",
    }


class SimulationRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=80)
    event_ids: list[str] = Field(default_factory=list, max_length=50)


class RecalculationRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)


@router.post("/drivers/{driver_id}/recalculation-requests", status_code=201)
def request_score_recalculation(
    driver_id: str,
    body: RecalculationRequest,
    authorization: Optional[str] = Header(None),
):
    """Queue a correction-driven recalculation without accepting score edits."""
    claims = _claims(authorization)
    role = str(claims.get("role") or "")
    staff_role = str(claims.get("staff_role") or "")
    if role not in STAFF_ROLES and staff_role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    actor_id = _actor_id(claims)
    current = _snapshot(driver_id)
    payload = {
        "driver_id": driver_id,
        "requested_by": actor_id,
        "reason": body.reason,
        "evidence_ids": sorted(set(body.evidence_ids)),
        "current_snapshot_id": current.id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    }
    ref = get_db().collection("tip_score_recalculation_requests").document()
    ref.set(payload)
    return {"id": ref.id, **payload}


@router.post("/drivers/{driver_id}/simulations")
def simulate_score(
    driver_id: str,
    body: SimulationRequest,
    authorization: Optional[str] = Header(None),
):
    current = get_score_for_driver(driver_id, authorization)
    return {
        "current_score": current["score"],
        "projected_score": current["score"],
        "estimated_delta": 0,
        "projection_status": "ESTIMATE",
        "scenario": body.scenario,
        "event_ids": body.event_ids,
        "assumptions": [
            "No verified score-affecting event transformation is available for this scenario.",
            "Projected score—not guaranteed.",
        ],
    }


class DisputeRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    event_ids: list[str] = Field(default_factory=list, max_length=50)


@router.post("/drivers/{driver_id}/disputes", status_code=201)
def submit_dispute(
    driver_id: str,
    body: DisputeRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    _authorize_driver_or_staff(claims, driver_id)
    actor_id = _actor_id(claims)
    db = get_db()
    payload = {
        "driver_id": driver_id,
        "actor_id": actor_id,
        "reason": body.reason,
        "event_ids": body.event_ids,
        "status": "submitted",
        "created_at": datetime.now(timezone.utc),
    }
    ref = db.collection("tip_score_disputes").document()
    ref.set(payload)
    snapshot = _snapshot(driver_id)
    db.collection("tip_score_lifecycle").document(driver_id).set({
        "driver_id": driver_id,
        "snapshot_id": snapshot.id,
        "publication_state": "human_review",
        "score_status": TipScoreStatus.DISPUTED.value,
        "reason": f"Dispute {ref.id} submitted",
        "changed_by": actor_id,
        "updated_at": datetime.now(timezone.utc),
    })
    return {"id": ref.id, **payload}
