"""WP-13 privacy-safe operational analytics and data-quality gates."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.platform.models import utc_now


class QualityRule(BaseModel):
    id: str
    collection: str
    required_fields: list[str] = Field(default_factory=list)
    freshness_field: Optional[str] = None
    max_age_hours: Optional[int] = Field(default=None, gt=0)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


class AnalyticsQuery(BaseModel):
    tenant_id: Optional[str] = None
    minimum_cohort_size: int = Field(default=5, ge=3, le=100)


class AnalyticsService:
    def __init__(self, db):
        self.db = db

    def _rows(self, collection: str):
        reference = self.db.collection(collection)
        if hasattr(reference, "rows"):
            return list(reference.rows.values())
        return [item.to_dict() or {} for item in reference.limit(5000).stream()]

    @staticmethod
    def _tenant(rows: list[dict], tenant_id: Optional[str]):
        return [row for row in rows if not tenant_id or row.get("tenant_id") == tenant_id]

    @staticmethod
    def _ratio(numerator: int, denominator: int):
        return round(numerator / denominator, 4) if denominator else None

    def operational_snapshot(self, body: AnalyticsQuery):
        jobs = self._tenant(self._rows("sync_jobs"), body.tenant_id)
        tasks = self._tenant(self._rows("workflow_tasks"), body.tenant_id)
        signals = self._tenant(self._rows("signals"), body.tenant_id)
        auth = self._tenant(self._rows("authorization_shadow_comparisons"), body.tenant_id)
        webhooks = self._tenant(self._rows("webhook_deliveries"), body.tenant_id)
        documents = self._tenant(self._rows("document_jobs"), body.tenant_id)
        now = utc_now().isoformat()
        metrics = {
            "connector_sync_success_rate": self._ratio(
                sum(1 for row in jobs if row.get("status") == "succeeded"), len(jobs)
            ),
            "document_job_success_rate": self._ratio(
                sum(1 for row in documents if row.get("status") in {"completed", "human_review"}),
                len(documents),
            ),
            "overdue_task_rate": self._ratio(
                sum(
                    1 for row in tasks
                    if row.get("status") in {"open", "blocked"}
                    and row.get("due_at") and str(row["due_at"]) < now
                ),
                sum(1 for row in tasks if row.get("status") in {"open", "blocked"}),
            ),
            "critical_open_signal_count": sum(
                1 for row in signals if row.get("status") == "open" and row.get("severity") == "critical"
            ),
            "authorization_shadow_match_rate": self._ratio(
                sum(1 for row in auth if (row.get("comparison") or {}).get("match") is True), len(auth)
            ),
            "webhook_delivery_success_rate": self._ratio(
                sum(1 for row in webhooks if row.get("status") == "delivered"), len(webhooks)
            ),
            "webhook_dead_letter_count": sum(1 for row in webhooks if row.get("status") == "dead_letter"),
        }
        # Never emit a metric derived from a cohort smaller than the declared
        # privacy threshold. Counts of operational exceptions are not people
        # cohorts and remain visible.
        cohort_sizes = {
            "connector_sync_success_rate": len(jobs),
            "document_job_success_rate": len(documents),
            "overdue_task_rate": sum(1 for row in tasks if row.get("status") in {"open", "blocked"}),
            "authorization_shadow_match_rate": len(auth),
            "webhook_delivery_success_rate": len(webhooks),
        }
        suppressed = []
        for key, cohort_size in cohort_sizes.items():
            if 0 < cohort_size < body.minimum_cohort_size:
                metrics[key] = None
                suppressed.append(key)
        snapshot = {
            "id": f"met_{uuid.uuid4().hex}",
            "tenant_id": body.tenant_id,
            "metrics": metrics,
            "cohort_sizes": cohort_sizes,
            "suppressed_metrics": suppressed,
            "minimum_cohort_size": body.minimum_cohort_size,
            "created_at": utc_now().isoformat(),
        }
        self.db.collection("analytics_snapshots").document(snapshot["id"]).set(snapshot)
        return snapshot

    def evaluate_quality(self, rule: QualityRule, tenant_id: Optional[str] = None):
        rows = self._tenant(self._rows(rule.collection), tenant_id)
        failures = []
        cutoff = utc_now() - timedelta(hours=rule.max_age_hours or 0)
        for row in rows:
            reasons = [
                f"missing:{field}" for field in rule.required_fields
                if row.get(field) is None or row.get(field) == ""
            ]
            if rule.freshness_field and rule.max_age_hours:
                value = row.get(rule.freshness_field)
                try:
                    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    if parsed < cutoff:
                        reasons.append("stale")
                except (TypeError, ValueError):
                    reasons.append("invalid_freshness")
            if reasons:
                failures.append({"record_id": row.get("id"), "reasons": reasons})
        result = {
            "id": f"dq_{uuid.uuid4().hex}",
            "rule_id": rule.id,
            "collection": rule.collection,
            "tenant_id": tenant_id,
            "severity": rule.severity,
            "records_evaluated": len(rows),
            "failure_count": len(failures),
            "pass_rate": self._ratio(len(rows) - len(failures), len(rows)),
            "status": "passed" if not failures else "failed",
            "failures": failures,
            "created_at": utc_now().isoformat(),
        }
        self.db.collection("data_quality_results").document(result["id"]).set(result)
        return result
