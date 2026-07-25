from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.platform.service import PlatformService
from app.routes import carrier_portal, driver_profile
from app.services.carrier_resolve import CarrierResolveService
from tests.test_platform_identity import FakeDb


DRIVER = {"uid": "driver_uid", "role": "driver", "phone_number": "+15125550101"}
CARRIER = {
    "uid": "carrier_uid",
    "role": "carrier",
    "email": "fleet@example.com",
    "email_verified": True,
}


def setup_connection_stack(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(driver_profile, "get_db", lambda: db)
    monkeypatch.setattr(driver_profile, "verify_firebase_token", lambda _header: DRIVER)
    monkeypatch.setattr(carrier_portal, "get_db", lambda: db)
    monkeypatch.setattr(carrier_portal, "verify_token", lambda _header: CARRIER)
    monkeypatch.setattr(carrier_portal.fb_auth, "set_custom_user_claims", lambda *_args: None)

    service = PlatformService(db)
    service.bootstrap_principal(CARRIER)
    db.collection("carriers").document(CARRIER["uid"]).set({
        "company_name": "Open Road Freight",
        "email": CARRIER["email"],
        "verification_status": "unverified",
        "tenant_status": "pending",
        "dot_claim_status": "not_provided",
    })
    organization, _, _ = service.bootstrap_role_organization(CARRIER)
    return db, organization.id


def test_one_time_code_creates_invitation_then_driver_controls_consent(monkeypatch):
    db, organization_id = setup_connection_stack(monkeypatch)

    issued = driver_profile.create_carrier_connection_code(authorization="Bearer driver")
    assert len(issued["code"].replace("-", "")) == 12

    connected = carrier_portal.connect_driver(
        carrier_portal.DriverConnectionRequest(code=issued["code"]),
        authorization="Bearer carrier",
    )
    relationship = connected["relationship"]
    assert connected["created"] is True
    assert relationship.carrier_organization_id == organization_id
    assert relationship.status.value == "invited"

    with pytest.raises(HTTPException) as replay:
        carrier_portal.connect_driver(
            carrier_portal.DriverConnectionRequest(code=issued["code"]),
            authorization="Bearer carrier",
        )
    assert replay.value.status_code == 409

    driver_view = driver_profile.list_carrier_relationships(
        authorization="Bearer driver"
    )
    assert len(driver_view["relationships"]) == 1
    assert driver_view["consents"] == []

    accepted = driver_profile.respond_to_carrier_relationship(
        relationship.id,
        driver_profile.RelationshipResponse(accept=True),
        authorization="Bearer driver",
    )
    assert accepted["relationship"].status.value == "active"

    consent_result = driver_profile.grant_carrier_safety_consent(
        relationship.id,
        driver_profile.SafetyConsentRequest(
            disclosure_version="carrier-safety-pilot-v1"
        ),
        authorization="Bearer driver",
    )
    consent = consent_result["consent"]
    assert consent.recipient_organization_id == organization_id
    assert consent.record_categories == [
        "profile", "credential", "employment", "inspection"
    ]

    carrier_summary = CarrierResolveService(db).driver_summary(
        relationship.invited_by_principal_id,
        organization_id,
        relationship.driver_principal_id,
    )
    assert carrier_summary["consent_id"] == consent.id

    ended = carrier_portal.end_driver_relationship(
        relationship.id,
        carrier_portal.EndDriverRelationshipRequest(reason="Employment ended"),
        authorization="Bearer carrier",
    )
    assert ended["relationship"].status.value == "ended"
    with pytest.raises(PermissionError, match="relationship"):
        CarrierResolveService(db).driver_summary(
            relationship.invited_by_principal_id,
            organization_id,
            relationship.driver_principal_id,
        )

    revoked = driver_profile.revoke_carrier_safety_consent(
        consent.id,
        driver_profile.RevokeSafetyConsentRequest(reason="Employment ended"),
        authorization="Bearer driver",
    )
    assert revoked["consent"].status.value == "revoked"

    acquisition = db.collection("acquisition_events").rows
    assert any(
        event["event_type"] == "first_driver_relationship_requested"
        for event in acquisition.values()
    )


def test_connection_code_is_not_a_consent_and_wrong_driver_cannot_respond(monkeypatch):
    _, _ = setup_connection_stack(monkeypatch)
    issued = driver_profile.create_carrier_connection_code(authorization="Bearer driver")
    connected = carrier_portal.connect_driver(
        carrier_portal.DriverConnectionRequest(
            code=issued["code"], relationship_type="contractor"
        ),
        authorization="Bearer carrier",
    )
    relationship = connected["relationship"]

    monkeypatch.setattr(
        driver_profile,
        "verify_firebase_token",
        lambda _header: {"uid": "other_driver", "role": "driver"},
    )
    with pytest.raises(HTTPException) as wrong_driver:
        driver_profile.respond_to_carrier_relationship(
            relationship.id,
            driver_profile.RelationshipResponse(accept=True),
            authorization="Bearer other",
        )
    assert wrong_driver.value.status_code == 403

    with pytest.raises(HTTPException) as no_consent:
        driver_profile.grant_carrier_safety_consent(
            relationship.id,
            driver_profile.SafetyConsentRequest(
                disclosure_version="carrier-safety-pilot-v1"
            ),
            authorization="Bearer other",
        )
    assert no_consent.value.status_code == 404
