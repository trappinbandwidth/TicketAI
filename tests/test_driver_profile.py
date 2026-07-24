import base64

import pytest
from fastapi import HTTPException

from app.routes import _common, driver_profile
from app.services import firebase_service
from app.services.driver_profile import (
    DriverProfileService,
    PiiCipher,
    decode_avatar,
)


class Snapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class Document:
    def __init__(self, collection, key):
        self.collection = collection
        self.key = key

    def get(self):
        return Snapshot(self.collection.rows.get(self.key))

    def set(self, value):
        self.collection.rows[self.key] = dict(value)


class Collection:
    def __init__(self):
        self.rows = {}

    def document(self, key):
        return Document(self, key)


class Batch:
    def __init__(self):
        self.writes = []

    def set(self, document, value):
        self.writes.append((document, dict(value)))

    def commit(self):
        for document, value in self.writes:
            document.set(value)


class Db:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


def profile_body(**overrides):
    values = {
        "first_name": "Ada",
        "middle_initial": "M",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone": "+15125550101",
        "dob": "1988-04-12",
        "cdl_number": "TX8841203",
        "cdl_state": "TX",
        "cdl_expiration": "2027-09-30",
        "address": {
            "street": "1420 Rig Way",
            "city": "San Antonio",
            "state": "TX",
            "zip": "78201",
        },
        "ssn_last4": "4412",
        "driver_role": "company_driver",
        "carrier_name": "Big Rig Freight Co",
        "profile_image": "data:image/jpeg;base64,"
        + base64.b64encode(b"\xff\xd8\xff\xe0synthetic-jpeg").decode(),
    }
    values.update(overrides)
    return driver_profile.DriverProfileUpdate(**values)


def test_get_db_reads_handle_created_during_initialization(monkeypatch):
    expected = object()
    monkeypatch.setattr(firebase_service, "_firestore_client", None)
    monkeypatch.setattr(
        firebase_service,
        "_init",
        lambda: setattr(firebase_service, "_firestore_client", expected),
    )

    assert _common.get_db() is expected


def test_save_separates_sensitive_fields_and_encrypts_ssn():
    db = Db()
    cipher = PiiCipher(b"\x07" * 32, "test-v1")
    service = DriverProfileService(
        db,
        cipher,
        avatar_uploader=lambda uid, _image: f"driver_profiles/{uid}/avatar.jpg",
    )

    result = service.save("driver_1", profile_body(), phone="+15125550101")

    public = db.collection("drivers").rows["driver_1"]
    private = db.collection("driver_private").rows["driver_1"]
    assert public["profile_complete"] is True
    assert public["profile_image_path"] == "driver_profiles/driver_1/avatar.jpg"
    for key in ("ssn_last4", "dob", "address", "cdl_number", "cdl_expiration", "profile_image"):
        assert key not in public
    assert private["cdl_number"] == "TX8841203"
    assert private["ssn_last4_encrypted"]["algorithm"] == "AES-256-GCM"
    assert "4412" not in str(private["ssn_last4_encrypted"])
    assert result["ssn_last4_present"] is True
    assert "ssn_last4" not in result


def test_save_removes_legacy_plaintext_from_public_profile():
    db = Db()
    db.collection("drivers").rows["driver_1"] = {
        "plan": "pro",
        "ssn_last4": "4412",
        "dob": "1988-04-12",
        "address": {"street": "legacy"},
        "cdl_number": "LEGACY",
        "profile_image": "data:image/jpeg;base64,legacy",
    }
    service = DriverProfileService(
        db,
        PiiCipher(b"\x07" * 32, "test-v1"),
        avatar_uploader=lambda uid, _image: f"driver_profiles/{uid}/avatar.jpg",
    )

    service.save("driver_1", profile_body())

    public = db.collection("drivers").rows["driver_1"]
    assert public["plan"] == "pro"
    assert not set(public).intersection(
        {"ssn_last4", "dob", "address", "cdl_number", "cdl_expiration", "profile_image"}
    )


def test_cipher_fails_closed_without_valid_key(monkeypatch):
    monkeypatch.delenv("PII_ENCRYPTION_KEY_B64", raising=False)
    monkeypatch.delenv("PII_ENCRYPTION_KEY_ID", raising=False)

    with pytest.raises(HTTPException) as exc:
        PiiCipher.from_env()

    assert exc.value.status_code == 503


def test_avatar_validation_rejects_bad_type_and_oversize():
    with pytest.raises(HTTPException) as bad:
        decode_avatar("data:text/plain;base64,SGVsbG8=")
    assert bad.value.status_code == 422

    mismatch = "data:image/png;base64," + base64.b64encode(b"not-a-png").decode()
    with pytest.raises(HTTPException) as disguised:
        decode_avatar(mismatch)
    assert disguised.value.status_code == 422

    huge = "data:image/jpeg;base64," + base64.b64encode(
        b"\xff\xd8\xff" + b"x" * (512 * 1024)
    ).decode()
    with pytest.raises(HTTPException) as large:
        decode_avatar(huge)
    assert large.value.status_code == 413


def test_profile_route_rejects_wrong_role(monkeypatch):
    monkeypatch.setattr(
        driver_profile,
        "verify_firebase_token",
        lambda _header: {"uid": "carrier_1", "role": "carrier"},
    )

    with pytest.raises(HTTPException) as exc:
        driver_profile.get_profile(authorization="Bearer carrier")

    assert exc.value.status_code == 403


def test_profile_route_uses_token_uid(monkeypatch):
    seen = {}

    class Service:
        def get(self, uid, phone=None):
            seen.update(uid=uid, phone=phone)
            return {"driver_id": uid}

    monkeypatch.setattr(
        driver_profile,
        "verify_firebase_token",
        lambda _header: {
            "uid": "driver_from_token",
            "role": "driver",
            "phone_number": "+15125550101",
        },
    )
    monkeypatch.setattr(driver_profile, "_service", lambda: Service())

    result = driver_profile.get_profile(authorization="Bearer driver")

    assert result == {"driver_id": "driver_from_token"}
    assert seen == {"uid": "driver_from_token", "phone": "+15125550101"}
