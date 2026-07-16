from app.platform.shadow_service import shadow_authorization
from app.platform.service import principal_id_for_uid
from tests.test_platform_identity import FakeDb


def test_shadow_disabled_performs_no_reads_or_writes(monkeypatch):
    monkeypatch.setenv("TIP_OS_AUTH_SHADOW_ENABLED", "false")

    result = shadow_authorization(
        None,
        {"uid": "attorney_1"},
        legacy_allowed=True,
        legacy_reason="assigned",
        action="read",
        resource_type="case",
        resource_id="case_1",
    )

    assert result == ""


def test_shadow_records_missing_principal_mismatch_without_enforcement(monkeypatch):
    monkeypatch.setenv("TIP_OS_AUTH_SHADOW_ENABLED", "true")
    db = FakeDb()

    result = shadow_authorization(
        db,
        {"uid": "attorney_1"},
        legacy_allowed=True,
        legacy_reason="assigned",
        action="read",
        resource_type="case",
        resource_id="case_1",
    )
    record = db.collection("authorization_shadow_comparisons").rows[result]

    assert record["actor_id"] == principal_id_for_uid("attorney_1")
    assert record["enforced"] is False
    assert record["comparison"]["legacy_allowed"] is True
    assert record["comparison"]["platform_allowed"] is False
    assert record["comparison"]["platform_reason"] == "canonical_principal_missing"


def test_shadow_storage_failure_never_raises_into_business_route(monkeypatch):
    monkeypatch.setenv("TIP_OS_AUTH_SHADOW_ENABLED", "true")

    class BrokenDb:
        def collection(self, _name):
            raise RuntimeError("temporary audit outage")

    result = shadow_authorization(
        BrokenDb(),
        {"uid": "attorney_1"},
        legacy_allowed=True,
        legacy_reason="assigned",
        action="read",
        resource_type="case",
        resource_id="case_1",
    )

    assert result == ""
