from app.platform.launch import LaunchAssessmentRequest, LaunchService
from tests.test_platform_identity import FakeDb


FLAGS = ["TIP_OS_IDENTITY_ENABLED", "TIP_OS_DOCUMENTS_ENABLED"]


def test_dark_launch_requires_flags_to_exist_and_remain_disabled():
    db = FakeDb()
    for key in FLAGS:
        db.collection("feature_flags").document(key).set({
            "key": key, "enabled": False, "environment": "staging",
        })
    assessment = LaunchService(db).assess(LaunchAssessmentRequest(
        stage="dark", environment="staging", required_feature_flags=FLAGS
    ), "prn_admin")
    assert assessment["status"] == "ready"
    assert assessment["does_not_activate_features"] is True


def test_launch_blocks_conflicts_degraded_connectors_and_missing_evidence():
    db = FakeDb()
    db.collection("migration_runs").document("mig_1").set({
        "id": "mig_1", "status": "blocked", "summary": {"conflicts": 1},
    })
    db.collection("integration_health").document("int_1").set({
        "id": "int_1", "connector_id": "fmcsa", "status": "degraded",
    })
    result = LaunchService(db).assess(LaunchAssessmentRequest(
        stage="production", environment="production", tenant_ids=["org_1"]
    ), "prn_admin")
    codes = {item["code"] for item in result["blockers"]}
    assert result["status"] == "blocked"
    assert "migration_failed_or_blocked" in codes
    assert "migration_conflicts_or_invalid" in codes
    assert "integration_degraded" in codes
    assert "launch_evidence_missing" in codes


def test_cohort_never_passes_without_explicit_tenant_and_shadow_threshold():
    db = FakeDb()
    db.collection("launch_evidence").document("e1").set({
        "evidence_type": "rollback_rehearsal", "status": "approved",
    })
    db.collection("launch_evidence").document("e2").set({
        "evidence_type": "staging_e2e", "status": "approved",
    })
    db.collection("authorization_shadow_comparisons").document("cmp").set({
        "comparison": {"match": False},
    })
    result = LaunchService(db).assess(LaunchAssessmentRequest(
        stage="cohort", environment="staging", maximum_shadow_mismatch_rate=0
    ), "prn_admin")
    codes = {item["code"] for item in result["blockers"]}
    assert "rollout_tenant_cohort_required" in codes
    assert "authorization_shadow_threshold_exceeded" in codes
