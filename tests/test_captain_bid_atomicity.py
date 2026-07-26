"""Atomic and replay-safe Captain case award behavior."""
from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.routes import bids
from app.routes.bids import SelectBidBody


class _Snapshot:
    def __init__(self, ref, data):
        self.reference = ref
        self.id = ref.path.rsplit("/", 1)[-1]
        self._data = deepcopy(data) if data is not None else None
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self._data)


class _Ref:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def get(self):
        return _Snapshot(self, self.db.docs.get(self.path))

    def collection(self, name):
        return _Collection(self.db, f"{self.path}/{name}")

    def update(self, data):
        self.db.direct_writes.append(("update", self.path, data))

    def set(self, data):
        self.db.direct_writes.append(("set", self.path, data))


class _Collection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, ident):
        return _Ref(self.db, f"{self.path}/{ident}")

    def stream(self):
        prefix = f"{self.path}/"
        for path, data in self.db.docs.items():
            remainder = path.removeprefix(prefix)
            if path.startswith(prefix) and "/" not in remainder:
                yield _Snapshot(_Ref(self.db, path), data)


class _Batch:
    def __init__(self, db):
        self.db = db
        self.operations = []

    def update(self, ref, data):
        self.operations.append(("update", ref.path, data))

    def set(self, ref, data):
        self.operations.append(("set", ref.path, data))

    def commit(self):
        if self.db.fail_commit:
            raise OSError("emulator unavailable")
        for kind, path, data in self.operations:
            if kind == "update":
                self.db.docs.setdefault(path, {}).update(deepcopy(data))
            else:
                self.db.docs[path] = deepcopy(data)


class _DB:
    def __init__(self, docs, fail_commit=False):
        self.docs = deepcopy(docs)
        self.fail_commit = fail_commit
        self.direct_writes = []
        self.last_batch = None

    def collection(self, name):
        return _Collection(self, name)

    def batch(self):
        self.last_batch = _Batch(self)
        return self.last_batch


def _docs(case_overrides=None):
    case = {
        "bid_status": "open",
        "ticket_id": "ticket-1",
        **(case_overrides or {}),
    }
    return {
        "cases/case-1": case,
        "cases/case-1/bids/bid-1": {
            "bid_status": "submitted",
            "attorney_name": "Ada Counsel",
            "attorney_phone": "555-0100",
            "attorney_email": "ada@example.com",
            "fee_amount": 800,
        },
        "cases/case-1/bids/bid-2": {"bid_status": "submitted"},
        "bids/bid-1": {"bid_status": "submitted"},
        "bids/bid-2": {"bid_status": "submitted"},
        "tickets/ticket-1": {"attorney_status": "New"},
    }


def _authorize(monkeypatch, db):
    monkeypatch.setattr(bids, "_db", lambda: db)
    monkeypatch.setattr(
        bids,
        "require_staff",
        lambda _authorization: {
            "uid": "staff-1",
            "email": "captain@example.com",
            "role": "staff",
        },
    )


def test_bid_award_batches_case_ticket_bids_activity_and_audit(monkeypatch):
    db = _DB(_docs())
    _authorize(monkeypatch, db)

    result = bids.select_bid(
        "case-1",
        "bid-1",
        SelectBidBody(selected_by="spoofed-browser-value"),
        "Bearer staff",
    )

    assert result["idempotent_replay"] is False
    assert db.direct_writes == []
    assert db.docs["cases/case-1"]["last_updated_by"] == "captain@example.com"
    assert db.docs["cases/case-1"]["bid_awarded_to"] == "bid-1"
    assert db.docs["cases/case-1/bids/bid-2"]["bid_status"] == "rejected"
    assert "cases/case-1/activity/bid_awarded_bid-1" in db.docs
    assert "captain_action_audits/bid_awarded_case-1_bid-1" in db.docs


def test_bid_award_failed_commit_is_safe_to_retry(monkeypatch):
    original = _docs()
    db = _DB(original, fail_commit=True)
    _authorize(monkeypatch, db)

    with pytest.raises(HTTPException) as error:
        bids.select_bid(
            "case-1",
            "bid-1",
            SelectBidBody(selected_by="staff"),
            "Bearer staff",
        )

    assert error.value.status_code == 503
    assert "safe to retry" in error.value.detail
    assert db.docs == original
    assert db.direct_writes == []


def test_same_bid_award_replay_is_idempotent(monkeypatch):
    db = _DB(_docs({
        "bid_status": "awarded",
        "bid_awarded_to": "bid-1",
        "attorney_name": "Ada Counsel",
        "attorney_fee_amount": 800,
    }))
    _authorize(monkeypatch, db)

    result = bids.select_bid(
        "case-1",
        "bid-1",
        SelectBidBody(selected_by="staff"),
        "Bearer staff",
    )

    assert result["idempotent_replay"] is True
    assert db.last_batch is None


def test_conflicting_bid_award_is_rejected(monkeypatch):
    db = _DB(_docs({"bid_status": "awarded", "bid_awarded_to": "bid-2"}))
    _authorize(monkeypatch, db)

    with pytest.raises(HTTPException) as error:
        bids.select_bid(
            "case-1",
            "bid-1",
            SelectBidBody(selected_by="staff"),
            "Bearer staff",
        )

    assert error.value.status_code == 409
    assert db.last_batch is None
