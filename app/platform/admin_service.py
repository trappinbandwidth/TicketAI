"""WP-09 governed operations queues and configuration registries."""
from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from typing import Literal, Optional

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


class CarrierAuthorityDecision(BaseModel):
    decision: Literal["approve", "reject", "request_more_information"]
    reason: str = Field(min_length=1, max_length=1000)
    support_ticket_id: str = Field(min_length=1, max_length=120)


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

    def list_carrier_authority_claims(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ):
        claims = self._all("carrier_authority_claims", limit=500)
        evidence = self._all("carrier_authority_evidence", limit=1000)
        rows = []
        for claim in claims:
            if status and claim.get("status") != status:
                continue
            claim_evidence = [
                item for item in evidence
                if item.get("claim_id") == claim.get("id")
            ]
            rows.append({
                "id": claim.get("id"),
                "carrier_profile_id": claim.get("carrier_profile_id"),
                "organization_id": claim.get("organization_id"),
                "dot_number": claim.get("dot_number"),
                "status": claim.get("status"),
                "dot_claim_status": claim.get("dot_claim_status"),
                "fmcsa_snapshot_id": claim.get("fmcsa_snapshot_id"),
                "evidence_count": len(claim_evidence),
                "evidence_methods": sorted({
                    item.get("evidence_method")
                    for item in claim_evidence
                    if item.get("evidence_method")
                }),
                "evidence": [{
                    "id": item.get("id"),
                    "evidence_method": item.get("evidence_method"),
                    "file_name": item.get("file_name"),
                    "content_type": item.get("content_type"),
                    "size_bytes": item.get("size_bytes"),
                    "status": item.get("status"),
                    "created_at": item.get("created_at"),
                } for item in claim_evidence],
                "created_at": claim.get("created_at"),
                "updated_at": claim.get("updated_at"),
                "decision_reason": claim.get("decision_reason"),
            })
        rows.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return rows[:limit]

    def carrier_authority_evidence_for_review(
        self,
        claim_id: str,
        evidence_id: str,
    ):
        claim = self.db.collection("carrier_authority_claims").document(claim_id).get()
        if not getattr(claim, "exists", False):
            raise KeyError("Carrier authority claim not found.")
        evidence = (
            self.db.collection("carrier_authority_evidence")
            .document(evidence_id)
            .get()
        )
        if not getattr(evidence, "exists", False):
            raise KeyError("Carrier authority evidence not found.")
        value = evidence.to_dict() or {}
        if value.get("claim_id") != claim_id or not value.get("storage_path"):
            raise KeyError("Carrier authority evidence not found.")
        return value

    def _set_atomically(self, writes: list[tuple[object, dict]]):
        if hasattr(self.db, "batch"):
            batch = self.db.batch()
            for reference, value in writes:
                batch.set(reference, value, merge=True)
            batch.commit()
            return
        for reference, value in writes:
            reference.set(value, merge=True)

    def decide_carrier_authority(
        self,
        actor_id: str,
        claim_id: str,
        body: CarrierAuthorityDecision,
    ):
        claim_ref = self.db.collection("carrier_authority_claims").document(claim_id)
        snapshot = claim_ref.get()
        if not getattr(snapshot, "exists", False):
            raise KeyError("Carrier authority claim not found.")
        claim = snapshot.to_dict() or {}
        if (
            claim.get("decision") == body.decision
            and claim.get("decision_reason") == body.reason
            and claim.get("support_ticket_id") == body.support_ticket_id
        ):
            return {**claim, "duplicate": True}

        status = claim.get("status")
        if status in {"verified", "rejected"}:
            raise RuntimeError("Carrier authority claim already has a terminal decision.")

        carrier_id = claim.get("carrier_profile_id")
        organization_id = claim.get("organization_id")
        dot_number = claim.get("dot_number")
        if not carrier_id or not organization_id or not dot_number:
            raise RuntimeError("Carrier authority claim identity is incomplete.")

        carrier_ref = self.db.collection("carriers").document(carrier_id)
        organization_ref = self.db.collection("organizations").document(organization_id)
        dot_ref = self.db.collection("carrier_dot_claims").document(dot_number)
        carrier = carrier_ref.get()
        organization = organization_ref.get()
        dot_snapshot = dot_ref.get()
        if not getattr(carrier, "exists", False) or not getattr(organization, "exists", False):
            raise RuntimeError("Carrier authority projections are incomplete.")
        carrier_value = carrier.to_dict() or {}
        organization_value = organization.to_dict() or {}
        if (
            carrier_value.get("organization_id") != organization_id
            or str(carrier_value.get("dot_number") or "") != str(dot_number)
        ):
            raise RuntimeError("Carrier authority projections do not reconcile.")

        evidence = [
            item for item in self._all("carrier_authority_evidence", limit=1000)
            if item.get("claim_id") == claim_id and item.get("status") == "received"
        ]
        if body.decision == "approve":
            if status != "pending_review" or not evidence:
                raise RuntimeError("Received authority evidence is required before approval.")
            if not getattr(dot_snapshot, "exists", False):
                raise RuntimeError("USDOT reservation is missing.")
            dot_claim = dot_snapshot.to_dict() or {}
            if (
                dot_claim.get("claimant_carrier_id") != carrier_id
                or dot_claim.get("status") == "duplicate_disputed"
                or claim.get("dot_claim_status") == "duplicate_disputed"
                or carrier_value.get("dot_claim_status") == "duplicate_disputed"
                or carrier_value.get("tenant_status") == "quarantined"
                or organization_value.get("tenant_status") == "quarantined"
            ):
                raise RuntimeError("Duplicate or disputed USDOT claims cannot be approved.")

        now = utc_now()
        version = int(claim.get("decision_version", 0)) + 1
        next_status = {
            "approve": "verified",
            "reject": "rejected",
            "request_more_information": "pending_evidence",
        }[body.decision]
        decision_patch = {
            "status": next_status,
            "decision": body.decision,
            "decision_reason": body.reason,
            "support_ticket_id": body.support_ticket_id,
            "decided_by": actor_id,
            "decided_at": now.isoformat(),
            "decision_version": version,
            "updated_at": now,
        }
        writes = [(claim_ref, decision_patch)]
        if body.decision == "approve":
            writes.extend([
                (carrier_ref, {
                    "account_authority_status": "verified",
                    "verification_status": "verified",
                    "dot_claim_status": "verified",
                    "tenant_status": "active",
                    "updated_at": now,
                }),
                (organization_ref, {
                    "verification_status": "verified",
                    "tenant_status": "active",
                    "updated_at": now,
                }),
                (dot_ref, {
                    "status": "verified",
                    "verified_at": now,
                    "verified_by": actor_id,
                }),
            ])
        elif body.decision == "reject":
            writes.extend([
                (carrier_ref, {
                    "account_authority_status": "rejected",
                    "verification_status": "unverified",
                    "updated_at": now,
                }),
                (organization_ref, {
                    "verification_status": "unverified",
                    "updated_at": now,
                }),
            ])
        else:
            writes.extend([
                (carrier_ref, {
                    "account_authority_status": "pending_verification",
                    "verification_status": "unverified",
                    "updated_at": now,
                }),
                (organization_ref, {
                    "verification_status": "unverified",
                    "updated_at": now,
                }),
            ])
        audit_digest = hashlib.sha256(
            f"{claim_id}:{version}:{body.decision}".encode("utf-8")
        ).hexdigest()[:32]
        audit_id = f"audit_authority_{audit_digest}"
        audit_ref = self.db.collection("audit_events").document(audit_id)
        writes.append((audit_ref, {
            "id": audit_id,
            "event_type": f"carrier.authority_{body.decision}",
            "actor_id": actor_id,
            "entity_type": "carrier_authority_claim",
            "entity_id": claim_id,
            "payload": {
                "decision": body.decision,
                "reason": body.reason,
                "support_ticket_id": body.support_ticket_id,
                "dot_number": dot_number,
                "evidence_count": len(evidence),
            },
            "created_at": now.isoformat(),
        }))
        self._set_atomically(writes)
        return {
            **claim,
            **decision_patch,
            "duplicate": False,
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
