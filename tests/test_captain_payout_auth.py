from fastapi import HTTPException
import pytest

from app.routes import attorney_workspace
from app.routes.attorney_workspace import MarkPaid
from app.services import case_lifecycle


class _Snapshot:
    exists = True

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _Ref:
    def __init__(self, path, payout):
        self.path = path
        self._payout = payout
        self.direct_updates = []

    def get(self):
        return _Snapshot(self._payout)

    def update(self, data):
        self.direct_updates.append(data)


class _Collection:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def document(self, ident):
        path = f"{self.name}/{ident}"
        return self.db.refs.setdefault(path, _Ref(path, self.db.payout))


class _Batch:
    def __init__(self, fail=False):
        self.fail = fail
        self.operations = []

    def update(self, ref, data):
        self.operations.append(("update", ref.path, data))

    def set(self, ref, data):
        self.operations.append(("set", ref.path, data))

    def commit(self):
        if self.fail:
            raise OSError("emulator unavailable")
        return self.operations


class _DB:
    def __init__(self, payout, fail=False):
        self.payout = payout
        self.refs = {}
        self.last_batch = _Batch(fail)

    def collection(self, name):
        return _Collection(self, name)

    def batch(self):
        return self.last_batch


def test_mark_paid_uses_verified_actor_and_requires_mfa(monkeypatch):
    actor = {
        "uid": "staff-1",
        "email": "aam@example.com",
        "role": "staff",
        "staff_role": "attorney_account_manager",
    }
    calls = []
    monkeypatch.setattr(attorney_workspace, "require_staff", lambda _header: actor)
    monkeypatch.setattr(
        attorney_workspace,
        "require_staff_claim",
        lambda claims, roles: calls.append(("roles", claims, roles)) or claims,
    )
    monkeypatch.setattr(
        attorney_workspace,
        "require_recent_auth",
        lambda claims, require_mfa=False: calls.append(("recent", claims, require_mfa)) or claims,
    )
    monkeypatch.setattr(attorney_workspace, "get_db", lambda: object())
    monkeypatch.setattr(
        attorney_workspace.cl,
        "mark_payout_paid",
        lambda _db, payout_id, method, staff_id: {
            "payout_id": payout_id,
            "method": method,
            "staff_id": staff_id,
        },
    )

    result = attorney_workspace.admin_mark_paid(
        "payout-1",
        MarkPaid(payout_method="Choice Digital"),
        "Bearer token",
    )

    assert result["staff_id"] == "aam@example.com"
    assert ("roles", actor, ["admin", "attorney_account_manager"]) in calls
    assert ("recent", actor, True) in calls


def test_mark_paid_denies_unauthorized_staff_role(monkeypatch):
    actor = {"uid": "reviewer-1", "role": "staff", "staff_role": "reviewer"}
    monkeypatch.setattr(attorney_workspace, "require_staff", lambda _header: actor)
    monkeypatch.setattr(
        attorney_workspace,
        "require_staff_claim",
        lambda _claims, _roles: (_ for _ in ()).throw(
            HTTPException(status_code=403, detail="Required staff role missing."),
        ),
    )

    with pytest.raises(HTTPException) as error:
        attorney_workspace.admin_mark_paid(
            "payout-1",
            MarkPaid(payout_method="Choice Digital"),
            "Bearer token",
        )

    assert error.value.status_code == 403


def test_mark_paid_batches_payout_cases_notifications_and_audit():
    db = _DB({
        "status": "requested",
        "payout_method": None,
        "attorney_id": "attorney-1",
        "ticket_ids": ["ticket-1", "ticket-2"],
    })

    result = case_lifecycle.mark_payout_paid(
        db, "payout-1", "Choice Digital", "aam@example.com",
    )

    paths = [operation[1] for operation in db.last_batch.operations]
    assert result["idempotent_replay"] is False
    assert paths == [
        "payout_requests/payout-1",
        "tickets/ticket-1",
        "attorney_notifications/payout_sent_payout-1_ticket-1",
        "tickets/ticket-2",
        "attorney_notifications/payout_sent_payout-1_ticket-2",
        "captain_action_audits/payout_paid_payout-1",
    ]
    assert all(not ref.direct_updates for ref in db.refs.values())


def test_mark_paid_failed_batch_is_safe_to_retry():
    db = _DB({
        "status": "requested",
        "payout_method": None,
        "attorney_id": "attorney-1",
        "ticket_ids": ["ticket-1"],
    }, fail=True)

    with pytest.raises(RuntimeError, match="payout_commit_failed"):
        case_lifecycle.mark_payout_paid(
            db, "payout-1", "Choice Digital", "aam@example.com",
        )

    assert all(not ref.direct_updates for ref in db.refs.values())


def test_mark_paid_same_method_replay_is_idempotent():
    db = _DB({
        "status": "paid",
        "payout_method": "Choice Digital",
        "attorney_id": "attorney-1",
        "ticket_ids": ["ticket-1"],
    })

    result = case_lifecycle.mark_payout_paid(
        db, "payout-1", "Choice Digital", "aam@example.com",
    )

    assert result == {
        "ok": True,
        "payout_id": "payout-1",
        "idempotent_replay": True,
    }
    assert db.last_batch.operations == []


def test_mark_paid_commit_failure_returns_retryable_service_error(monkeypatch):
    actor = {
        "uid": "staff-1",
        "email": "aam@example.com",
        "role": "staff",
        "staff_role": "attorney_account_manager",
    }
    monkeypatch.setattr(attorney_workspace, "require_staff", lambda _header: actor)
    monkeypatch.setattr(attorney_workspace, "require_staff_claim", lambda claims, _roles: claims)
    monkeypatch.setattr(attorney_workspace, "require_recent_auth", lambda claims, require_mfa=False: claims)
    monkeypatch.setattr(attorney_workspace, "get_db", lambda: object())
    monkeypatch.setattr(
        attorney_workspace.cl,
        "mark_payout_paid",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("payout_commit_failed")),
    )

    with pytest.raises(HTTPException) as error:
        attorney_workspace.admin_mark_paid(
            "payout-1",
            MarkPaid(payout_method="Choice Digital"),
            "Bearer token",
        )

    assert error.value.status_code == 503
    assert "safe to retry" in error.value.detail
