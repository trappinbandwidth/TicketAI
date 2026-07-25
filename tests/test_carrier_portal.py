"""Route tests for the folded carrier self-serve portal (/api/v1/carrier/*)."""
from __future__ import annotations

import asyncio
import secrets

import pytest
from fastapi import HTTPException
from google.api_core.exceptions import AlreadyExists

from app.routes import carrier_portal, carriers_crm


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

    def create(self, data):
        if self.id in self._coll.rows:
            raise AlreadyExists("already exists")
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

CARRIER_TOKEN = {
    "uid": "carrier_1",
    "email": "fleet@example.com",
    "email_verified": True,
    "role": "carrier",
}


def _wire(monkeypatch, db, token=CARRIER_TOKEN):
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)
    monkeypatch.setattr(carrier_portal, "verify_token", lambda _h: dict(token))


def _register(monkeypatch, db, body=None):
    claims = {}
    monkeypatch.setattr(carrier_portal.fb_auth, "set_custom_user_claims",
                        lambda uid, c: claims.update({uid: c}))
    body = body or carrier_portal.CarrierRegistration(
        company_name="Big Rig Co", dot_number="1234567"
    )
    return carrier_portal.register_carrier(body, authorization="Bearer x"), claims


# ── Consumer/provider contract ───────────────────────────────────────────────

def test_carrier_openapi_matches_frontend_route_matrix():
    from app.main import app

    paths = app.openapi()["paths"]
    expected = {
        ("post", "/api/v1/carrier/register"),
        ("get", "/api/v1/carrier/me"),
        ("patch", "/api/v1/carrier/me"),
        ("get", "/api/v1/carrier/drivers"),
        ("post", "/api/v1/carrier/drivers"),
        ("post", "/api/v1/carrier/drivers/bulk"),
        ("patch", "/api/v1/carrier/drivers/{driver_id}"),
        ("patch", "/api/v1/carrier/drivers/{driver_id}/toggle-active"),
        ("post", "/api/v1/carrier/drivers/{driver_id}/fire"),
        ("get", "/api/v1/carrier/drivers/{driver_id}/profile"),
        ("get", "/api/v1/carrier/fmcsa/safety"),
        ("get", "/api/v1/carrier/subscription"),
        ("get", "/api/v1/carrier/notifications"),
        ("post", "/api/v1/carrier/notifications/{notification_id}/read"),
        ("get", "/api/v1/carrier/billing"),
        ("get", "/api/v1/carrier/documents"),
        ("post", "/api/v1/carrier/documents"),
        ("get", "/api/v1/carrier/documents/{document_id}/download"),
    }
    missing = {
        (method, path)
        for method, path in expected
        if path not in paths or method not in paths[path]
    }
    assert missing == set()
    for legacy in (
            "/api/v1/drivers",
            "/api/v1/fmcsa/safety",
            "/api/v1/subscription",
            "/api/v1/billing",
        ):
        assert legacy not in paths


# ── Registration + profile ───────────────────────────────────────────────────

def test_register_sets_claim_creates_profile_and_is_idempotent(monkeypatch):
    db = Db()
    _wire(monkeypatch, db, token={
        "uid": "carrier_1",
        "email": "fleet@example.com",
        "email_verified": True,
    })  # no role yet
    first, claims = _register(monkeypatch, db)
    assert first["carrier_id"] == "carrier_1"
    assert first["already_registered"] is False
    assert first["dot_claim_status"] == "pending_review"
    assert first["tenant_status"] == "pending"
    assert first["token_refresh_required"] is True
    assert claims["carrier_1"]["role"] == "carrier"
    assert claims["carrier_1"]["carrier_id"] == "carrier_1"
    assert claims["carrier_1"]["organization_id"] == first["organization_id"]
    assert db.collection("carriers").rows["carrier_1"]["subscription_status"] == "trial"
    assert db.collection("carriers").rows["carrier_1"]["verification_status"] == "unverified"
    assert len(db.collection("organizations").rows) == 1
    assert len(db.collection("organization_memberships").rows) == 1
    assert len(db.collection("acquisition_events").rows) == 3

    second, _ = _register(monkeypatch, db)
    assert second["already_registered"] is True
    assert second["organization_id"] == first["organization_id"]
    assert len(db.collection("organizations").rows) == 1
    assert len(db.collection("acquisition_events").rows) == 3


def test_register_requires_verified_email_and_rejects_existing_other_role(monkeypatch):
    db = Db()
    _wire(monkeypatch, db, token={
        "uid": "carrier_1",
        "email": "fleet@example.com",
        "email_verified": False,
    })
    with pytest.raises(HTTPException) as exc:
        _register(monkeypatch, db)
    assert exc.value.status_code == 403
    assert not db.collection("carriers").rows

    _wire(monkeypatch, db, token={
        "uid": "carrier_1",
        "email": "fleet@example.com",
        "email_verified": True,
        "role": "driver",
    })
    with pytest.raises(HTTPException) as exc:
        _register(monkeypatch, db)
    assert exc.value.status_code == 403
    assert not db.collection("carriers").rows


def test_register_quarantines_duplicate_dot_without_merging_tenants(monkeypatch):
    db = Db()
    first_token = {
        "uid": "carrier_1",
        "email": "one@example.com",
        "email_verified": True,
    }
    _wire(monkeypatch, db, token=first_token)
    first, _ = _register(monkeypatch, db)

    second_token = {
        "uid": "carrier_2",
        "email": "two@example.com",
        "email_verified": True,
    }
    _wire(monkeypatch, db, token=second_token)
    second, _ = _register(monkeypatch, db)

    assert first["organization_id"] != second["organization_id"]
    assert second["dot_claim_status"] == "duplicate_disputed"
    assert second["tenant_status"] == "quarantined"
    assert db.collection("carriers").rows["carrier_1"]["tenant_status"] == "quarantined"
    assert db.collection("carriers").rows["carrier_2"]["tenant_status"] == "quarantined"
    assert len(db.collection("organizations").rows) == 2


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


def test_carrier_route_rejects_anonymous(monkeypatch):
    db = Db()
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)

    def reject(_header):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    monkeypatch.setattr(carrier_portal, "verify_token", reject)
    with pytest.raises(HTTPException) as exc:
        carrier_portal.get_my_carrier_profile(authorization=None)
    assert exc.value.status_code == 401


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


def test_subscription_uses_integer_cents_without_guessing_legacy_units(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    carrier = db.collection("carriers").document("carrier_1")
    carrier.set({"per_driver_rate_cents": 900, "per_driver_rate": 11.99})
    carrier.collection("drivers").document("d1").set({"active": True})
    carrier.collection("drivers").document("d2").set({"active": True})

    result = carrier_portal.subscription(authorization="Bearer x")

    assert result["per_driver_rate_cents"] == 900
    assert result["estimated_monthly_cents"] == 1800
    assert "per_driver_rate" not in result
    assert "estimated_monthly" not in result

    carrier.set({"per_driver_rate": 11.99})
    unresolved = carrier_portal.subscription(authorization="Bearer x")
    assert unresolved["per_driver_rate_cents"] is None
    assert unresolved["pricing_data_status"] == "legacy_unit_unresolved"


def test_crm_keeps_record_id_and_dot_identifier_distinct(monkeypatch):
    db = Db()
    db.collection("carriers").document("carrier_uuid").set(
        {"company_name": "Big Rig", "dot_number": "1234567"}
    )
    db.collection("drivers").document("driver_1").set(
        {"full_name": "Ada Driver", "carrier_id": "carrier_uuid"}
    )
    monkeypatch.setattr(carriers_crm, "_db", lambda: db)
    monkeypatch.setattr(carriers_crm, "require_staff", lambda _authorization: {})

    carrier = asyncio.run(carriers_crm.get_carrier("1234567", authorization="Bearer staff"))
    roster = asyncio.run(
        carriers_crm.get_carrier_drivers("1234567", authorization="Bearer staff")
    )

    assert carrier["carrier_id"] == "carrier_uuid"
    assert carrier["dot_number"] == "1234567"
    assert roster["carrier_id"] == "carrier_uuid"
    assert roster["dot_number"] == "1234567"
    assert roster["drivers"][0]["driver_id"] == "driver_1"


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


def test_driver_profile_is_scoped_to_authenticated_carrier(monkeypatch):
    db = Db()
    carrier_two_roster = (
        db.collection("carriers")
        .document("carrier_2")
        .collection("drivers")
    )
    carrier_two_roster.document("shared_driver_id").set({"first_name": "Other"})
    monkeypatch.setattr(carrier_portal, "shadow_enabled", lambda: False)

    _wire(monkeypatch, db, token={"uid": "carrier_1", "role": "carrier"})
    with pytest.raises(HTTPException) as exc:
        carrier_portal.driver_profile("shared_driver_id", authorization="Bearer carrier-1")
    assert exc.value.status_code == 404

    _wire(monkeypatch, db, token={"uid": "carrier_2", "role": "carrier"})
    result = carrier_portal.driver_profile("shared_driver_id", authorization="Bearer carrier-2")
    assert result["driver"]["first_name"] == "Other"
