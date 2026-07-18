from datetime import timedelta

import pytest

from app.platform.admin_service import AdminService, FeatureFlagUpdate, PrivilegedAccessRequest
from app.platform.models import utc_now
from tests.test_platform_identity import FakeDb


def test_operations_queues_classify_exceptions_without_sensitive_cross_queue_data():
    db = FakeDb()
    db.collection("document_assets").document("doc_1").set({"id": "doc_1", "status": "unsafe"})
    db.collection("document_jobs").document("job_1").set({"id": "job_1", "status": "failed"})
    db.collection("workflow_tasks").document("task_1").set({
        "id": "task_1", "status": "open",
        "due_at": (utc_now() - timedelta(hours=1)).isoformat(),
    })
    db.collection("signals").document("sig_1").set({
        "id": "sig_1", "status": "open", "severity": "critical",
    })
    db.collection("authorization_shadow_comparisons").document("cmp_1").set({
        "id": "cmp_1", "comparison": {"match": False},
    })

    summary = AdminService(db).operations_summary()

    assert [item["id"] for item in summary["queues"]["document_security"]] == ["doc_1"]
    assert [item["id"] for item in summary["queues"]["document_processing"]] == ["job_1"]
    assert [item["id"] for item in summary["queues"]["overdue_tasks"]] == ["task_1"]
    assert [item["id"] for item in summary["queues"]["high_risk_signals"]] == ["sig_1"]
    assert [item["id"] for item in summary["queues"]["authorization_mismatches"]] == ["cmp_1"]


def test_feature_flag_updates_are_versioned_reasoned_and_audited():
    db = FakeDb()
    service = AdminService(db)
    body = FeatureFlagUpdate(
        key="TIP_OS_DOCUMENTS_ENABLED",
        enabled=False,
        environment="production",
        expected_version=0,
        reason="Create disabled production flag before cohort rollout",
    )

    first = service.set_feature_flag("prn_admin", body)

    assert first["version"] == 1
    assert first["enabled"] is False
    assert len(db.collection("audit_events").rows) == 1
    with pytest.raises(RuntimeError, match="version conflict"):
        service.set_feature_flag("prn_admin", body)


def test_privileged_access_is_reason_coded_ticketed_and_time_bound():
    db = FakeDb()
    access = AdminService(db).start_privileged_access(
        "prn_support",
        PrivilegedAccessRequest(
            purpose="Investigate driver-reported extraction mismatch",
            support_ticket_id="SUP-123",
            duration_minutes=15,
            resource_type="document",
            resource_id="doc_1",
        ),
    )

    assert access["status"] == "active"
    assert access["support_ticket_id"] == "SUP-123"
    assert access["expires_at"] > access["started_at"]
    audit = db.collection("audit_events").rows[access["id"]]
    assert audit["payload"]["purpose"].startswith("Investigate")
