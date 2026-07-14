"""Recommendation Contract writer.

Recommendations give product surfaces a stable way to show explainable
intelligence without coupling directly to individual AI agents.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.models.response import AttorneyMatch, Recommendation, RecommendationEvidence
from app.services.event_service import write_event

logger = logging.getLogger(__name__)


def _server_timestamp():
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        return SERVER_TIMESTAMP
    except Exception:
        return None


def _db():
    from app.services.firebase_service import _firestore_client, _init

    _init()
    return _firestore_client


def build_recommendation(
    rec_type: str,
    subject_type: str,
    subject_id: str,
    audience: str,
    summary: str,
    why_it_matters: str,
    recommended_action: str,
    confidence: float,
    severity: str,
    requires_human_approval: bool,
    evidence: Optional[list[dict]] = None,
    reasoning_summary: str = "",
    created_by: str = "system",
    status: str = "pending_review",
) -> Recommendation:
    return Recommendation(
        id=f"rec_{uuid.uuid4().hex}",
        type=rec_type,
        subject_type=subject_type,
        subject_id=subject_id,
        audience=audience,
        summary=summary,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        confidence=confidence,
        severity=severity,
        status=status,
        requires_human_approval=requires_human_approval,
        evidence=[RecommendationEvidence(**item) for item in (evidence or [])],
        reasoning_summary=reasoning_summary,
        created_by=created_by,
        created_at=_server_timestamp(),
    )


def create_recommendation(recommendation: Recommendation) -> str:
    """Persist a recommendation and emit recommendation.created. Returns id or empty string."""
    try:
        db = _db()
        if db is None:
            logger.warning("[recommendation] Firestore unavailable rec=%s", recommendation.id)
            return ""

        data = recommendation.model_dump()
        db.collection("recommendations").document(recommendation.id).set(data)
        write_event(
            event_type="recommendation.created",
            actor_type="system",
            actor_id=None,
            entity_type=recommendation.subject_type,
            entity_id=recommendation.subject_id,
            source="system",
            payload={
                "recommendation_id": recommendation.id,
                "type": recommendation.type,
                "audience": recommendation.audience,
                "severity": recommendation.severity,
            },
        )
        return recommendation.id
    except Exception as exc:
        logger.warning("[recommendation] write failed rec=%s: %s", recommendation.id, exc)
        return ""


def create_court_deadline_recommendation(
    ticket_id: str,
    urgency_level: Optional[str],
    urgency_reason: Optional[str],
    court_date: Optional[str],
) -> str:
    if not urgency_level or urgency_level.upper() not in {"CRITICAL", "HIGH"}:
        return ""

    severity = "critical" if urgency_level.upper() == "CRITICAL" else "high"
    recommendation = build_recommendation(
        rec_type="court_deadline_warning",
        subject_type="ticket",
        subject_id=ticket_id,
        audience="staff",
        summary=f"This ticket needs {urgency_level.lower()} deadline attention.",
        why_it_matters="Court deadlines can limit defense options and require fast attorney assignment.",
        recommended_action="Prioritize review and assign or confirm attorney coverage immediately.",
        confidence=0.9,
        severity=severity,
        requires_human_approval=True,
        evidence=[{
            "source_type": "ai_extraction",
            "source_id": ticket_id,
            "field": "Court_Date__c",
            "quote": court_date or "",
            "confidence": 0.8,
        }],
        reasoning_summary=urgency_reason or "Urgency router identified a near-term court deadline.",
        created_by="legal_intelligence",
    )
    return create_recommendation(recommendation)


def create_attorney_match_recommendation(ticket_id: str, match: Optional[AttorneyMatch]) -> str:
    if not match:
        return ""

    recommendation = build_recommendation(
        rec_type="attorney_match_recommendation",
        subject_type="ticket",
        subject_id=ticket_id,
        audience="staff",
        summary=f"{match.name} is the strongest current attorney match for this ticket.",
        why_it_matters="Fast, explainable attorney matching helps move eligible cases out of AI Review.",
        recommended_action="Review the match and assign or request quotes from the ranked attorneys.",
        confidence=0.85 if match.match_type == "county" else 0.72,
        severity="medium",
        requires_human_approval=True,
        evidence=[
            {
                "source_type": "attorney_profile",
                "source_id": match.attorney_id,
                "field": "match_type",
                "quote": match.match_type,
                "confidence": 1.0 if match.match_type == "county" else 0.8,
            },
            {
                "source_type": "attorney_stats",
                "source_id": match.attorney_id,
                "field": "win_rate",
                "quote": f"{round(match.win_rate * 100)}%",
                "confidence": 0.8,
            },
        ],
        reasoning_summary=(
            "Team Quest selected this attorney from available matches using "
            "state/county coverage and available attorney profile signals."
        ),
        created_by="legal_intelligence",
    )
    return create_recommendation(recommendation)
