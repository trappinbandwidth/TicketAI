from datetime import datetime, timezone

import pytest

from app.platform.record_service import DriverCloudService
from app.platform.records import CanonicalRecordCreate, SourceProvenance


class Snapshot:
    def __init__(self, data=None):
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class Document:
    def __init__(self, collection, key):
        self.collection = collection
        self.key = key

    def get(self):
        return Snapshot(self.collection.rows.get(self.key))

    def set(self, value):
        self.collection.rows[self.key] = dict(value)


class Query:
    def __init__(self, rows, field, value):
        self.rows = rows
        self.field = field
        self.value = value

    def stream(self):
        return [Snapshot(row) for row in self.rows.values() if row.get(self.field) == self.value]


class Collection:
    def __init__(self):
        self.rows = {}

    def document(self, key):
        return Document(self, key)

    def where(self, field, operator, value):
        assert operator == "=="
        return Query(self.rows, field, value)


class Db:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())


def record_body(**overrides):
    values = {
        "category": "credential",
        "record_type": "commercial_driver_license",
        "title": "Commercial Driver License",
        "raw": {"license_number": "RAW-123"},
        "normalized": {"state": "MO", "class": "A"},
        "derived": {"days_to_expiry": 30},
        "provenance": SourceProvenance(
            source_type="driver",
            source_name="Driver upload",
            method="upload",
            acquired_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
        ),
    }
    values.update(overrides)
    return CanonicalRecordCreate(**values)


def test_record_preserves_raw_normalized_derived_and_provenance():
    service = DriverCloudService(Db())

    record = service.create_record("prn_driver", "prn_driver", record_body())

    assert record.raw == {"license_number": "RAW-123"}
    assert record.normalized["state"] == "MO"
    assert record.derived["days_to_expiry"] == 30
    assert record.provenance.source_name == "Driver upload"
    assert len(record.raw_sha256) == 64
    assert service.list_activity("prn_driver")[0].event_type == "record.created"


def test_cross_driver_create_and_update_are_denied():
    service = DriverCloudService(Db())
    with pytest.raises(PermissionError):
        service.create_record("prn_attacker", "prn_driver", record_body())

    record = service.create_record("prn_driver", "prn_driver", record_body())
    with pytest.raises(PermissionError):
        service.update_record("prn_attacker", record.id, 1, record_body())


def test_update_is_versioned_and_conflict_safe():
    service = DriverCloudService(Db())
    original = service.create_record("prn_driver", "prn_driver", record_body())

    updated = service.update_record(
        "prn_driver",
        original.id,
        1,
        record_body(status="verified", normalized={"state": "MO", "class": "A", "verified": True}),
    )

    assert updated.record_version == 2
    assert updated.status.value == "verified"
    assert service.list_activity("prn_driver")[0].changed_fields == ["normalized", "status"]
    with pytest.raises(RuntimeError, match="version conflict"):
        service.update_record("prn_driver", original.id, 1, record_body())


def test_records_are_isolated_and_groupable_by_category():
    service = DriverCloudService(Db())
    service.create_record("prn_a", "prn_a", record_body())
    service.create_record(
        "prn_b",
        "prn_b",
        record_body(category="inspection", record_type="roadside_inspection", title="Inspection"),
    )

    records = service.list_records("prn_a")

    assert len(records) == 1
    assert records[0].subject_principal_id == "prn_a"
    assert records[0].category.value == "credential"
