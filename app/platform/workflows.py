"""WP-04 deterministic workflow, task, deadline, and notification contracts."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.platform.models import utc_now


class WorkflowType(str, Enum):
    TICKET = "ticket"
    DATAQS = "dataqs"
    CREDENTIAL = "credential"
    CASE = "case"


class TaskStatus(str, Enum):
    OPEN = "open"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    WAIVED = "waived"
    CANCELLED = "cancelled"


class WorkflowTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    assignee_principal_id: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    dependency_ids: list[str] = Field(default_factory=list)
    requires_evidence: bool = False


class WorkflowTask(WorkflowTaskCreate):
    id: str
    workflow_id: str
    status: TaskStatus = TaskStatus.OPEN
    completion_evidence_ids: list[str] = Field(default_factory=list)
    waiver_reason: Optional[str] = None
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowHistory(BaseModel):
    from_state: Optional[str] = None
    to_state: str
    actor_principal_id: str
    reason: Optional[str] = None
    approval_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowInstance(BaseModel):
    id: str
    workflow_type: WorkflowType
    definition_version: str
    subject_principal_id: str
    resource_type: str
    resource_id: str
    current_state: str
    correlation_id: str
    deadline_at: Optional[datetime] = None
    deadline_basis: Optional[str] = None
    deadline_source_ref: Optional[str] = None
    deadline_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    tenant_id: Optional[str] = None
    history: list[WorkflowHistory] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Approval(BaseModel):
    id: str
    workflow_id: str
    action: str
    approver_principal_id: str
    status: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=1, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)


class NotificationPreferences(BaseModel):
    principal_id: str
    in_app: bool = True
    email: bool = True
    sms: bool = False
    push: bool = False
    urgent_deadline_override: bool = False
    disclosure_version: str = "notifications-v1"
    updated_at: datetime = Field(default_factory=utc_now)


class Alert(BaseModel):
    id: str
    principal_id: str
    workflow_id: Optional[str] = None
    severity: str = Field(pattern="^(info|warning|urgent)$")
    title: str
    message: str
    channels: list[str]
    status: str = "pending"
    dedupe_key: str
    correlation_id: str
    created_at: datetime = Field(default_factory=utc_now)


WORKFLOW_DEFINITIONS = {
    WorkflowType.TICKET: {
        "version": "ticket-v1",
        "initial": "intake",
        "transitions": {
            "intake": {"extraction_review"},
            "extraction_review": {"intelligence_ready", "rejected"},
            "intelligence_ready": {"attorney_matching", "closed"},
            "attorney_matching": {"engagement_pending", "coverage_exception"},
            "engagement_pending": {"engaged", "coverage_exception"},
            "engaged": {"resolved"},
            "resolved": {"closed"},
        },
        "approval_actions": {"engaged", "closed"},
    },
    WorkflowType.DATAQS: {
        "version": "dataqs-v1",
        "initial": "candidate",
        "transitions": {
            "candidate": {"evidence_collection", "dismissed"},
            "evidence_collection": {"package_review"},
            "package_review": {"approved", "changes_requested"},
            "changes_requested": {"evidence_collection"},
            "approved": {"submitted"},
            "submitted": {"response_received"},
            "response_received": {"reconciled"},
        },
        "approval_actions": {"approved", "submitted"},
    },
    WorkflowType.CREDENTIAL: {
        "version": "credential-v1",
        "initial": "current",
        "transitions": {
            "current": {"expiring", "expired"},
            "expiring": {"replacement_requested", "expired"},
            "replacement_requested": {"replacement_review"},
            "replacement_review": {"current", "changes_requested"},
            "changes_requested": {"replacement_requested"},
            "expired": {"replacement_requested"},
        },
        "approval_actions": {"current"},
    },
    WorkflowType.CASE: {
        "version": "case-v1",
        "initial": "new",
        "transitions": {
            "new": {"conflict_check"},
            "conflict_check": {"offered", "conflict_rejected"},
            "offered": {"engagement_pending", "declined"},
            "engagement_pending": {"active", "declined"},
            "active": {"outcome_review"},
            "outcome_review": {"closed"},
        },
        "approval_actions": {"active", "closed"},
    },
}


def new_workflow(
    workflow_type: WorkflowType,
    subject_id: str,
    resource_type: str,
    resource_id: str,
    actor_id: str,
    **kwargs,
) -> WorkflowInstance:
    definition = WORKFLOW_DEFINITIONS[workflow_type]
    state = definition["initial"]
    return WorkflowInstance(
        id=f"wfl_{uuid.uuid4().hex}",
        workflow_type=workflow_type,
        definition_version=definition["version"],
        subject_principal_id=subject_id,
        resource_type=resource_type,
        resource_id=resource_id,
        current_state=state,
        correlation_id=f"wf-{uuid.uuid4().hex}",
        history=[WorkflowHistory(to_state=state, actor_principal_id=actor_id)],
        **kwargs,
    )
