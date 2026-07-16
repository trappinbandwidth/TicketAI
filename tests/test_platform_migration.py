from app.platform.migration import (
    MIGRATION_VERSION,
    ProfileRecord,
    apply_profile_backfill,
    plan_profile_backfill,
    write_migration_run,
)
from app.platform.models import AuthorizationDecision
from app.platform.service import principal_id_for_uid
from app.platform.shadow import compare_decisions, write_shadow_comparison
from tests.test_platform_identity import FakeDb


def test_backfill_plan_creates_links_and_is_safe_to_rerun():
    profiles = [ProfileRecord("drivers", "uid_1", {"email": "driver@example.com"})]
    first = plan_profile_backfill(profiles, {})

    assert first.create == 1
    assert first.conflict == 0
    assert "driver@example.com" not in str(first.safe_dict())
    assert "uid_1" not in str(first.safe_dict())

    db = FakeDb()
    lookup = {("drivers", "uid_1"): profiles[0].data}
    result = apply_profile_backfill(db, first, lookup)
    principal_id = principal_id_for_uid("uid_1")

    assert result["applied"] == 1
    assert db.collection("drivers").rows["uid_1"]["principal_id"] == principal_id
    assert db.collection("drivers").rows["uid_1"]["migration_version"] == MIGRATION_VERSION
    assert db.collection("principals").rows[principal_id]["email_masked"] == "d***@example.com"

    updated_profile = ProfileRecord("drivers", "uid_1", db.collection("drivers").rows["uid_1"])
    second = plan_profile_backfill(
        [updated_profile],
        {principal_id: db.collection("principals").rows[principal_id]},
    )
    assert second.unchanged == 1
    assert second.create == 0


def test_backfill_detects_existing_link_and_principal_uid_conflicts():
    uid = "uid_1"
    expected = principal_id_for_uid(uid)
    link_conflict = plan_profile_backfill(
        [ProfileRecord("drivers", uid, {"principal_id": "prn_wrong"})],
        {},
    )
    uid_conflict = plan_profile_backfill(
        [ProfileRecord("drivers", uid, {})],
        {expected: {"id": expected, "firebase_uid": "different_uid"}},
    )

    assert link_conflict.conflict == 1
    assert link_conflict.actions[0].reason == "profile_link_mismatch"
    assert uid_conflict.conflict == 1
    assert uid_conflict.actions[0].reason == "principal_uid_mismatch"


def test_backfill_detects_uid_reused_across_role_profiles():
    report = plan_profile_backfill(
        [
            ProfileRecord("drivers", "shared_uid", {}),
            ProfileRecord("attorneys", "shared_uid", {}),
        ],
        {},
    )

    assert report.create == 1
    assert report.conflict == 1
    assert report.actions[-1].reason == "uid_reused_across_role_profiles"


def test_backfill_does_not_create_consent_or_copy_raw_identifiers():
    profile = ProfileRecord(
        "drivers",
        "uid_1",
        {
            "email": "driver@example.com",
            "phone": "+13145551234",
            "cdl_number": "SECRET-CDL",
            "consent_on_file": True,
        },
    )
    report = plan_profile_backfill([profile], {})
    db = FakeDb()
    apply_profile_backfill(db, report, {(profile.collection, profile.document_id): profile.data})
    principal = next(iter(db.collection("principals").rows.values()))

    assert principal["email_masked"] == "d***@example.com"
    assert principal["phone_masked"] == "***-***-1234"
    assert "cdl_number" not in principal
    assert "consent_on_file" not in principal
    assert db.collection("consent_grants").rows == {}


def test_shadow_comparison_never_marks_itself_enforced():
    platform = AuthorizationDecision(allowed=False, reason="active_matching_consent_required")
    comparison = compare_decisions(True, "legacy_role_check", platform)
    db = FakeDb()

    comparison_id = write_shadow_comparison(
        db,
        actor_id="prn_actor",
        action="read",
        resource_type="case",
        resource_id="case_1",
        comparison=comparison,
        correlation_id="req_1",
    )
    record = db.collection("authorization_shadow_comparisons").rows[comparison_id]

    assert comparison.match is False
    assert record["enforced"] is False
    assert record["comparison"]["legacy_allowed"] is True
    assert record["comparison"]["platform_allowed"] is False


def test_apply_writes_minimal_migration_audit_and_rollback_pointer():
    profile = ProfileRecord("drivers", "uid_1", {})
    report = plan_profile_backfill([profile], {})
    db = FakeDb()
    result = apply_profile_backfill(db, report, {(profile.collection, profile.document_id): profile.data})

    run_id = write_migration_run(db, report, result)
    record = db.collection("migration_runs").rows[run_id]

    assert record["counts"]["applied"] == 1
    assert record["rollback"]["profile_field"] == "migration_previous_principal_id"
    assert "uid_1" not in str(record)
