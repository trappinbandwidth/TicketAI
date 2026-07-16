"""WP-09 governed operations queues and configuration registries."""
from __future__ import annotations

import uuid
from datetime import timedelta

from pydantic import BaseModel, Field

from app.platform.models import utc_now


class FeatureFlagUpdate(BaseModel):
    key: str = Field(pattern="^[A-Z0-9_]{3,120}$")
    enabled: bool
    environment: str = Field(pattern="^(development|staging|production)$")
    tenant_ids: list[str] = Field(default_factory=list)
    cohort_ids: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class PrivilegedAccessRequest(BaseModel):
    purpose: str = Field(min_length=1, max_length=200)
    support_ticket_id: str = Field(min_length=1, max_length=120)
    duration_minutes: int = Field(ge=5, le=60)
    resource_type: str
    resource_id: str


class AdminService:
    def __init__(self, db):
        self.db = db

    def _all(self, collection: str, limit=500):
        reference = self.db.collection(collection)
        if not hasattr(reference, "stream") and hasattr(reference, "rows"):
            return list(reference.rows.values())[:limit]
        query = reference.limit(limit) if hasattr(reference, "limit") else reference
        return [item.to_dict() or {} for item in query.stream()]

    def operations_summary(self):
        now = utc_now()
        documents = self._all("document_assets")
        jobs = self._all("document_jobs")
        workflows = self._all("workflow_instances")
        tasks = self._all("workflow_tasks")
        signals = self._all("signals")
        organizations = self._all("organizations")
        attorneys = self._all("attorneys")
        shadow = self._all("authorization_shadow_comparisons")
        integrations = self._all("integration_health")
        return {
            "queues": {
                "document_security": [
                    item for item in documents if item.get("status") in {"scan_pending", "unsafe", "failed"}
                ],
                "document_processing": [
                    item for item in jobs if item.get("status") == "failed"
                ],
                "overdue_tasks": [
                    item for item in tasks
                    if item.get("status") in {"open", "blocked"}
                    and item.get("due_at")
                    and str(item["due_at"]) < now.isoformat()
                ],
                "high_risk_signals": [
                    item for item in signals
                    if item.get("status") == "open" and item.get("severity") in {"high", "critical"}
                ],
                "organization_verification": [
                    item for item in organizations if item.get("verification_status") != "verified"
                ],
                "attorney_verification": [
                    item for item in attorneys
                    if (
                        item.get("verification_status")
                        or item.get("license_verification_status")
                        or item.get("bar_verification_status")
                    ) not in {"verified", "approved"}
                ],
                "authorization_mismatches": [
                    item for item in shadow
                    if not (item.get("comparison") or {}).get("match", False)
                ],
            },
            "counts": {
                "workflows": len(workflows),
                "open_tasks": sum(1 for item in tasks if item.get("status") in {"open", "blocked"}),
                "open_signals": sum(1 for item in signals if item.get("status") == "open"),
            },
            "integration_health": integrations,
        }

    def set_feature_flag(self, actor_id: str, body: FeatureFlagUpdate):
        ref = self.db.collection("feature_flags").document(body.key)
        snapshot = ref.get()
        current = snapshot.to_dict() or {} if getattr(snapshot, "exists", False) else {}
        current_version = int(current.get("version", 0))
        if current_version != body.expected_version:
            raise RuntimeError("Feature flag version conflict.")
        next_version = current_version + 1
        value = {
            **body.model_dump(exclude={"expected_version", "reason"}),
            "version": next_version,
            "updated_by": actor_id,
            "updated_at": utc_now().isoformat(),
        }
        ref.set(value)
        audit_id = f"audit_{uuid.uuid4().hex}"
        self.db.collection("audit_events").document(audit_id).set({
            "id": audit_id,
            "event_type": "feature_flag.updated",
            "actor_id": actor_id,
            "entity_type": "feature_flag",
            "entity_id": body.key,
            "payload": {
                "before": {key: current.get(key) for key in ("enabled", "version")},
                "after": {"enabled": body.enabled, "version": next_version},
                "reason": body.reason,
            },
            "created_at": utc_now().isoformat(),
        })
        return value

    def start_privileged_access(self, actor_id: str, body: PrivilegedAccessRequest):
        access_id = f"pac_{uuid.uuid4().hex}"
        started = utc_now()
        access = {
            "id": access_id,
            "actor_id": actor_id,
            **body.model_dump(),
            "status": "active",
            "started_at": started.isoformat(),
            "expires_at": (started + timedelta(minutes=body.duration_minutes)).isoformat(),
        }
        self.db.collection("privileged_access_sessions").document(access_id).set(access)
        self.db.collection("audit_events").document(access_id).set({
            "id": access_id,
            "event_type": "privileged_access.started",
            "actor_id": actor_id,
            "entity_type": body.resource_type,
            "entity_id": body.resource_id,
            "payload": {
                "purpose": body.purpose,
                "support_ticket_id": body.support_ticket_id,
                "expires_at": access["expires_at"],
            },
            "created_at": started.isoformat(),
        })
        return access
