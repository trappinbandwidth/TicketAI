"""Feature-flagged WP-05 governed intelligence APIs."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.platform.intelligence_service import IntelligenceService
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import verify_firebase_token


router = APIRouter(prefix="/intelligence", tags=["tip-os-intelligence"])


class SignalDispositionRequest(BaseModel):
    action: str = Field(pattern="^(confirm|dismiss|snooze|escalate)$")
    reason: str = Field(min_length=1, max_length=1000)
    snoozed_until: Optional[datetime] = None


class RecommendationReviewRequest(BaseModel):
    approved: bool
    reason: str = Field(min_length=1, max_length=1000)


def _claims(authorization: Optional[str]) -> dict:
    if os.getenv("TIP_OS_INTELLIGENCE_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Intelligence APIs are not enabled.")
    return verify_firebase_token(authorization)


def _actor(claims: dict) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _service() -> IntelligenceService:
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Intelligence store unavailable.")
    return IntelligenceService(firebase_service._firestore_client)


@router.get("/me")
def get_my_intelligence(authorization: Optional[str] = Header(None)):
    actor_id = _actor(_claims(authorization))
    service = _service()
    return {
        "signals": service.list_signals(actor_id),
        "recommendations": service.list_recommendations(actor_id),
    }


@router.post("/signals/{signal_id}/disposition")
def disposition_signal(
    signal_id: str,
    body: SignalDispositionRequest,
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor(_claims(authorization))
    service = _service()
    matching = {item.id for item in service.list_signals(actor_id)}
    if signal_id not in matching:
        raise HTTPException(status_code=404, detail="Signal not found.")
    try:
        return {"signal": service.disposition_signal(
            actor_id, signal_id, body.action, body.reason, body.snoozed_until
        )}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/recommendations/{recommendation_id}/review")
def review_recommendation(
    recommendation_id: str,
    body: RecommendationReviewRequest,
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor(_claims(authorization))
    service = _service()
    matching = {item.id for item in service.list_recommendations(actor_id)}
    if recommendation_id not in matching:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    return {"recommendation": service.review_recommendation(
        actor_id, recommendation_id, body.approved, body.reason
    )}
