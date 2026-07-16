import pytest
from fastapi import HTTPException

from app.routes import attorney_cases
from app.routes.attorney_cases import (
    ActivityUpdate,
    ConflictDecisionBody,
    _legacy_case_access,
    _require_verified_attorney,
)
from tests.test_platform_identity import FakeDb


def test_assigned_claimed_or_closing_attorney_has_case_access():
    for field in ("assigned_attorney_id", "claimed_by", "closed_by_attorney_id"):
        allowed, reason = _legacy_case_access({field: "attorney_1"}, "attorney_1")
        assert allowed is True
        assert reason == "assigned_or_claimed_case"


def test_unassigned_attorney_cannot_read_or_write_case_activity():
    allowed, reason = _legacy_case_access(
        {"assigned_attorney_id": "attorney_2", "attorney_status": "Accepted"},
        "attorney_1",
    )

    assert allowed is False
    assert reason == "legacy_case_scope_denied"


def test_available_case_access_is_explicit_and_does_not_extend_to_activity():
    data = {"attorney_status": "New"}

    detail_allowed, _ = _legacy_case_access(data, "attorney_1", allow_available=True)
    activity_allowed, _ = _legacy_case_access(data, "attorney_1", allow_available=False)

    assert detail_allowed is True
    assert activity_allowed is False


def test_activity_route_denies_non_owner_and_still_emits_shadow(monkeypatch):
    db = FakeDb()
    db.collection("tickets").document("case_1").set({
        "assigned_attorney_id": "attorney_2",
        "attorney_status": "Accepted",
    })
    comparisons = []
    monkeypatch.setattr(attorney_cases, "_verify_token", lambda _header: {"uid": "attorney_1"})
    monkeypatch.setattr(attorney_cases, "_db", lambda: db)
    monkeypatch.setattr(
        attorney_cases,
        "_shadow_case_access",
        lambda *_args, **kwargs: comparisons.append(kwargs),
    )

    with pytest.raises(HTTPException) as read_exc:
        attorney_cases.get_activity("case_1", "Bearer test")
    with pytest.raises(HTTPException) as write_exc:
        attorney_cases.add_activity("case_1", ActivityUpdate(message="private"), "Bearer test")

    assert read_exc.value.status_code == 403
    assert write_exc.value.status_code == 403
    assert [item["action"] for item in comparisons] == ["read_activity", "write_activity"]
    assert all(item["allowed"] is False for item in comparisons)


def test_unverified_attorney_is_denied_governed_marketplace_access():
    db = FakeDb()
    db.collection("attorneys").document("attorney_1").set({
        "verification_status": "pending",
    })

    with pytest.raises(HTTPException) as exc:
        _require_verified_attorney(db, "attorney_1")

    assert exc.value.status_code == 403


def test_conflict_decision_is_idempotent_and_audited(monkeypatch):
    db = FakeDb()
    db.collection("attorneys").document("attorney_1").set({
        "verification_status": "verified",
    })
    db.collection("tickets").document("case_1").set({"attorney_status": "New"})
    monkeypatch.setenv("TIP_OS_ATTORNEY_GOVERNANCE_ENABLED", "true")
    monkeypatch.setattr(attorney_cases, "_verify_token", lambda _: {"uid": "attorney_1"})
    monkeypatch.setattr(attorney_cases, "_db", lambda: db)
    body = ConflictDecisionBody(decision="no_conflict", reason="Parties checked")

    first = attorney_cases.record_conflict_decision("case_1", body, "Bearer test")
    second = attorney_cases.record_conflict_decision("case_1", body, "Bearer test")

    assert first["conflict_decision"]["id"] == second["conflict_decision"]["id"]
    assert len(db.collection("attorney_conflict_decisions").rows) == 1
    assert len(db.collection("audit_events").rows) == 1
