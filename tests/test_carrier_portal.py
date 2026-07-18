"""Route tests for the folded carrier self-serve portal (/api/v1/carrier/*)."""
from __future__ import annotations

import secrets

import pytest
from fastapi import HTTPException

from app.routes import carrier_portal


# ── Local fake Firestore (richer than tests.test_platform_identity.FakeDb:
#    auto-ID documents, per-document subcollections, collection stream, update,
#    limit, and batch — everything the carrier portal routes touch). ──────────

class Snapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class Document:
    def __init__(self, coll, doc_id):
        self._coll = coll
        self.id = doc_id

    def get(self):
        return Snapshot(self.id, self._coll.rows.get(self.id))

    def set(self, data, merge=False):
        if merge and self.id in self._coll.rows:
            self._coll.rows[self.id].update(data)
        else:
            self._coll.rows[self.id] = dict(data)

    def update(self, data):
        if self.id not in self._coll.rows:
            raise KeyError(self.id)
        self._coll.rows[self.id].update(data)

    def collection(self, name):
        return self._coll.subs.setdefault((self.id, name), Collection())


class Query:
    def __init__(self, coll, field, value, limit_n=None):
        self._coll, self._field, self._value, self._limit = coll, field, value, limit_n

    def limit(self, n):
        return Query(self._coll, self._field, self._value, n)

    def stream(self):
        out = [Snapshot(doc_id, row) for doc_id, row in self._coll.rows.items()
               if row.get(self._field) == self._value]
        return out[: self._limit] if self._limit else out


class Collection:
    def __init__(self):
        self.rows = {}
        self.subs = {}

    def document(self, doc_id=None):
        return Document(self, doc_id or f"auto_{secrets.token_hex(4)}")

    def where(self, field, op, value):
        assert op == "=="
        return Query(self, field, value)

    def stream(self):
        return [Snapshot(doc_id, row) for doc_id, row in self.rows.items()]


class Batch:
    def __init__(self):
        self._ops = []

    def set(self, doc, data):
        self._ops.append((doc, data))

    def commit(self):
        for doc, data in self._ops:
            doc.set(data)


class Db:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


# ── Helpers ──────────────────────────────────────────────────────────────────

CARRIER_TOKEN = {"uid": "carrier_1", "email": "fleet@example.com", "role": "carrier"}


def _wire(monkeypatch, db, token=CARRIER_TOKEN):
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)
    monkeypatch.setattr(carrier_portal, "verify_token", lambda _h: dict(token))


def _register(monkeypatch, db):
    claims = {}
    monkeypatch.setattr(carrier_portal.fb_auth, "set_custom_user_claims",
                        lambda uid, c: claims.update({uid: c}))
    body = carrier_portal.CarrierRegistration(company_name="Big Rig Co", dot_number="1234567")
    return carrier_portal.register_carrier(body, authorization="Bearer x"), claims


# ── Registration + profile ───────────────────────────────────────────────────

def test_register_sets_claim_creates_profile_and_is_idempotent(monkeypatch):
    db = Db()
    _wire(monkeypatch, db, token={"uid": "carrier_1", "email": "fleet@example.com"})  # no role yet
    first, claims = _register(monkeypatch, db)
    assert first == {"ok": True, "carrier_id": "carrier_1", "already_registered": False}
    assert claims == {"carrier_1": {"role": "carrier"}}
    assert db.collection("carriers").rows["carrier_1"]["subscription_status"] == "trial"

    second, _ = _register(monkeypatch, db)
    assert second["already_registered"] is True


def test_me_requires_carrier_role_and_returns_profile(monkeypatch):
    db = Db()
    _wire(monkeypatch, db, token={"uid": "carrier_1", "role": "driver"})
    with pytest.raises(HTTPException) as exc:
        carrier_portal.get_my_carrier_profile(authorization="Bearer x")
    assert exc.value.status_code == 403

    _wire(monkeypatch, db)
    with pytest.raises(HTTPException) as exc:
        carrier_portal.get_my_carrier_profile(authorization="Bearer x")
    assert exc.value.status_code == 404

    _register(monkeypatch, db)
    profile = carrier_portal.get_my_carrier_profile(authorization="Bearer x")
    assert profile["carrier_id"] == "carrier_1"
    assert profile["company_name"] == "Big Rig Co"


# ── Roster lifecycle ─────────────────────────────────────────────────────────

def test_roster_create_toggle_fire_lifecycle(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    created = carrier_portal.create_driver(
        carrier_portal.DriverCreate(first_name="Ada", last_name="Lovelace", cdl_number="C1", cdl_state="tx"),
        authorization="Bearer x")
    driver_id = created["driver_id"]

    assert carrier_portal.list_drivers(authorization="Bearer x")["count"] == 1

    toggled = carrier_portal.toggle_driver_active(driver_id, authorization="Bearer x")
    assert toggled["active"] is False

    fired = carrier_portal.fire_driver(driver_id, authorization="Bearer x")
    assert fired["ok"] is True
    assert carrier_portal.list_drivers(authorization="Bearer x")["count"] == 0
    assert carrier_portal.list_drivers(include_fired=True, authorization="Bearer x")["count"] == 1

    with pytest.raises(HTTPException) as exc:
        carrier_portal.toggle_driver_active(driver_id, authorization="Bearer x")
    assert exc.value.status_code == 400


def test_bulk_rejects_duplicate_cdl_and_commits_nothing(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    body = carrier_portal.BulkDriverCreate(drivers=[
        carrier_portal.DriverCreate(first_name="A", last_name="One", cdl_number="X1", cdl_state="TX"),
        carrier_portal.DriverCreate(first_name="B", last_name="Two", cdl_number="x1", cdl_state="tx"),
    ])
    with pytest.raises(HTTPException) as exc:
        carrier_portal.bulk_create_drivers(body, authorization="Bearer x")
    assert exc.value.status_code == 422
    assert carrier_portal.list_drivers(authorization="Bearer x")["count"] == 0


def test_bulk_commits_valid_rows_and_uppercases_state(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    body = carrier_portal.BulkDriverCreate(drivers=[
        carrier_portal.DriverCreate(first_name="A", last_name="One", cdl_number="X1", cdl_state="tx"),
        carrier_portal.DriverCreate(first_name="B", last_name="Two", cdl_number="X2", cdl_state="ok"),
    ])
    result = carrier_portal.bulk_create_drivers(body, authorization="Bearer x")
    assert result["created"] == 2
    listed = carrier_portal.list_drivers(authorization="Bearer x")["drivers"]
    assert sorted(d["cdl_state"] for d in listed) == ["OK", "TX"]


# ── Driver profile + shadow ──────────────────────────────────────────────────

def test_driver_profile_returns_tickets_and_emits_shadow_when_enabled(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    db.collection("carriers").document("carrier_1").set(
        {"company_name": "Big Rig Co", "organization_id": "org_carrier_1"})
    roster = db.collection("carriers").document("carrier_1").collection("drivers")
    roster.document("drv_1").set({"first_name": "Ada", "principal_id": "prn_drv_1"})
    db.collection("tickets").document("t1").set(
        {"driver_id": "drv_1", "attorney_status": "New"})
    db.collection("tickets").document("t2").set(
        {"driver_id": "drv_1", "attorney_status": "Ticket Closed"})

    calls = []
    monkeypatch.setattr(carrier_portal, "shadow_enabled", lambda: True)
    monkeypatch.setattr(carrier_portal, "shadow_authorization",
                        lambda _db, _claims, **kw: calls.append(kw) or "cmp_1")

    profile = carrier_portal.driver_profile("drv_1", authorization="Bearer x")

    assert profile["ticket_count"] == 2
    assert profile["open_ticket_count"] == 1
    assert len(calls) == 1
    assert calls[0]["tenant_id"] == "org_carrier_1"
    assert calls[0]["subject_principal_id"] == "prn_drv_1"
    assert calls[0]["resource_type"] == "driver_profile"


def test_driver_profile_skips_shadow_read_when_disabled(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    roster = db.collection("carriers").document("carrier_1").collection("drivers")
    roster.document("drv_1").set({"first_name": "Ada"})

    monkeypatch.setattr(carrier_portal, "shadow_enabled", lambda: False)
    monkeypatch.setattr(carrier_portal, "shadow_authorization",
                        lambda *a, **kw: pytest.fail("shadow must not be called when disabled"))

    profile = carrier_portal.driver_profile("drv_1", authorization="Bearer x")
    assert profile["driver"]["first_name"] == "Ada"
