"""Captain scan and ticket review decisions commit as one unit."""
import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.routes import queue
from app.routes.queue import ReviewDecisionRequest
from app.services import queue_store


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
        self.db, self.path = db, path

    def get(self):
        return _Snapshot(self, self.db.docs.get(self.path))

    def collection(self, name):
        return _Collection(self.db, f"{self.path}/{name}")


class _Collection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, ident):
        return _Ref(self.db, f"{self.path}/{ident}")


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
        self.last_batch = None

    def collection(self, name):
        return _Collection(self, name)

    def batch(self):
        self.last_batch = _Batch(self)
        return self.last_batch


def _docs(scan_status="pending", ticket_status="AI Review", scan_id="scan-1"):
    return {
        "scan_queue/scan-1": {
            "filename": "ticket.pdf",
            "pass_status": "yellow",
            "status": scan_status,
            "process_response": {
                "result": {
                    "Ticket_State__c": {"value": "KS"},
                    "Citation_Number__c": {"value": "ABC-1"},
                },
            },
        },
        "tickets/ticket-1": {
            "ai_scan_id": scan_id,
            "attorney_status": ticket_status,
        },
    }


def _authorize(monkeypatch, db):
    monkeypatch.setattr(queue_store, "_fs", lambda: db)
    monkeypatch.setattr(
        queue,
        "_authorize_staff_or_integration",
        lambda _authorization, _key: {
            "uid": "reviewer-1",
            "email": "reviewer@example.com",
            "role": "reviewer",
        },
    )


def _decide(action, edited=None, reason=""):
    return asyncio.run(queue.decide_queue_item(
        "scan-1",
        ReviewDecisionRequest(
            action=action,
            ticket_id="ticket-1",
            edited_fields=edited or {},
            reason=reason,
        ),
        "Bearer staff",
        None,
    ))


def test_approval_batches_scan_training_ticket_and_audit(monkeypatch):
    db = _DB(_docs())
    _authorize(monkeypatch, db)

    result = _decide("approve", {"Ticket_State__c": "TX"})

    assert result["idempotent_replay"] is False
    assert db.docs["scan_queue/scan-1"]["status"] == "approved"
    assert db.docs["tickets/ticket-1"]["attorney_status"] == "New"
    assert db.docs["training_records/scan-1"]["final_values"]["Ticket_State__c"] == "TX"
    assert db.docs["scan_queue/scan-1"]["reviewed_by"] == "reviewer@example.com"
    assert "captain_action_audits/review_approve_scan-1_ticket-1" in db.docs


def test_rejection_batches_scan_ticket_and_reason(monkeypatch):
    db = _DB(_docs())
    _authorize(monkeypatch, db)

    result = _decide("reject", reason="Image is unreadable")

    assert result["idempotent_replay"] is False
    assert db.docs["scan_queue/scan-1"]["status"] == "rejected"
    assert db.docs["tickets/ticket-1"]["attorney_status"] == "Rejected"
    assert db.docs["tickets/ticket-1"]["rejection_reason"] == "Image is unreadable"


def test_review_failed_commit_is_safe_to_retry(monkeypatch):
    original = _docs()
    db = _DB(original, fail_commit=True)
    _authorize(monkeypatch, db)

    with pytest.raises(HTTPException) as error:
        _decide("approve")

    assert error.value.status_code == 503
    assert "safe to retry" in error.value.detail
    assert db.docs == original


def test_review_rejects_mismatched_scan_and_ticket(monkeypatch):
    db = _DB(_docs(scan_id="different-scan"))
    _authorize(monkeypatch, db)

    with pytest.raises(HTTPException) as error:
        _decide("approve")

    assert error.value.status_code == 409
    assert db.last_batch is None


def test_exact_review_replay_is_idempotent(monkeypatch):
    db = _DB(_docs(scan_status="approved", ticket_status="New"))
    _authorize(monkeypatch, db)

    result = _decide("approve")

    assert result["idempotent_replay"] is True
    assert db.last_batch is None
