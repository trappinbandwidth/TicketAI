import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routes import driver_profile
from tests.test_platform_identity import FakeDb


DRIVER = {"uid": "driver_uid", "role": "driver"}


def _carrier(dot_number: str):
    return {
        "dot_number": dot_number,
        "legal_name": "OPEN ROAD FREIGHT LLC",
        "operating_status": "Active",
        "carrier_level_crash_context": {
            "crash_count": 3,
            "scope_note": "Carrier-level public context. This is not an individual Driver safety record.",
        },
        "provenance": {"source_kind": "authoritative_public"},
    }


def _wire(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(driver_profile, "get_db", lambda: db)
    monkeypatch.setattr(
        driver_profile, "verify_firebase_token", lambda _header: DRIVER
    )
    monkeypatch.setattr(driver_profile, "carrier_discovery_detail", _carrier)
    return db


def _body(ended_on=None):
    return driver_profile.EmploymentHistoryWrite(
        dot_number="USDOT 1234567",
        started_on="2024-01-15",
        ended_on=ended_on,
        relationship_type="employee",
        title="Company Driver",
        source_record_reviewed=True,
    )


def test_driver_employment_history_is_self_owned_retry_safe_and_deletable(
    monkeypatch,
):
    db = _wire(monkeypatch)

    created = driver_profile.create_employment_history(
        _body(), authorization="Bearer driver"
    )
    employment = created["employment"]
    assert created["created"] is True
    assert employment["employment_claim"]["verification_status"] == "self_reported"
    assert employment["carrier_source_snapshot"]["legal_name"] == "OPEN ROAD FREIGHT LLC"
    assert employment["individual_driver_safety_record"] is False

    replay = driver_profile.create_employment_history(
        _body(), authorization="Bearer driver"
    )
    assert replay["duplicate"] is True
    assert replay["employment"]["id"] == employment["id"]

    updated = driver_profile.update_employment_history(
        employment["id"], _body("2025-06-30"), authorization="Bearer driver"
    )
    assert updated["employment"]["employment_claim"]["ended_on"] == "2025-06-30"

    listed = driver_profile.list_employment_history(
        authorization="Bearer driver"
    )
    assert listed["count"] == 1
    assert listed["employment_history"][0]["id"] == employment["id"]

    assert driver_profile.delete_employment_history(
        employment["id"], authorization="Bearer driver"
    ) == {"ok": True}
    assert driver_profile.list_employment_history(
        authorization="Bearer driver"
    )["count"] == 0
    audit_types = {
        event["event_type"] for event in db.collection("audit_events").rows.values()
    }
    assert {
        "driver.employment_history_created",
        "driver.employment_history_updated",
        "driver.employment_history_deleted",
    } <= audit_types


def test_another_driver_cannot_update_or_delete_employment_history(monkeypatch):
    _wire(monkeypatch)
    employment = driver_profile.create_employment_history(
        _body(), authorization="Bearer driver"
    )["employment"]
    monkeypatch.setattr(
        driver_profile,
        "verify_firebase_token",
        lambda _header: {"uid": "other_driver", "role": "driver"},
    )

    assert driver_profile.list_employment_history(
        authorization="Bearer other"
    )["employment_history"] == []
    with pytest.raises(HTTPException) as update:
        driver_profile.update_employment_history(
            employment["id"], _body("2025-06-30"), authorization="Bearer other"
        )
    assert update.value.status_code == 404
    with pytest.raises(HTTPException) as delete:
        driver_profile.delete_employment_history(
            employment["id"], authorization="Bearer other"
        )
    assert delete.value.status_code == 404


def test_employment_history_rejects_unreviewed_or_reversed_dates():
    with pytest.raises(ValidationError):
        driver_profile.EmploymentHistoryWrite(
            dot_number="1234567",
            started_on="2025-01-01",
            ended_on="2024-01-01",
            relationship_type="employee",
            source_record_reviewed=True,
        )
    with pytest.raises(ValidationError):
        driver_profile.EmploymentHistoryWrite(
            dot_number="1234567",
            started_on="2025-01-01",
            relationship_type="employee",
            source_record_reviewed=False,
        )
