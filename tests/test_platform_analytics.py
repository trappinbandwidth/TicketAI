from datetime import timedelta

from app.platform.analytics import AnalyticsQuery, AnalyticsService, QualityRule
from app.platform.models import utc_now
from tests.test_platform_identity import FakeDb


def test_operational_metrics_are_tenant_scoped_and_small_cohorts_suppressed():
    db = FakeDb()
    for index, status in enumerate(["succeeded", "failed", "succeeded"]):
        db.collection("sync_jobs").document(str(index)).set({
            "id": str(index), "tenant_id": "org_1", "status": status,
        })
    db.collection("sync_jobs").document("other").set({
        "id": "other", "tenant_id": "org_2", "status": "failed",
    })
    snapshot = AnalyticsService(db).operational_snapshot(
        AnalyticsQuery(tenant_id="org_1", minimum_cohort_size=5)
    )
    assert snapshot["metrics"]["connector_sync_success_rate"] is None
    assert snapshot["cohort_sizes"]["connector_sync_success_rate"] == 3
    assert "connector_sync_success_rate" in snapshot["suppressed_metrics"]
    assert "payer_id" not in str(snapshot)


def test_quality_gate_reports_missing_and_stale_records_without_copying_payloads():
    db = FakeDb()
    db.collection("credentials").document("cred_1").set({
        "id": "cred_1", "tenant_id": "org_1", "status": "",
        "updated_at": (utc_now() - timedelta(days=3)).isoformat(),
        "raw": {"cdl_number": "SECRET"},
    })
    result = AnalyticsService(db).evaluate_quality(QualityRule(
        id="credential-required-fresh",
        collection="credentials",
        required_fields=["status"],
        freshness_field="updated_at",
        max_age_hours=24,
        severity="high",
    ), "org_1")
    assert result["status"] == "failed"
    assert set(result["failures"][0]["reasons"]) == {"missing:status", "stale"}
    assert "SECRET" not in str(result)


def test_empty_quality_population_is_explicit_not_false_failure():
    result = AnalyticsService(FakeDb()).evaluate_quality(QualityRule(
        id="tickets-required", collection="tickets", required_fields=["status"]
    ))
    assert result["records_evaluated"] == 0
    assert result["failure_count"] == 0
    assert result["pass_rate"] is None
    assert result["status"] == "passed"
