"""Human-governed entity resolution; never auto-merges canonical identities."""
from __future__ import annotations

import hashlib
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.platform.models import utc_now


class MatchCandidate(BaseModel):
    canonical_id: str
    score: float = Field(ge=0, le=1)
    evidence: list[str] = Field(min_length=1)
    conflicting_fields: list[str] = Field(default_factory=list)


class ResolutionCaseCreate(BaseModel):
    tenant_id: Optional[str] = None
    entity_type: Literal["principal", "organization", "record_owner"]
    source_system: str
    source_record_reference: str
    source_fingerprint: str = Field(min_length=16)
    candidates: list[MatchCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_candidates(self):
        ids = [item.canonical_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate canonical candidates are not allowed.")
        return self


class ResolutionDecision(BaseModel):
    action: Literal["link", "create_new", "reject"]
    canonical_id: Optional[str] = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def link_requires_target(self):
        if self.action == "link" and not self.canonical_id:
            raise ValueError("Link decisions require a canonical target.")
        return self


class EntityResolutionService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _stable_id(body: ResolutionCaseCreate):
        key = f"{body.source_system}|{body.entity_type}|{body.source_record_reference}|{body.source_fingerprint}"
        return f"erc_{hashlib.sha256(key.encode()).hexdigest()[:40]}"

    def open_case(self, body: ResolutionCaseCreate, actor_id: str):
        case_id = self._stable_id(body)
        ref = self.db.collection("entity_resolution_cases").document(case_id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            return snapshot.to_dict(), False
        value = {
            "id": case_id,
            **body.model_dump(),
            "status": "pending_review",
            "created_by": actor_id,
            "created_at": utc_now().isoformat(),
        }
        ref.set(value)
        return value, True

    def decide(self, case_id: str, body: ResolutionDecision, actor_id: str):
        ref = self.db.collection("entity_resolution_cases").document(case_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Resolution case not found.")
        current = snapshot.to_dict() or {}
        if current.get("status") == "resolved":
            existing = current.get("decision") or {}
            if existing.get("action") == body.action and existing.get("canonical_id") == body.canonical_id:
                return current, False
            raise RuntimeError("Resolution case already has a different decision.")
        if body.action == "link":
            candidate_ids = {item.get("canonical_id") for item in current.get("candidates", [])}
            if body.canonical_id not in candidate_ids:
                raise ValueError("Link target is not an evaluated candidate.")
        decision = {
            "id": f"erd_{uuid.uuid4().hex}",
            **body.model_dump(),
            "decided_by": actor_id,
            "decided_at": utc_now().isoformat(),
        }
        updated = {**current, "status": "resolved", "decision": decision}
        ref.set(updated)
        self.db.collection("audit_events").document(decision["id"]).set({
            "id": decision["id"],
            "event_type": "entity_resolution.decided",
            "actor_id": actor_id,
            "entity_type": "entity_resolution_case",
            "entity_id": case_id,
            "payload": {
                "action": body.action,
                "canonical_id": body.canonical_id,
                "reason": body.reason,
            },
            "created_at": decision["decided_at"],
        })
        return updated, True
