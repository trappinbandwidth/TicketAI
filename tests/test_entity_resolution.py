import pytest

from app.platform.entity_resolution import (
    EntityResolutionService,
    MatchCandidate,
    ResolutionCaseCreate,
    ResolutionDecision,
)
from tests.test_platform_identity import FakeDb


def case_body():
    return ResolutionCaseCreate(
        tenant_id="org_1",
        entity_type="record_owner",
        source_system="legacy_tickets",
        source_record_reference="tickets/ticket_1",
        source_fingerprint="a" * 64,
        candidates=[
            MatchCandidate(
                canonical_id="prn_driver_1", score=0.82,
                evidence=["hashed_identifier_match"], conflicting_fields=["date_of_birth"],
            )
        ],
    )


def test_resolution_queue_is_idempotent_and_never_auto_links():
    db = FakeDb()
    service = EntityResolutionService(db)
    first, created = service.open_case(case_body(), "prn_migration")
    second, created_again = service.open_case(case_body(), "prn_migration")
    assert created is True and created_again is False
    assert first == second
    assert first["status"] == "pending_review"
    assert "decision" not in first


def test_human_may_only_link_an_evaluated_candidate_and_decision_is_audited():
    db = FakeDb()
    service = EntityResolutionService(db)
    case, _ = service.open_case(case_body(), "prn_migration")
    with pytest.raises(ValueError, match="not an evaluated"):
        service.decide(case["id"], ResolutionDecision(
            action="link", canonical_id="prn_unknown", reason="manual review"
        ), "prn_reviewer")
    resolved, changed = service.decide(case["id"], ResolutionDecision(
        action="link", canonical_id="prn_driver_1", reason="Verified authoritative source"
    ), "prn_reviewer")
    assert changed is True
    assert resolved["decision"]["decided_by"] == "prn_reviewer"
    assert len(db.collection("audit_events").rows) == 1


def test_conflicting_second_decision_is_rejected():
    db = FakeDb()
    service = EntityResolutionService(db)
    case, _ = service.open_case(case_body(), "prn_migration")
    service.decide(case["id"], ResolutionDecision(
        action="reject", reason="Identifiers conflict"
    ), "prn_reviewer")
    with pytest.raises(RuntimeError, match="different decision"):
        service.decide(case["id"], ResolutionDecision(
            action="create_new", reason="Changed mind"
        ), "prn_reviewer")
