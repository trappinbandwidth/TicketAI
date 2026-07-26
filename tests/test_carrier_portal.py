"""Route tests for the folded carrier self-serve portal (/api/v1/carrier/*)."""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from io import BytesIO

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.datastructures import Headers, UploadFile
from google.api_core.exceptions import AlreadyExists

from app.routes import carrier_portal, carriers_crm
from app.platform.models import ConsentGrantCreate, DriverCarrierRelationshipCreate
from app.platform.service import PlatformService, principal_id_for_uid


# ── Local fake Firestore (richer than tests.test_platform_identity.FakeDb:
#    auto-ID documents, per-document subcollections, collection stream, update,
#    limit, and batch — everything the carrier portal routes touch). ──────────

class Snapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.update_time = datetime.now(timezone.utc)

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

    def update(self, data, option=None):
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
        ("get", "/api/v1/carrier/discovery/search"),
        ("get", "/api/v1/carrier/discovery/{dot_number}"),
        ("post", "/api/v1/carrier/acquisition/funnel"),
        ("post", "/api/v1/carrier/register"),
        ("get", "/api/v1/carrier/authority-verification"),
        ("post", "/api/v1/carrier/authority-verification/evidence"),
        ("get", "/api/v1/carrier/me"),
        ("patch", "/api/v1/carrier/me"),
        ("get", "/api/v1/carrier/systems"),
        ("put", "/api/v1/carrier/systems"),
        ("get", "/api/v1/carrier/drivers"),
        ("post", "/api/v1/carrier/drivers"),
        ("post", "/api/v1/carrier/drivers/bulk"),
        ("patch", "/api/v1/carrier/drivers/{driver_id}"),
        ("patch", "/api/v1/carrier/drivers/{driver_id}/toggle-active"),
        ("put", "/api/v1/carrier/drivers/{driver_id}/active"),
        ("post", "/api/v1/carrier/drivers/{driver_id}/fire"),
        ("get", "/api/v1/carrier/drivers/{driver_id}/profile"),
        ("get", "/api/v1/carrier/relationships"),
        ("post", "/api/v1/carrier/relationships/connect"),
        ("post", "/api/v1/carrier/relationships/{relationship_id}/end"),
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
    assert "get" in paths["/api/v1/driver/profile/notifications"]
    assert "post" in paths[
        "/api/v1/driver/profile/notifications/{notification_id}/read"
    ]
    assert "get" in paths["/api/v1/driver/profile/employment-history"]
    assert "post" in paths["/api/v1/driver/profile/employment-history"]
    assert "put" in paths[
        "/api/v1/driver/profile/employment-history/{employment_id}"
    ]
    assert "delete" in paths[
        "/api/v1/driver/profile/employment-history/{employment_id}"
    ]
    for legacy in (
            "/api/v1/drivers",
            "/api/v1/fmcsa/safety",
            "/api/v1/subscription",
            "/api/v1/billing",
        ):
        assert legacy not in paths


def test_pre_signup_funnel_events_are_anonymous_idempotent_and_bounded(monkeypatch):
    db = Db()
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)

    def record(event_type, visit_id):
        return carrier_portal.record_acquisition_funnel_event(
            carrier_portal.AcquisitionFunnelEvent(event_type=event_type, visit_id=visit_id)
        )

    assert record("signup_viewed", "visitor-abc123")["ok"] is True
    record("signup_started", "visitor-abc123")

    rows = db.collection("acquisition_events").rows
    assert len(rows) == 2
    for row in rows.values():
        # Privacy-minimized: no principal yet, and the raw client id is never kept.
        assert row["principal_id"] is None
        assert row["funnel"] == "carrier_self_service_pilot"
        assert row["visit_hash"] and row["visit_hash"] != "visitor-abc123"
        assert "visitor-abc123" not in str(row)

    # Idempotent per visitor + step: replaying does not inflate the funnel.
    record("signup_viewed", "visitor-abc123")
    assert len(db.collection("acquisition_events").rows) == 2

    # The open endpoint cannot record authenticated funnel steps.
    for spoofed in ("account_created", "email_verified", "carrier_profile_completed"):
        with pytest.raises(ValidationError):
            carrier_portal.AcquisitionFunnelEvent(event_type=spoofed, visit_id="visitor-abc123")


def test_public_discovery_grants_no_account_authority(monkeypatch):
    record = {
        "dot_number": "1234567",
        "legal_name": "OPEN ROAD FREIGHT LLC",
        "provenance": {"source_kind": "authoritative_public"},
    }
    monkeypatch.setattr(
        carrier_portal, "search_carriers", lambda *_args, **_kwargs: [record]
    )
    monkeypatch.setattr(
        carrier_portal, "carrier_discovery_detail", lambda _dot: record
    )

    results = carrier_portal.discover_carriers(q="Open Road")
    selected = carrier_portal.discover_carrier("USDOT 1234567")

    assert results["carriers"] == [record]
    assert results["account_authority_proven"] is False
    assert selected["carrier"] == record
    assert selected["account_authority_proven"] is False
    assert "does not prove authority" in selected["claim_note"]


def test_selected_fmcsa_registration_reloads_and_preserves_source_snapshot(
    monkeypatch,
):
    db = Db()
    _wire(monkeypatch, db)
    monkeypatch.setattr(
        carrier_portal,
        "carrier_discovery_detail",
        lambda dot: {
            "dot_number": dot,
            "legal_name": "FMCSA LEGAL NAME LLC",
            "dba_name": "FMCSA DBA",
            "operating_status": "Active",
            "provenance": {"source_kind": "authoritative_public"},
        },
    )
    monkeypatch.setattr(
        carrier_portal.fb_auth, "set_custom_user_claims", lambda *_args: None
    )

    result = carrier_portal.register_carrier(
        carrier_portal.CarrierRegistration(
            company_name="Carrier Confirmed Name",
            dot_number="1234567",
            selected_fmcsa_dot_number="USDOT 1234567",
            fmcsa_record_confirmed=True,
        ),
        authorization="Bearer carrier",
    )

    profile = db.collection("carriers").rows[CARRIER_TOKEN["uid"]]
    snapshot = db.collection("carrier_fmcsa_snapshots").rows[
        result["fmcsa_snapshot_id"]
    ]
    assert profile["company_name"] == "Carrier Confirmed Name"
    assert profile["account_authority_status"] == "pending_verification"
    assert snapshot["record"]["legal_name"] == "FMCSA LEGAL NAME LLC"
    assert snapshot["account_authority_proven"] is False
    assert result["account_authority_status"] == "pending_verification"


def test_selected_fmcsa_registration_rejects_mismatch_and_unconfirmed_record(
    monkeypatch,
):
    db = Db()
    _wire(monkeypatch, db)
    monkeypatch.setattr(
        carrier_portal.fb_auth, "set_custom_user_claims", lambda *_args: None
    )
    with pytest.raises(HTTPException) as mismatch:
        carrier_portal.register_carrier(
            carrier_portal.CarrierRegistration(
                company_name="Another",
                dot_number="7654321",
                selected_fmcsa_dot_number="1234567",
                fmcsa_record_confirmed=True,
            ),
            authorization="Bearer carrier",
        )
    assert mismatch.value.status_code == 422
    assert db.collection("carriers").rows == {}

    with pytest.raises(HTTPException) as unconfirmed:
        carrier_portal.register_carrier(
            carrier_portal.CarrierRegistration(
                company_name="Another",
                dot_number="1234567",
                selected_fmcsa_dot_number="1234567",
                fmcsa_record_confirmed=False,
            ),
            authorization="Bearer carrier",
        )
    assert unconfirmed.value.status_code == 422
    assert db.collection("carriers").rows == {}


def test_carrier_notifications_are_principal_scoped_and_read_is_idempotent(
    monkeypatch,
):
    db = Db()
    _wire(monkeypatch, db)
    _register(monkeypatch, db)
    recipient = principal_id_for_uid(CARRIER_TOKEN["uid"])
    service = PlatformService(db)
    db.collection("principal_notifications").document("ntf_owned").set({
        "id": "ntf_owned",
        "recipient_principal_id": recipient,
        "event_type": "relationship_accepted",
        "title": "Driver connection accepted",
        "message": "The Driver accepted.",
        "resource_type": "driver_carrier_relationship",
        "resource_id": "rel_owned",
        "read": False,
        "created_at": "2026-07-25T12:00:00+00:00",
    })
    db.collection("principal_notifications").document("ntf_other").set({
        "id": "ntf_other",
        "recipient_principal_id": principal_id_for_uid("another_carrier"),
        "event_type": "relationship_accepted",
        "title": "Other tenant",
        "message": "Private",
        "resource_type": "driver_carrier_relationship",
        "resource_id": "rel_other",
        "read": False,
        "created_at": "2026-07-25T12:01:00+00:00",
    })

    result = carrier_portal.notifications(authorization="Bearer x")
    assert [item["id"] for item in result["notifications"]] == ["ntf_owned"]
    assert result["unread_count"] == 1

    assert carrier_portal.mark_notification_read(
        "ntf_owned", authorization="Bearer x"
    ) == {"ok": True}
    assert carrier_portal.mark_notification_read(
        "ntf_owned", authorization="Bearer x"
    ) == {"ok": True}
    assert service.list_notifications(recipient)[0]["read"] is True

    with pytest.raises(HTTPException) as cross_tenant:
        carrier_portal.mark_notification_read(
            "ntf_other", authorization="Bearer x"
        )
    assert cross_tenant.value.status_code == 404


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
    assert db.collection("carrier_dot_claims").rows["1234567"]["status"] == "duplicate_disputed"
    authority_claims = db.collection("carrier_authority_claims").rows.values()
    assert {claim["status"] for claim in authority_claims} == {
        "duplicate_disputed"
    }
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


def test_profile_dot_claim_cannot_bypass_duplicate_quarantine_or_change_identity(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    monkeypatch.setattr(carrier_portal.fb_auth, "set_custom_user_claims", lambda *_args: None)
    db.collection("carriers").document("carrier_1").set({
        "company_name": "Big Rig Co",
        "email": "fleet@example.com",
        "verification_status": "unverified",
        "tenant_status": "pending",
    })

    added = carrier_portal.update_my_carrier_profile(
        carrier_portal.CarrierProfileUpdate(dot_number="USDOT 1234567"),
        authorization="Bearer carrier",
    )
    assert "dot_claim_status" in added["updated"]
    profile = db.collection("carriers").rows["carrier_1"]
    assert profile["dot_number"] == "1234567"
    assert profile["dot_claim_status"] == "pending_review"

    with pytest.raises(HTTPException) as changed:
        carrier_portal.update_my_carrier_profile(
            carrier_portal.CarrierProfileUpdate(dot_number="7654321"),
            authorization="Bearer carrier",
        )
    assert changed.value.status_code == 409
    assert db.collection("carriers").rows["carrier_1"]["dot_number"] == "1234567"


def test_profile_settings_validate_normalize_and_audit_routed_fields(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    _register(monkeypatch, db)

    result = carrier_portal.update_my_carrier_profile(
        carrier_portal.CarrierProfileUpdate(
            company_name="  Big   Rig Logistics  ",
            phone="  +1 512 555 0100  ",
            mc_number="  MC-765432  ",
            billing_email="BILLING@EXAMPLE.COM",
            billing_state="tx",
            total_driver_count=100,
        ),
        authorization="Bearer carrier",
    )

    profile = db.collection("carriers").rows[CARRIER_TOKEN["uid"]]
    assert profile["company_name"] == "Big Rig Logistics"
    assert profile["phone"] == "+1 512 555 0100"
    assert profile["mc_number"] == "MC-765432"
    assert profile["billing_email"] == "billing@example.com"
    assert profile["billing_state"] == "TX"
    assert profile["total_driver_count"] == 100
    assert set(result["updated"]) >= {
        "company_name", "phone", "mc_number", "billing_email", "billing_state"
    }
    assert any(
        event["event_type"] == "carrier.profile_updated"
        and "billing_email" in event["payload"]["fields"]
        for event in db.collection("audit_events").rows.values()
    )

    with pytest.raises(ValidationError):
        carrier_portal.CarrierProfileUpdate(billing_email="not-an-email")
    with pytest.raises(ValidationError):
        carrier_portal.CarrierProfileUpdate(billing_state="Texas")
    with pytest.raises(ValidationError):
        carrier_portal.CarrierProfileUpdate(total_driver_count=-1)


def test_systems_replace_normalize_isolate_and_audit(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    _register(monkeypatch, db)

    saved = carrier_portal.update_carrier_systems(
        carrier_portal.CarrierSystemsUpdate(
            eld_provider="  Motive  ",
            tms_system="  McLeod   Software ",
            legal_support_type="outside_firm",
            legal_support="  Example   Transportation Law  ",
        ),
        authorization="Bearer carrier",
    )
    assert saved == {
        "ok": True,
        "systems": {
            "eld_provider": "Motive",
            "tms_system": "McLeod Software",
            "legal_support": "Example Transportation Law",
            "legal_support_type": "outside_firm",
        },
    }
    first = carrier_portal.get_carrier_systems(
        authorization="Bearer carrier"
    )
    assert first["systems"] == saved["systems"]
    assert first["updated_at"]
    assert "updated_at" not in first["systems"]
    assert any(
        event["event_type"] == "carrier.systems_updated"
        and event["payload"]["fields"] == [
            "eld_provider", "legal_support", "legal_support_type", "tms_system"
        ]
        for event in db.collection("audit_events").rows.values()
    )

    # PUT replaces the record, so an omitted field is intentionally cleared.
    carrier_portal.update_carrier_systems(
        carrier_portal.CarrierSystemsUpdate(eld_provider="Samsara"),
        authorization="Bearer carrier",
    )
    assert carrier_portal.get_carrier_systems(
        authorization="Bearer carrier"
    )["systems"] == {"eld_provider": "Samsara"}

    # A second Carrier reads only its own nested systems record.
    second_token = {
        **CARRIER_TOKEN,
        "uid": "carrier_2",
        "email": "second@example.com",
    }
    _wire(monkeypatch, db, token=second_token)
    _register(
        monkeypatch,
        db,
        carrier_portal.CarrierRegistration(
            company_name="Second Carrier", dot_number="7654321"
        ),
    )
    assert carrier_portal.get_carrier_systems(
        authorization="Bearer second"
    )["systems"] == {}


def test_systems_reject_invalid_or_anonymous_input(monkeypatch):
    with pytest.raises(ValidationError):
        carrier_portal.CarrierSystemsUpdate(legal_support_type="unknown")
    with pytest.raises(ValidationError):
        carrier_portal.CarrierSystemsUpdate(eld_provider="x" * 121)

    db = Db()
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)

    def reject(_header):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    monkeypatch.setattr(carrier_portal, "verify_token", reject)
    with pytest.raises(HTTPException) as exc:
        carrier_portal.get_carrier_systems(authorization=None)
    assert exc.value.status_code == 401


def test_carrier_route_rejects_anonymous(monkeypatch):
    db = Db()
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)

    def reject(_header):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    monkeypatch.setattr(carrier_portal, "verify_token", reject)
    with pytest.raises(HTTPException) as exc:
        carrier_portal.get_my_carrier_profile(authorization=None)
    assert exc.value.status_code == 401


def _upload(name: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


def test_document_upload_validates_content_routes_to_owned_bucket_and_deduplicates(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    uploads = []

    class Blob:
        def __init__(self, path):
            self.path = path

        def upload_from_string(self, content, content_type=None):
            uploads.append((self.path, content, content_type))

    class Bucket:
        def blob(self, path):
            return Blob(path)

    monkeypatch.setattr(carrier_portal, "_bucket", lambda: Bucket())
    file = _upload("../unsafe name.pdf", "application/pdf", b"%PDF-pilot")
    first = asyncio.run(carrier_portal.upload_document(
        file=file,
        category="insurance",
        name="Insurance certificate",
        authorization="Bearer carrier",
    ))
    duplicate = asyncio.run(carrier_portal.upload_document(
        file=_upload("../unsafe name.pdf", "application/pdf", b"%PDF-pilot"),
        category="insurance",
        name="Insurance certificate",
        authorization="Bearer carrier",
    ))

    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert duplicate["document_id"] == first["document_id"]
    assert len(uploads) == 1
    assert uploads[0][0].startswith(
        f"carriers/carrier_1/documents/{first['document_id']}_"
    )
    assert ".." not in uploads[0][0]
    document = (
        db.collection("carriers")
        .document("carrier_1")
        .collection("documents")
        .rows[first["document_id"]]
    )
    assert document["file_name"] == "unsafe name.pdf"
    assert document["sha256"]


def test_document_upload_rejects_disguised_content_before_storage(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    monkeypatch.setattr(
        carrier_portal,
        "_bucket",
        lambda: pytest.fail("Storage must not run for invalid content."),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(carrier_portal.upload_document(
            file=_upload("fake.pdf", "application/pdf", b"not-a-pdf"),
            category="insurance",
            name="Fake",
            authorization="Bearer carrier",
        ))

    assert exc.value.status_code == 422


def test_authority_evidence_is_private_idempotent_and_routes_claim_to_review(
    monkeypatch,
):
    db = Db()
    _wire(monkeypatch, db)
    _register(monkeypatch, db)
    uploads = []

    class Blob:
        def __init__(self, path):
            self.path = path

        def upload_from_string(self, content, content_type=None):
            uploads.append((self.path, content, content_type))

    class Bucket:
        def blob(self, path):
            return Blob(path)

    monkeypatch.setattr(carrier_portal, "_bucket", lambda: Bucket())
    initial = carrier_portal.get_authority_verification(
        authorization="Bearer carrier"
    )
    assert initial["claim"]["status"] == "pending_evidence"
    assert initial["evidence"] == []

    first = asyncio.run(carrier_portal.upload_authority_evidence(
        file=_upload("../MCS-150.pdf", "application/pdf", b"%PDF-authority"),
        evidence_method=carrier_portal.AuthorityEvidenceMethod.MCS150,
        authorization="Bearer carrier",
    ))
    replay = asyncio.run(carrier_portal.upload_authority_evidence(
        file=_upload("../MCS-150.pdf", "application/pdf", b"%PDF-authority"),
        evidence_method=carrier_portal.AuthorityEvidenceMethod.MCS150,
        authorization="Bearer carrier",
    ))

    assert first["duplicate"] is False
    assert replay == {**first, "duplicate": True}
    assert len(uploads) == 1
    assert uploads[0][0].startswith(
        "carriers/carrier_1/authority-verification/"
    )
    assert ".." not in uploads[0][0]
    routed = carrier_portal.get_authority_verification(
        authorization="Bearer carrier"
    )
    assert routed["claim"]["status"] == "pending_review"
    assert routed["evidence"][0]["evidence_method"] == "mcs150"
    assert "storage_path" not in routed["evidence"][0]
    assert "sha256" not in routed["evidence"][0]


def test_authority_evidence_rejects_invalid_content_and_storage_failure(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    _register(monkeypatch, db)
    monkeypatch.setattr(
        carrier_portal,
        "_bucket",
        lambda: pytest.fail("Storage must not run for invalid content."),
    )
    with pytest.raises(HTTPException) as invalid:
        asyncio.run(carrier_portal.upload_authority_evidence(
            file=_upload("fake.pdf", "application/pdf", b"not-a-pdf"),
            evidence_method=carrier_portal.AuthorityEvidenceMethod.OTHER,
            authorization="Bearer carrier",
        ))
    assert invalid.value.status_code == 422

    class FailingBlob:
        def upload_from_string(self, *_args, **_kwargs):
            raise RuntimeError("offline")

    class FailingBucket:
        def blob(self, _path):
            return FailingBlob()

    monkeypatch.setattr(carrier_portal, "_bucket", lambda: FailingBucket())
    with pytest.raises(HTTPException) as unavailable:
        asyncio.run(carrier_portal.upload_authority_evidence(
            file=_upload("letter.pdf", "application/pdf", b"%PDF-letter"),
            evidence_method=carrier_portal.AuthorityEvidenceMethod.AUTHORIZATION_LETTER,
            authorization="Bearer carrier",
        ))
    assert unavailable.value.status_code == 503
    assert db.collection("carrier_authority_evidence").rows == {}


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
    assert fired["duplicate"] is False
    fired_replay = carrier_portal.fire_driver(driver_id, authorization="Bearer x")
    assert fired_replay["duplicate"] is True
    assert fired_replay["fired_at"] == fired["fired_at"]
    assert carrier_portal.list_drivers(authorization="Bearer x")["count"] == 0
    assert carrier_portal.list_drivers(include_fired=True, authorization="Bearer x")["count"] == 1

    with pytest.raises(HTTPException) as exc:
        carrier_portal.toggle_driver_active(driver_id, authorization="Bearer x")
    assert exc.value.status_code == 400


def test_set_driver_active_is_desired_state_and_idempotent(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    created = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name="Ada", last_name="Driver", email="ada@example.com"
        ),
        authorization="Bearer carrier",
    )
    first = carrier_portal.set_driver_active(
        created["driver_id"],
        carrier_portal.DriverActiveRequest(active=False),
        authorization="Bearer carrier",
    )
    replay = carrier_portal.set_driver_active(
        created["driver_id"],
        carrier_portal.DriverActiveRequest(active=False),
        authorization="Bearer carrier",
    )
    assert first == {"ok": True, "active": False, "duplicate": False}
    assert replay == {"ok": True, "active": False, "duplicate": True}


def test_roster_create_is_idempotent_and_tenant_scoped(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    first = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name=" Ada ",
            last_name="Lovelace",
            email="ADA@EXAMPLE.COM",
        ),
        authorization="Bearer carrier-1",
    )
    replay = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        ),
        authorization="Bearer carrier-1",
    )
    assert first["duplicate"] is False
    assert replay == {**first, "duplicate": True}
    assert db.collection("carriers").document("carrier_1").collection("drivers").rows[
        first["driver_id"]
    ]["email"] == "ada@example.com"

    _wire(monkeypatch, db, token={
        "uid": "carrier_2",
        "email": "two@example.com",
        "email_verified": True,
        "role": "carrier",
    })
    other_tenant = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        ),
        authorization="Bearer carrier-2",
    )
    assert other_tenant["duplicate"] is False
    assert other_tenant["driver_id"] != first["driver_id"]


def test_roster_update_reconciles_identity_and_rejects_collision(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    first = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name="Ada", last_name="One", email="ada@example.com"
        ),
        authorization="Bearer carrier",
    )
    second = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name="Grace", last_name="Two", email="grace@example.com"
        ),
        authorization="Bearer carrier",
    )

    carrier_portal.update_driver(
        first["driver_id"],
        carrier_portal.DriverUpdate(email="new@example.com"),
        authorization="Bearer carrier",
    )
    replay_new_identity = carrier_portal.create_driver(
        carrier_portal.DriverCreate(
            first_name="Ada", last_name="One", email="NEW@EXAMPLE.COM"
        ),
        authorization="Bearer carrier",
    )
    assert replay_new_identity["duplicate"] is True
    assert replay_new_identity["driver_id"] == first["driver_id"]

    with pytest.raises(HTTPException) as collision:
        carrier_portal.update_driver(
            second["driver_id"],
            carrier_portal.DriverUpdate(email="new@example.com"),
            authorization="Bearer carrier",
        )
    assert collision.value.status_code == 409


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
    assert result["duplicates"] == 0
    listed = carrier_portal.list_drivers(authorization="Bearer x")["drivers"]
    assert sorted(d["cdl_state"] for d in listed) == ["OK", "TX"]

    replay = carrier_portal.bulk_create_drivers(body, authorization="Bearer x")
    assert replay["created"] == 0
    assert replay["duplicates"] == 2
    assert carrier_portal.list_drivers(authorization="Bearer x")["count"] == 2


def test_bulk_is_limited_to_pilot_capacity(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    rows = [
        carrier_portal.DriverCreate(
            first_name="Driver",
            last_name=str(index),
            email=f"driver{index}@example.com",
        )
        for index in range(101)
    ]
    with pytest.raises(HTTPException) as exc:
        carrier_portal.bulk_create_drivers(
            carrier_portal.BulkDriverCreate(drivers=rows),
            authorization="Bearer carrier",
        )
    assert exc.value.status_code == 400


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


def test_fmcsa_returns_separate_named_basic_percentiles_and_safety_rating(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    db.collection("carriers").document("carrier_1").set({
        "company_name": "Big Rig",
        "dot_number": "1234567",
    })
    db.collection("carriers").document("1234567").set({
        "legal_name": "BIG RIG FREIGHT LLC",
        "safety_rating": "Satisfactory",
        "risk_profile": {
            "basics": [
                {"code": "unsafe", "name": "Unsafe Driving", "percentile": 78, "measure": 2.4},
                {"code": "hazmat", "name": "HM Compliance", "percentile": None},
                {"code": "bad", "name": "Invalid source value", "percentile": 140},
            ],
        },
    })

    result = carrier_portal.fmcsa_safety(authorization="Bearer carrier")

    assert result["status"] == "ready"
    assert result["source"] == "FMCSA SMS cached data"
    assert result["safety_rating"] == "Satisfactory"
    assert result["safety_rating_note"].startswith("FMCSA Safety Rating is separate")
    assert result["basics"][0]["metric_name"] == "FMCSA SMS BASIC percentile"
    assert result["basics"][0]["scale"]["direction"] == "0 best; 100 worst"
    assert result["basics"][0]["percentile"] == 78
    assert result["basics"][2]["percentile"] is None
    assert "score" not in result


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


# ── Driver profile privacy boundary ─────────────────────────────────────────

def test_carrier_provided_roster_profile_never_joins_global_ticket_data(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    roster = db.collection("carriers").document("carrier_1").collection("drivers")
    roster.document("drv_1").set({"first_name": "Ada"})
    db.collection("tickets").document("t1").set(
        {"driver_id": "drv_1", "attorney_status": "New"})

    profile = carrier_portal.driver_profile("drv_1", authorization="Bearer x")

    assert profile["driver"]["first_name"] == "Ada"
    assert profile["relationship_status"] == "carrier_provided_roster_only"
    assert profile["safety_summary"] is None
    assert profile["case_data_shared"] is False
    assert "tickets" not in profile

    with pytest.raises(HTTPException) as legal:
        carrier_portal.driver_tickets("drv_1", authorization="Bearer x")
    assert legal.value.status_code == 403


def test_connected_driver_profile_requires_relationship_and_safety_consent(monkeypatch):
    db = Db()
    _wire(monkeypatch, db)
    service = PlatformService(db)
    carrier_principal, _ = service.bootstrap_principal(CARRIER_TOKEN)
    db.collection("carriers").document("carrier_1").set({"company_name": "Big Rig"})
    organization, _, _ = service.bootstrap_role_organization(CARRIER_TOKEN)
    driver_principal, _ = service.bootstrap_principal({
        "uid": "driver_uid",
        "role": "driver",
    })
    relationship, _ = service.create_driver_relationship_invitation(
        carrier_principal.id,
        organization.id,
        DriverCarrierRelationshipCreate(driver_principal_id=driver_principal.id),
    )
    service.respond_to_driver_relationship(driver_principal.id, relationship.id, True)
    service.create_consent(
        driver_principal.id,
        ConsentGrantCreate(
            subject_principal_id=driver_principal.id,
            recipient_organization_id=organization.id,
            purpose="safety_compliance",
            record_categories=["profile", "credential", "employment", "inspection"],
            disclosure_version="carrier-safety-pilot-v1",
        ),
    )
    roster = db.collection("carriers").document("carrier_1").collection("drivers")
    roster.document("roster_1").set({
        "first_name": "Ada",
        "principal_id": driver_principal.id,
    })

    profile = carrier_portal.driver_profile("roster_1", authorization="Bearer carrier")

    assert profile["relationship_status"] == "active_consented"
    assert profile["case_data_shared"] is False
    assert profile["safety_summary"]["driver_principal_id"] == driver_principal.id
    assert "principal_id" not in profile["driver"]


def test_driver_profile_is_scoped_to_authenticated_carrier(monkeypatch):
    db = Db()
    carrier_two_roster = (
        db.collection("carriers")
        .document("carrier_2")
        .collection("drivers")
    )
    carrier_two_roster.document("shared_driver_id").set({"first_name": "Other"})
    _wire(monkeypatch, db, token={"uid": "carrier_1", "role": "carrier"})
    with pytest.raises(HTTPException) as exc:
        carrier_portal.driver_profile("shared_driver_id", authorization="Bearer carrier-1")
    assert exc.value.status_code == 404

    _wire(monkeypatch, db, token={"uid": "carrier_2", "role": "carrier"})
    result = carrier_portal.driver_profile("shared_driver_id", authorization="Bearer carrier-2")
    assert result["driver"]["first_name"] == "Other"
