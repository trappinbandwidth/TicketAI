"""WP-15 progressive rollout assessment and launch gates."""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.platform.models import utc_now


class LaunchAssessmentRequest(BaseModel):
    stage: Literal["dark", "internal", "cohort", "production"]
    environment: Literal["development", "staging", "production"]
    tenant_ids: list[str] = Field(default_factory=list)
    required_feature_flags: list[str] = Field(default_factory=list)
    maximum_shadow_mismatch_rate: float = Field(default=0.0, ge=0, le=1)
    maximum_failed_quality_gates: int = Field(default=0, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class LaunchService:
    def __init__(self, db):
        self.db = db

    def _rows(self, collection: str):
        reference = self.db.collection(collection)
        if hasattr(reference, "rows"):
            return list(reference.rows.values())
        return [item.to_dict() or {} for item in reference.limit(5000).stream()]

    def assess(self, body: LaunchAssessmentRequest, actor_id: str):
        blockers = []
        warnings = []
        flags = {item.get("key"): item for item in self._rows("feature_flags")}
        for key in body.required_feature_flags:
            flag = flags.get(key)
            if not flag:
                blockers.append({"code": "feature_flag_missing", "subject": key})
            elif flag.get("environment") != body.environment:
                blockers.append({"code": "feature_flag_environment_mismatch", "subject": key})
            elif body.stage == "dark" and flag.get("enabled"):
                blockers.append({"code": "dark_launch_flag_enabled", "subject": key})
            elif body.stage != "dark" and not flag.get("enabled"):
                blockers.append({"code": "required_feature_flag_disabled", "subject": key})

        migrations = self._rows("migration_runs")
        for run in migrations:
            if run.get("status") in {"failed", "blocked"}:
                blockers.append({"code": "migration_failed_or_blocked", "subject": run.get("id")})
            summary = run.get("summary") or {}
            if summary.get("conflicts", 0) or summary.get("invalid", 0):
                blockers.append({"code": "migration_conflicts_or_invalid", "subject": run.get("id")})

        reconciliations = (
            self._rows("reconciliation_reports")
            + self._rows("financial_reconciliations")
        )
        for report in reconciliations:
            if report.get("status") not in {"balanced", "passed"}:
                blockers.append({"code": "reconciliation_needs_review", "subject": report.get("id")})

        quality = self._rows("data_quality_results")
        failed_quality = [item for item in quality if item.get("status") == "failed"]
        if len(failed_quality) > body.maximum_failed_quality_gates:
            blockers.append({
                "code": "quality_gate_threshold_exceeded",
                "subject": str(len(failed_quality)),
            })

        shadow = self._rows("authorization_shadow_comparisons")
        mismatch_count = sum(
            1 for item in shadow if not (item.get("comparison") or {}).get("match", False)
        )
        mismatch_rate = mismatch_count / len(shadow) if shadow else None
        if (
            mismatch_rate is not None
            and mismatch_rate > body.maximum_shadow_mismatch_rate
        ):
            blockers.append({
                "code": "authorization_shadow_threshold_exceeded",
                "subject": f"{mismatch_rate:.4f}",
            })

        integration_health = self._rows("integration_health")
        for health in integration_health:
            if health.get("status") not in {"healthy", "disabled"}:
                blockers.append({"code": "integration_degraded", "subject": health.get("connector_id")})

        security_evidence = {
            item.get("evidence_type"): item for item in self._rows("launch_evidence")
            if item.get("status") == "approved"
        }
        required_evidence = {
            "production": {
                "backup_restore", "incident_tabletop", "security_scan",
                "secret_rotation", "rollback_rehearsal",
            },
            "cohort": {"rollback_rehearsal", "staging_e2e"},
            "internal": {"staging_e2e"},
            "dark": set(),
        }[body.stage]
        for evidence_type in sorted(required_evidence - set(security_evidence)):
            blockers.append({"code": "launch_evidence_missing", "subject": evidence_type})

        if body.stage in {"cohort", "production"} and not body.tenant_ids:
            blockers.append({"code": "rollout_tenant_cohort_required", "subject": body.stage})
        if not shadow:
            warnings.append({"code": "no_authorization_shadow_samples"})

        assessment = {
            "id": f"las_{uuid.uuid4().hex}",
            **body.model_dump(),
            "status": "ready" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": warnings,
            "metrics": {
                "authorization_shadow_samples": len(shadow),
                "authorization_shadow_mismatch_rate": mismatch_rate,
                "failed_quality_gates": len(failed_quality),
                "reconciliation_reports": len(reconciliations),
            },
            "assessed_by": actor_id,
            "assessed_at": utc_now().isoformat(),
            "does_not_activate_features": True,
        }
        self.db.collection("launch_assessments").document(assessment["id"]).set(assessment)
        return assessment
