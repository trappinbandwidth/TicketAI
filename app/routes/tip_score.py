"""Role-filtered API projections for the authoritative TIP Score service."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

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
from app.services.tip_score import TipScoreCalculator, TipScoreSnapshot, thin_file_input


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
    if current.exists:
        return TipScoreSnapshot.model_validate(current.to_dict())
    return TipScoreCalculator().calculate(
        thin_file_input(driver_id, data_as_of=datetime.now(timezone.utc))
    )


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
    organization_id = organization_id_for_profile(uid)
    CarrierResolveService(db)._authorize(
        principal_id_for_uid(uid), organization_id, driver_id
    )


def _carrier_context(claims: dict):
    if claims.get("role") != "carrier":
        raise HTTPException(status_code=403, detail="Carrier role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    actor_id = principal_id_for_uid(uid)
    organization_id = organization_id_for_profile(uid)
    return db, actor_id, organization_id


def _authorize_attorney(claims: dict, driver_id: str) -> None:
    if claims.get("role") != "attorney":
        raise HTTPException(status_code=403, detail="Attorney role required.")
    db = get_db()
    uid = claims.get("uid") or claims.get("sub")
    attorney_id = claims.get("attorney_id") or uid
    # Attorney access is tied to an active case and explicit client consent.
    matches = (
        db.collection("cases")
        .where("driver_id", "==", driver_id)
        .where("attorney_id", "==", attorney_id)
        .limit(5)
        .stream()
    )
    allowed = any(
        (doc.to_dict() or {}).get("consent_on_file") is True
        and (doc.to_dict() or {}).get("status") not in {"closed", "cancelled"}
        for doc in matches
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Active client case and score-sharing consent required.",
        )


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
    return {
        "organization_id": organization_id,
        "driver_count": len(visible),
        "average_score": average,
        "median_score": median,
        "tier_distribution": tiers,
        "low_confidence_count": sum(item.confidence_percent < 60 for item in visible),
        "critical_condition_count": sum(item.active_ceiling is not None for item in visible),
        "publication_state": "shadow",
        "proprietary_notice": (
            "TIP Score is a proprietary Rig Resolve score, not an official FMCSA score."
        ),
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


class SimulationRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=80)
    event_ids: list[str] = Field(default_factory=list, max_length=50)


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
    return {"id": ref.id, **payload}
