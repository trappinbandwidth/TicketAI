from datetime import timedelta

import pytest

from fastapi import HTTPException

from app.platform.admin_service import (
    AdminService,
    CarrierAuthorityDecision,
    FeatureFlagUpdate,
    PrivilegedAccessRequest,
)
from app.platform.models import utc_now
from app.routes import platform_admin
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


def test_system_health_reconciles_shared_business_records():
    db = FakeDb()
    db.collection("drivers").document("driver_1").set({"id": "driver_1"})
    db.collection("carriers").document("carrier_1").set({"id": "carrier_1"})
    db.collection("attorneys").document("attorney_1").set({"id": "attorney_1"})
    db.collection("tickets").document("ticket_1").set({
        "id": "ticket_1", "attorney_status": "New",
    })
    db.collection("payout_requests").document("payout_1").set({
        "id": "payout_1", "status": "requested", "total_amount": 425.50,
    })
    db.collection("feature_flags").document("TIP_OS_DOCUMENTS_ENABLED").set({
        "key": "TIP_OS_DOCUMENTS_ENABLED", "enabled": True,
    })

    health = AdminService(db).system_health()

    assert health["status"] == "operational"
    assert health["business"] == {
        "drivers": 1,
        "carriers": 1,
        "attorneys": 1,
        "active_cases": 1,
        "pending_payouts": 1,
        "pending_payout_amount": 425.5,
    }
    assert {service["key"] for service in health["services"]} == {
        "engine_api", "data_store", "driver_points", "tip_os_modules",
    }


def test_staff_notifications_are_identified_and_marked_read():
    db = FakeDb()
    db.collection("staff_notifications").document("note_1").set({
        "title": "Review needed",
        "read": False,
    })
    db.collection("staff_notifications").document("note_2").set({
        "title": "Already handled",
        "read": True,
    })

    service = AdminService(db)
    assert service.list_staff_notifications() == [
        {"id": "note_1", "title": "Review needed", "read": False},
        {"id": "note_2", "title": "Already handled", "read": True},
    ]
    assert service.mark_all_staff_notifications_read() == 1
    assert db.collection("staff_notifications").rows["note_1"]["read"] is True


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


def test_feature_flags_are_listed_and_updates_require_control_plane_role(monkeypatch):
    db = FakeDb()
    db.collection("feature_flags").document("TIP_OS_DOCUMENTS_ENABLED").set({
        "key": "TIP_OS_DOCUMENTS_ENABLED",
        "enabled": True,
        "environment": "development",
        "version": 2,
    })
    assert AdminService(db).list_feature_flags() == [{
        "key": "TIP_OS_DOCUMENTS_ENABLED",
        "enabled": True,
        "environment": "development",
        "version": 2,
    }]

    monkeypatch.setenv("TIP_OS_ADMIN_CONSOLE_ENABLED", "true")
    reviewer = {
        "uid": "reviewer_1",
        "role": "staff",
        "staff_role": "reviewer",
        "auth_time": int(utc_now().timestamp()),
        "mfa_verified": True,
    }
    monkeypatch.setattr(platform_admin, "verify_firebase_token", lambda _header: reviewer)
    with pytest.raises(HTTPException) as wrong_role:
        platform_admin.update_feature_flag(
            "TIP_OS_DOCUMENTS_ENABLED",
            FeatureFlagUpdate(
                key="TIP_OS_DOCUMENTS_ENABLED",
                enabled=False,
                environment="development",
                expected_version=2,
                reason="Reviewer cannot change control-plane state",
            ),
            authorization="Bearer reviewer",
        )
    assert wrong_role.value.status_code == 403


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


def _authority_review_fixture(status="pending_review", dot_status="pending_review"):
    db = FakeDb()
    db.collection("carrier_authority_claims").document("claim_1").set({
        "id": "claim_1",
        "carrier_profile_id": "carrier_1",
        "organization_id": "org_1",
        "dot_number": "1234567",
        "status": status,
        "dot_claim_status": dot_status,
        "evidence_ids": ["evidence_1"],
        "decision_version": 0,
    })
    db.collection("carrier_authority_evidence").document("evidence_1").set({
        "id": "evidence_1",
        "claim_id": "claim_1",
        "evidence_method": "mcs150",
        "status": "received",
        "storage_path": "private/path",
    })
    db.collection("carriers").document("carrier_1").set({
        "organization_id": "org_1",
        "dot_number": "1234567",
        "dot_claim_status": dot_status,
        "tenant_status": "pending",
        "verification_status": "unverified",
    })
    db.collection("organizations").document("org_1").set({
        "tenant_status": "pending",
        "verification_status": "unverified",
    })
    db.collection("carrier_dot_claims").document("1234567").set({
        "dot_number": "1234567",
        "claimant_carrier_id": "carrier_1",
        "status": dot_status,
    })
    return db


def test_carrier_authority_queue_minimizes_evidence_and_approval_reconciles():
    db = _authority_review_fixture()
    service = AdminService(db)
    queue = service.list_carrier_authority_claims(status="pending_review")
    assert queue == [{
        "id": "claim_1",
        "carrier_profile_id": "carrier_1",
        "organization_id": "org_1",
        "dot_number": "1234567",
        "status": "pending_review",
        "dot_claim_status": "pending_review",
        "fmcsa_snapshot_id": None,
        "evidence_count": 1,
        "evidence_methods": ["mcs150"],
        "evidence": [{
            "id": "evidence_1",
            "evidence_method": "mcs150",
            "file_name": None,
            "content_type": None,
            "size_bytes": None,
            "status": "received",
            "created_at": None,
        }],
        "created_at": None,
        "updated_at": None,
        "decision_reason": None,
    }]
    assert "storage_path" not in queue[0]

    body = CarrierAuthorityDecision(
        decision="approve",
        reason="Evidence matches the reserved USDOT record.",
        support_ticket_id="VERIFY-101",
    )
    approved = service.decide_carrier_authority("prn_reviewer", "claim_1", body)
    replay = service.decide_carrier_authority("prn_reviewer", "claim_1", body)

    assert approved["status"] == "verified"
    assert approved["duplicate"] is False
    assert replay["duplicate"] is True
    assert db.collection("carriers").rows["carrier_1"]["tenant_status"] == "active"
    assert db.collection("carriers").rows["carrier_1"]["account_authority_status"] == "verified"
    assert db.collection("organizations").rows["org_1"]["verification_status"] == "verified"
    assert db.collection("carrier_dot_claims").rows["1234567"]["status"] == "verified"
    authority_audits = [
        item for item in db.collection("audit_events").rows.values()
        if item["event_type"] == "carrier.authority_approve"
    ]
    assert len(authority_audits) == 1


def test_carrier_authority_duplicate_claim_cannot_be_approved():
    db = _authority_review_fixture(dot_status="duplicate_disputed")
    with pytest.raises(RuntimeError, match="Duplicate or disputed"):
        AdminService(db).decide_carrier_authority(
            "prn_reviewer",
            "claim_1",
            CarrierAuthorityDecision(
                decision="approve",
                reason="Should remain quarantined.",
                support_ticket_id="VERIFY-102",
            ),
        )
    assert db.collection("carriers").rows["carrier_1"]["tenant_status"] == "pending"


def test_carrier_authority_evidence_review_denies_wrong_claim():
    db = _authority_review_fixture()
    service = AdminService(db)
    evidence = service.carrier_authority_evidence_for_review(
        "claim_1",
        "evidence_1",
    )
    assert evidence["storage_path"] == "private/path"

    db.collection("carrier_authority_claims").document("claim_2").set({
        "id": "claim_2",
        "carrier_profile_id": "carrier_2",
    })
    with pytest.raises(KeyError, match="evidence not found"):
        service.carrier_authority_evidence_for_review(
            "claim_2",
            "evidence_1",
        )


def test_carrier_authority_more_information_preserves_workspace_and_evidence():
    db = _authority_review_fixture()
    result = AdminService(db).decide_carrier_authority(
        "prn_reviewer",
        "claim_1",
        CarrierAuthorityDecision(
            decision="request_more_information",
            reason="Upload an authorization letter.",
            support_ticket_id="VERIFY-103",
        ),
    )
    assert result["status"] == "pending_evidence"
    assert db.collection("carriers").rows["carrier_1"]["tenant_status"] == "pending"
    assert "evidence_1" in db.collection("carrier_authority_evidence").rows


def test_carrier_authority_decision_route_requires_staff_recent_auth_and_mfa(
    monkeypatch,
):
    monkeypatch.setenv("TIP_OS_ADMIN_CONSOLE_ENABLED", "true")
    monkeypatch.setattr(
        platform_admin,
        "verify_firebase_token",
        lambda _header: {
            "uid": "reviewer_1",
            "role": "reviewer",
            "auth_time": int(utc_now().timestamp()),
            "firebase": {},
        },
    )
    with pytest.raises(HTTPException) as missing_mfa:
        platform_admin.decide_carrier_authority(
            "claim_1",
            CarrierAuthorityDecision(
                decision="approve",
                reason="Reviewed.",
                support_ticket_id="VERIFY-104",
            ),
            authorization="Bearer reviewer",
        )
    assert missing_mfa.value.status_code == 403
    assert "Multi-factor" in missing_mfa.value.detail

    monkeypatch.setattr(
        platform_admin,
        "verify_firebase_token",
        lambda _header: {"uid": "carrier_1", "role": "carrier"},
    )
    with pytest.raises(HTTPException) as wrong_role:
        platform_admin.carrier_authority_claims(
            status=None,
            limit=100,
            authorization="Bearer carrier",
        )
    assert wrong_role.value.status_code == 403


def test_carrier_authority_evidence_download_is_mfa_gated_and_short_lived(
    monkeypatch,
):
    from app.main import app

    path = (
        "/api/v1/platform-admin/carrier-authority-claims/{claim_id}/"
        "evidence/{evidence_id}/download"
    )
    assert "get" in app.openapi()["paths"][path]
    monkeypatch.setenv("TIP_OS_ADMIN_CONSOLE_ENABLED", "true")
    monkeypatch.setattr(
        platform_admin,
        "verify_firebase_token",
        lambda _header: {
            "uid": "reviewer_1",
            "role": "reviewer",
            "auth_time": int(utc_now().timestamp()),
            "mfa_verified": True,
        },
    )

    class Service:
        def carrier_authority_evidence_for_review(self, claim_id, evidence_id):
            assert (claim_id, evidence_id) == ("claim_1", "evidence_1")
            return {"storage_path": "private/path"}

    class Blob:
        def generate_signed_url(self, **kwargs):
            assert kwargs == {
                "version": "v4",
                "expiration": 900,
                "method": "GET",
            }
            return "https://signed.invalid/evidence"

    class Bucket:
        def blob(self, path):
            assert path == "private/path"
            return Blob()

    monkeypatch.setattr(platform_admin, "_service", lambda: Service())
    monkeypatch.setattr(platform_admin, "_bucket", lambda: Bucket())
    result = platform_admin.download_carrier_authority_evidence(
        "claim_1",
        "evidence_1",
        authorization="Bearer reviewer",
    )
    assert result == {
        "url": "https://signed.invalid/evidence",
        "expires_in": 900,
    }
