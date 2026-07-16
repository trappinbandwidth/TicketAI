"""Governed signal, recommendation, rule, and model-run persistence."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from app.platform.intelligence import (
    IntelligenceRun,
    KnowledgeSource,
    ModelRegistration,
    Recommendation,
    RecommendationStatus,
    RuleEvaluation,
    Signal,
    SignalStatus,
)
from app.platform.models import utc_now


def stable_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class IntelligenceService:
    def __init__(self, db):
        self.db = db

    def _audit(self, actor_id: str, event_type: str, entity_type: str, entity_id: str, payload=None):
        event_id = f"audit_{uuid.uuid4().hex}"
        self.db.collection("audit_events").document(event_id).set({
            "id": event_id, "actor_id": actor_id, "event_type": event_type,
            "entity_type": entity_type, "entity_id": entity_id, "payload": payload or {},
            "created_at": utc_now().isoformat(),
        })

    def create_signal(self, signal: Signal):
        self.db.collection("signals").document(signal.id).set(signal.model_dump(mode="json"))
        self._audit("system", "signal.created", "signal", signal.id)
        return signal

    def list_signals(self, subject_id: str):
        return [
            Signal.model_validate(item.to_dict())
            for item in self.db.collection("signals").where(
                "subject_principal_id", "==", subject_id
            ).stream()
        ]

    def disposition_signal(self, actor_id: str, signal_id: str, action: str, reason: str, snoozed_until: datetime | None = None):
        ref = self.db.collection("signals").document(signal_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Signal not found.")
        signal = Signal.model_validate(snapshot.to_dict())
        mapping = {
            "confirm": SignalStatus.CONFIRMED,
            "dismiss": SignalStatus.DISMISSED,
            "snooze": SignalStatus.SNOOZED,
            "escalate": SignalStatus.ESCALATED,
        }
        if action not in mapping:
            raise ValueError("Unsupported signal disposition.")
        if action == "snooze" and not snoozed_until:
            raise ValueError("Snooze requires an end time.")
        signal.status = mapping[action]
        signal.snoozed_until = snoozed_until
        signal.disposition_reason = reason
        signal.updated_at = utc_now()
        ref.set(signal.model_dump(mode="json"))
        self._audit(actor_id, "signal.dispositioned", "signal", signal.id, {
            "action": action, "reason": reason,
        })
        return signal

    def create_recommendation(self, recommendation: Recommendation):
        self.db.collection("governed_recommendations").document(recommendation.id).set(
            recommendation.model_dump(mode="json")
        )
        self._audit("system", "recommendation.created", "recommendation", recommendation.id)
        return recommendation

    def list_recommendations(self, subject_id: str):
        return [
            Recommendation.model_validate(item.to_dict())
            for item in self.db.collection("governed_recommendations").where(
                "subject_principal_id", "==", subject_id
            ).stream()
        ]

    def review_recommendation(self, actor_id: str, recommendation_id: str, approved: bool, reason: str):
        ref = self.db.collection("governed_recommendations").document(recommendation_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Recommendation not found.")
        recommendation = Recommendation.model_validate(snapshot.to_dict())
        if recommendation.status != RecommendationStatus.PENDING_REVIEW:
            return recommendation
        recommendation.status = (
            RecommendationStatus.APPROVED if approved else RecommendationStatus.REJECTED
        )
        recommendation.approved_by = actor_id if approved else None
        recommendation.reviewer_reason = reason
        recommendation.updated_at = utc_now()
        ref.set(recommendation.model_dump(mode="json"))
        self._audit(actor_id, "recommendation.reviewed", "recommendation", recommendation.id, {
            "status": recommendation.status.value, "reason": reason,
        })
        return recommendation

    def evaluate_rule(self, rule_id: str, rule_version: str, facts: dict, evaluator):
        outcome, explanation = evaluator(facts)
        evaluation = RuleEvaluation(
            id=f"rule_{uuid.uuid4().hex}",
            rule_id=rule_id,
            rule_version=rule_version,
            input_hash=stable_hash(facts),
            outcome=outcome,
            facts=facts,
            explanation=explanation,
        )
        self.db.collection("rule_evaluations").document(evaluation.id).set(
            evaluation.model_dump(mode="json")
        )
        return evaluation

    def record_run(self, **kwargs):
        run = IntelligenceRun(id=f"irun_{uuid.uuid4().hex}", **kwargs)
        if not run.rule_evaluation_ids:
            raise ValueError("Deterministic rule evaluation must precede generative reasoning.")
        self.db.collection("intelligence_runs").document(run.id).set(run.model_dump(mode="json"))
        return run

    def publish_knowledge(self, actor_id: str, source: KnowledgeSource):
        if source.status == "approved" and not source.approved_by:
            source.approved_by = actor_id
        self.db.collection("knowledge_sources").document(source.id).set(
            source.model_dump(mode="json")
        )
        return source

    def register_model(self, actor_id: str, registration: ModelRegistration):
        if registration.status == "approved" and not registration.approved_by:
            registration.approved_by = actor_id
        registration.updated_at = utc_now()
        self.db.collection("model_registry").document(registration.id).set(
            registration.model_dump(mode="json")
        )
        self._audit(actor_id, "model.registered", "model_registration", registration.id, {
            "provider": registration.provider,
            "model": registration.model,
            "status": registration.status,
        })
        return registration
