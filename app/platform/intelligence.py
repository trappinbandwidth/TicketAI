"""WP-05 governed intelligence contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.platform.models import utc_now


class Evidence(BaseModel):
    source_type: str
    source_id: str
    field: Optional[str] = None
    quote: Optional[str] = Field(default=None, max_length=500)
    retrieved_at: datetime
    source_version: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class SignalStatus(str, Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    ESCALATED = "escalated"


class Signal(BaseModel):
    id: str
    signal_type: str
    subject_principal_id: str
    resource_type: str
    resource_id: str
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    confidence: float = Field(ge=0, le=1)
    source_freshness_at: datetime
    explanation: str = Field(min_length=1, max_length=2000)
    impact_dimensions: list[str] = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    status: SignalStatus = SignalStatus.OPEN
    snoozed_until: Optional[datetime] = None
    disposition_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RecommendationStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Recommendation(BaseModel):
    id: str
    recommendation_type: str
    subject_principal_id: str
    resource_type: str
    resource_id: str
    action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    alternatives: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    required_approver_role: str
    status: RecommendationStatus = RecommendationStatus.PENDING_REVIEW
    educational_disclosure: str = (
        "Educational information only; this is not legal advice or a guaranteed outcome."
    )
    approved_by: Optional[str] = None
    reviewer_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RuleEvaluation(BaseModel):
    id: str
    rule_id: str
    rule_version: str
    input_hash: str
    outcome: str
    facts: dict[str, Any]
    explanation: str
    evaluated_at: datetime = Field(default_factory=utc_now)


class IntelligenceRun(BaseModel):
    id: str
    purpose: str
    provider: str
    model: str
    model_snapshot: Optional[str] = None
    prompt_version: str
    knowledge_versions: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    input_hash: str
    output_hash: str
    rule_evaluation_ids: list[str] = Field(default_factory=list)
    reviewer_disposition: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeSource(BaseModel):
    id: str
    title: str
    publisher: str
    version: str
    publication_date: datetime
    effective_at: Optional[datetime] = None
    status: str = Field(default="draft", pattern="^(draft|approved|retired)$")
    source_url: Optional[str] = None
    content_sha256: str
    applicability_tags: list[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class ModelRegistration(BaseModel):
    id: str
    provider: str = Field(pattern="^(anthropic|openai|rules|internal)$")
    model: str
    snapshot: Optional[str] = None
    purpose: str
    status: str = Field(default="evaluation", pattern="^(evaluation|approved|paused|retired)$")
    prompt_versions: list[str] = Field(default_factory=list)
    approval_thresholds: dict[str, float] = Field(default_factory=dict)
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
