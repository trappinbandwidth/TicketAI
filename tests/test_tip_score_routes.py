from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.platform.service import principal_id_for_uid
from app.routes import tip_score
from app.services.tip_score import (
    ComponentInput,
    ConfidenceInput,
    ScoreCalculationInput,
    TipComponent,
    TipScoreStatus,
)


class Snapshot:
    def __init__(self, document_id: str, value: dict | None):
        self.id = document_id
        self._value = value

    @property
    def exists(self):
        return self._value is not None

    def to_dict(self):
        return dict(self._value) if self._value is not None else None


class Document:
    def __init__(self, collection, document_id: str):
        self.collection = collection
        self.id = document_id

    def get(self):
        return Snapshot(self.id, self.collection.rows.get(self.id))

    def set(self, value):
        self.collection.rows[self.id] = dict(value)

    def create(self, value):
        if self.id in self.collection.rows:
            raise RuntimeError("already exists")
        self.set(value)


class Query:
    def __init__(self, collection, field: str, value, limit_value: int | None = None):
        self.collection = collection
        self.field = field
        self.value = value
        self.limit_value = limit_value

    def limit(self, value: int):
        return Query(self.collection, self.field, self.value, value)

    def stream(self):
        rows = [
            Snapshot(document_id, value)
            for document_id, value in self.collection.rows.items()
            if value.get(self.field) == self.value
        ]
        return rows[: self.limit_value] if self.limit_value else rows


class Collection:
    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.next_id = 0

    def document(self, document_id: str | None = None):
        if document_id is None:
            self.next_id += 1
            document_id = f"auto_{self.next_id}"
        return Document(self, document_id)

    def where(self, field: str, operator: str, value):
        assert operator == "=="
        return Query(self, field, value)


class Db:
    def __init__(self):
        self.collections: dict[str, Collection] = {}

    def collection(self, name: str):
        return self.collections.setdefault(name, Collection())


def score_input(driver_id: str, unsafe_risk: float = 0.3):
    return ScoreCalculationInput(
        driver_id=driver_id,
        components={
            component: ComponentInput(
                risk=unsafe_risk if component == TipComponent.UNSAFE_DRIVING else 0.1
            )
            for component in TipComponent
        },
        confidence=ConfidenceInput(
            source_completeness=1,
            identity_match_quality=1,
            record_freshness=1,
            credential_verification=1,
            exposure_sufficiency=1,
        ),
        status=TipScoreStatus.OFFICIAL,
        data_as_of=datetime(2026, 7, 26, tzinfo=timezone.utc),
        verified_history_months=24,
        verified_inspections=2,
        evidence_ids=["evt_verified_1"],
        calculation_reason="verified evidence refresh",
    )


def wire(monkeypatch, db: Db, claims: dict):
    monkeypatch.setattr(tip_score, "get_db", lambda: db)
    monkeypatch.setattr(tip_score, "_claims", lambda _authorization: dict(claims))


def test_driver_can_only_read_own_score(monkeypatch):
    db = Db()
    uid = "driver_1"
    own_id = principal_id_for_uid(uid)
    wire(monkeypatch, db, {"uid": uid, "role": "driver"})

    result = tip_score.get_score_for_driver(own_id, "Bearer token")
    assert result["score"] == 700
    assert result["projection"] == "driver"
    with pytest.raises(HTTPException) as denied:
        tip_score.get_score_for_driver("prn_someone_else", "Bearer token")
    assert denied.value.status_code == 403


def test_attorney_case_projection_requires_assignment_consent_and_active_status(monkeypatch):
    db = Db()
    driver_uid = "driver_1"
    driver_id = principal_id_for_uid(driver_uid)
    db.collection("tickets").rows.update({
        "allowed": {
            "driver_id": driver_uid,
            "assigned_attorney_id": "attorney_1",
            "tip_score_consent_on_file": True,
            "attorney_status": "Accepted",
            "violation_category": "Speeding",
        },
        "no_consent": {
            "driver_id": "driver_2",
            "assigned_attorney_id": "attorney_1",
            "tip_score_consent_on_file": False,
            "attorney_status": "Accepted",
        },
        "closed": {
            "driver_id": "driver_3",
            "assigned_attorney_id": "attorney_1",
            "tip_score_consent_on_file": True,
            "attorney_status": "Ticket Closed",
        },
    })
    wire(monkeypatch, db, {
        "uid": "attorney_1",
        "attorney_id": "attorney_1",
        "role": "attorney",
    })

    listed = tip_score.list_attorney_score_cases("Bearer token")
    assert [item["ticket_id"] for item in listed["cases"]] == ["allowed"]
    result = tip_score.get_attorney_case_score("allowed", "Bearer token")
    assert result["driver_id"] == driver_id
    assert result["projection"] == "attorney"
    assert "substanceAlcohol" not in result["components"]
    assert result["restricted_components"] == ["substanceAlcohol"]

    with pytest.raises(HTTPException) as no_consent:
        tip_score.get_attorney_case_score("no_consent", "Bearer token")
    assert no_consent.value.status_code == 403
    with pytest.raises(HTTPException) as closed:
        tip_score.get_attorney_case_score("closed", "Bearer token")
    assert closed.value.status_code == 409


def test_recalculation_is_staff_only_immutable_idempotent_and_superseding(monkeypatch):
    db = Db()
    driver_id = principal_id_for_uid("driver_1")
    staff = {"uid": "staff_1", "role": "staff", "staff_role": "reviewer"}
    wire(monkeypatch, db, staff)

    first = tip_score.recalculate_score(driver_id, score_input(driver_id), "Bearer token")
    replay = tip_score.recalculate_score(driver_id, score_input(driver_id), "Bearer token")
    assert replay["id"] == first["id"]
    assert len(db.collection("tip_score_snapshots").rows) == 1
    assert first["evidence_ids"] == ["evt_verified_1"]
    assert first["calculated_by"] == principal_id_for_uid("staff_1")

    second = tip_score.recalculate_score(
        driver_id, score_input(driver_id, unsafe_risk=0.6), "Bearer token"
    )
    assert second["id"] != first["id"]
    assert second["supersedes_snapshot_id"] == first["id"]
    assert second["previous_score"] == first["score"]
    assert len(db.collection("tip_score_snapshots").rows) == 2
    assert db.collection("tip_score_current").rows[driver_id]["id"] == second["id"]

    wire(monkeypatch, db, {"uid": "driver_1", "role": "driver"})
    with pytest.raises(HTTPException) as denied:
        tip_score.recalculate_score(driver_id, score_input(driver_id), "Bearer token")
    assert denied.value.status_code == 403


def test_captain_recalculation_request_is_reason_logged_and_never_edits_score(monkeypatch):
    db = Db()
    driver_id = principal_id_for_uid("driver_1")
    wire(monkeypatch, db, {"uid": "staff_1", "role": "staff", "staff_role": "reviewer"})
    current = tip_score.recalculate_score(driver_id, score_input(driver_id), "Bearer token")

    result = tip_score.request_score_recalculation(
        driver_id,
        tip_score.RecalculationRequest(
            reason="Verified court disposition corrected the source event.",
            evidence_ids=["evt_2", "evt_2", "evt_1"],
        ),
        "Bearer token",
    )
    assert result["status"] == "queued"
    assert result["current_snapshot_id"] == current["id"]
    assert result["evidence_ids"] == ["evt_1", "evt_2"]
    assert db.collection("tip_score_current").rows[driver_id]["id"] == current["id"]
    assert len(db.collection("tip_score_recalculation_requests").rows) == 1
