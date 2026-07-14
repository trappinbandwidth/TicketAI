import pytest
from fastapi import HTTPException

from app.services import auth_rbac


def test_verify_firebase_token_requires_bearer_header():
    with pytest.raises(HTTPException) as exc:
        auth_rbac.verify_firebase_token(None)

    assert exc.value.status_code == 401


def test_verify_firebase_token_returns_decoded_claims(monkeypatch):
    monkeypatch.setattr(
        auth_rbac.fb_auth,
        "verify_id_token",
        lambda token: {"uid": "u1", "role": "staff", "token": token},
    )

    decoded = auth_rbac.verify_firebase_token("Bearer token-123")

    assert decoded["uid"] == "u1"
    assert decoded["token"] == "token-123"


def test_require_staff_accepts_staff_role_claim():
    decoded = {"uid": "u1", "role": "staff", "staff_role": "account_manager"}

    assert auth_rbac.require_staff(decoded) is decoded
    assert auth_rbac.require_staff(decoded, ["account_manager"]) is decoded


def test_require_staff_rejects_wrong_role():
    with pytest.raises(HTTPException) as exc:
        auth_rbac.require_staff({"uid": "u1", "role": "carrier"})

    assert exc.value.status_code == 403


def test_require_staff_rejects_wrong_staff_role():
    with pytest.raises(HTTPException) as exc:
        auth_rbac.require_staff(
            {"uid": "u1", "role": "staff", "staff_role": "ops_staff"},
            ["super_admin"],
        )

    assert exc.value.status_code == 403


def test_require_carrier_scopes_carrier_id():
    decoded = {"uid": "u1", "role": "carrier", "carrier_id": "carrier_1"}

    assert auth_rbac.require_carrier(decoded, "carrier_1") is decoded

    with pytest.raises(HTTPException) as exc:
        auth_rbac.require_carrier(decoded, "carrier_2")

    assert exc.value.status_code == 403


def test_require_attorney_scopes_attorney_id():
    decoded = {"uid": "u1", "role": "attorney", "attorney_id": "attorney_1"}

    assert auth_rbac.require_attorney(decoded, "attorney_1") is decoded

    with pytest.raises(HTTPException) as exc:
        auth_rbac.require_attorney(decoded, "attorney_2")

    assert exc.value.status_code == 403
