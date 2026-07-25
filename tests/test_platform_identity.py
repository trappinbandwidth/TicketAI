from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.platform.models import (
    AuthorizationRequest,
    ConsentGrant,
    ConsentGrantCreate,
    ConsentStatus,
    Membership,
    MembershipStatus,
    DriverCarrierRelationshipCreate,
    RelationshipStatus,
    OrganizationCreate,
    OrganizationType,
    Principal,
    PrincipalStatus,
    utc_now,
    DelegatedAccessGrantCreate,
)
from app.platform.service import PlatformService, evaluate_authorization, principal_id_for_uid


class FakeSnapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None
        self.update_time = datetime.now(timezone.utc)

    def to_dict(self):
        return self._data


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def get(self):
        return FakeSnapshot(self.collection.rows.get(self.document_id))

    def set(self, data, merge=False):
        if merge and self.document_id in self.collection.rows:
            self.collection.rows[self.document_id].update(data)
        else:
            self.collection.rows[self.document_id] = dict(data)

    def create(self, data):
        if self.document_id in self.collection.rows:
            from google.api_core.exceptions import AlreadyExists
            raise AlreadyExists("already exists")
        self.collection.rows[self.document_id] = dict(data)

    def update(self, data, option=None):
        if self.document_id not in self.collection.rows:
            raise KeyError(self.document_id)
        self.collection.rows[self.document_id].update(data)


class FakeQuery:
    def __init__(self, collection, field, value):
        self.collection = collection
        self.field = field
        self.value = value

    def stream(self):
        return [FakeSnapshot(row) for row in self.collection.rows.values() if row.get(self.field) == self.value]


class FakeCollection:
    def __init__(self):
        self.rows = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def where(self, field, operator, value):
        assert operator == "=="
        return FakeQuery(self, field, value)


class FakeDb:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


def test_principal_id_is_stable_and_does_not_expose_uid():
    principal_id = principal_id_for_uid("firebase-user-123")

    assert principal_id == principal_id_for_uid("firebase-user-123")
    assert "firebase-user-123" not in principal_id


def test_bootstrap_is_idempotent_and_links_role_profile():
    db = FakeDb()
    service = PlatformService(db)
    claims = {
        "uid": "driver-uid",
        "role": "driver",
        "email": "driver@example.com",
        "phone_number": "+13145551234",
    }

    first, first_created = service.bootstrap_principal(claims)
    second, second_created = service.bootstrap_principal(claims)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert first.email_masked == "d***@example.com"
    assert first.phone_masked == "***-***-1234"
    assert db.collection("drivers").rows["driver-uid"]["principal_id"] == first.id
    assert len(db.collection("principals").rows) == 1
    assert len(db.collection("audit_events").rows) == 1


def test_consent_requires_recipient_and_self_grant():
    with pytest.raises(ValidationError):
        ConsentGrantCreate(
            subject_principal_id="prn_driver",
            purpose="case_management",
            record_categories=["case"],
            disclosure_version="v1",
        )

    db = FakeDb()
    service = PlatformService(db)
    body = ConsentGrantCreate(
        subject_principal_id="prn_driver",
        recipient_organization_id="org_carrier",
        purpose="case_management",
        record_categories=["credential"],
        disclosure_version="v1",
    )
    with pytest.raises(PermissionError):
        service.create_consent("prn_someone_else", body)


def test_revocation_is_idempotent_and_blocks_policy_access():
    db = FakeDb()
    service = PlatformService(db)
    body = ConsentGrantCreate(
        subject_principal_id="prn_driver",
        recipient_organization_id="org_carrier",
        purpose="case_management",
        record_categories=["credential"],
        actions=["read"],
        disclosure_version="v1",
    )
    consent = service.create_consent("prn_driver", body)
    revoked = service.revoke_consent("prn_driver", consent.id, "employment ended")
    again = service.revoke_consent("prn_driver", consent.id, "ignored")

    assert revoked.status == ConsentStatus.REVOKED
    assert again.revocation_reason == "employment ended"

    actor = Principal(id="prn_manager", firebase_uid="manager")
    membership = Membership(
        id="mem_1",
        organization_id="org_carrier",
        principal_id=actor.id,
        role="safety_manager",
        status=MembershipStatus.ACTIVE,
        effective_at=utc_now() - timedelta(days=1),
        created_by=actor.id,
    )
    request = AuthorizationRequest(
        action="read",
        resource_type="credential",
        resource_id="cred_1",
        tenant_id="org_carrier",
        purpose="safety_compliance",
        record_category="credential",
        subject_principal_id="prn_driver",
    )
    decision = evaluate_authorization(actor, request, [membership], [again])
    assert decision.allowed is False
    assert decision.reason == "active_matching_consent_required"


def test_policy_denies_cross_tenant_and_terminal_mismatch():
    actor = Principal(id="prn_manager", firebase_uid="manager")
    membership = Membership(
        id="mem_1",
        organization_id="org_a",
        principal_id=actor.id,
        role="safety_manager",
        terminal_ids=["terminal_1"],
        status=MembershipStatus.ACTIVE,
        effective_at=utc_now() - timedelta(days=1),
        created_by=actor.id,
    )

    cross_tenant = evaluate_authorization(
        actor,
        AuthorizationRequest(action="read", resource_type="case", resource_id="case_1", tenant_id="org_b"),
        [membership],
        [],
    )
    wrong_terminal = evaluate_authorization(
        actor,
        AuthorizationRequest(
            action="read",
            resource_type="case",
            resource_id="case_1",
            tenant_id="org_a",
            terminal_id="terminal_2",
        ),
        [membership],
        [],
    )

    assert cross_tenant.reason == "active_tenant_membership_required"
    assert wrong_terminal.reason == "active_tenant_membership_required"


def test_policy_requires_matching_purpose_category_and_action():
    actor = Principal(id="prn_manager", firebase_uid="manager")
    membership = Membership(
        id="mem_1",
        organization_id="org_carrier",
        principal_id=actor.id,
        role="safety_manager",
        status=MembershipStatus.ACTIVE,
        effective_at=utc_now() - timedelta(days=1),
        created_by=actor.id,
    )
    consent = ConsentGrant(
        id="cns_1",
        grantor_principal_id="prn_driver",
        subject_principal_id="prn_driver",
        recipient_organization_id="org_carrier",
        purpose="safety_compliance",
        record_categories=["credential"],
        actions=["read"],
        disclosure_version="v1",
    )
    base = dict(
        resource_type="credential",
        resource_id="cred_1",
        tenant_id="org_carrier",
        subject_principal_id="prn_driver",
    )

    allowed = evaluate_authorization(
        actor,
        AuthorizationRequest(action="read", purpose="safety_compliance", record_category="credential", **base),
        [membership],
        [consent],
    )
    wrong_purpose = evaluate_authorization(
        actor,
        AuthorizationRequest(action="read", purpose="marketing", record_category="credential", **base),
        [membership],
        [consent],
    )
    wrong_action = evaluate_authorization(
        actor,
        AuthorizationRequest(action="export", purpose="safety_compliance", record_category="credential", **base),
        [membership],
        [consent],
    )

    assert allowed.allowed is True
    assert allowed.consent_id == consent.id
    assert wrong_purpose.allowed is False
    assert wrong_action.allowed is False


def test_disabled_principal_is_always_denied():
    actor = Principal(id="prn_disabled", firebase_uid="disabled", status=PrincipalStatus.DISABLED)
    decision = evaluate_authorization(
        actor,
        AuthorizationRequest(
            action="read",
            resource_type="profile",
            resource_id=actor.id,
            subject_principal_id=actor.id,
        ),
        [],
        [],
    )
    assert decision.allowed is False
    assert decision.reason == "principal_not_active"


def test_delegated_access_is_scoped_expiring_revocable_and_audited():
    db = FakeDb()
    service = PlatformService(db)
    for uid, role in (("grantor", "driver"), ("recipient", "driver")):
        service.bootstrap_principal({"uid": uid, "role": role})
    grantor = principal_id_for_uid("grantor")
    recipient = principal_id_for_uid("recipient")
    grant = service.create_delegation(grantor, DelegatedAccessGrantCreate(
        recipient_principal_id=recipient,
        purpose="case_support",
        record_categories=["ticket"],
        actions=["read"],
        expires_at=utc_now() + timedelta(hours=1),
        related_resource_type="ticket",
        related_resource_id="ticket_1",
    ))
    decision = evaluate_authorization(
        service.get_principal(recipient),
        AuthorizationRequest(
            action="read", resource_type="ticket", resource_id="ticket_1",
            purpose="case_support", record_category="ticket",
            subject_principal_id=grantor,
        ),
        [], [], [grant],
    )
    assert decision.allowed is True
    assert decision.reason == "active_delegation"
    revoked = service.revoke_delegation(grantor, grant.id, "Support complete")
    denied = evaluate_authorization(
        service.get_principal(recipient),
        AuthorizationRequest(
            action="read", resource_type="ticket", resource_id="ticket_1",
            purpose="case_support", record_category="ticket",
            subject_principal_id=grantor,
        ),
        [], [], [revoked],
    )
    assert denied.allowed is False


def test_organization_names_are_normalized():
    body = OrganizationCreate(type=OrganizationType.CARRIER, legal_name="  Example   Carrier LLC  ")
    assert body.legal_name == "Example Carrier LLC"


def test_carrier_organization_bootstrap_is_idempotent_and_links_profile():
    db = FakeDb()
    service = PlatformService(db)
    claims = {"uid": "carrier_uid", "role": "carrier", "email": "admin@example.com"}
    principal, _ = service.bootstrap_principal(claims)
    db.collection("carriers").document("carrier_uid").set({
        "company_name": "Example Carrier LLC",
        "dot_number": "123456",
    }, merge=True)

    organization, membership, created = service.bootstrap_role_organization(claims)
    again_org, again_membership, again_created = service.bootstrap_role_organization(claims)

    assert created is True
    assert again_created is False
    assert organization.id == again_org.id
    assert membership.id == again_membership.id
    assert membership.principal_id == principal.id
    assert membership.role == "carrier_admin"
    assert organization.verification_status == "pending"
    assert organization.external_identifiers["dot_number"] == "123456"
    profile = db.collection("carriers").rows["carrier_uid"]
    assert profile["organization_id"] == organization.id
    assert profile["membership_id"] == membership.id
    assert len(db.collection("organizations").rows) == 1
    assert len(db.collection("organization_memberships").rows) == 1


def test_organization_bootstrap_requires_supported_role_and_allows_pending_profile():
    db = FakeDb()
    service = PlatformService(db)
    driver_claims = {"uid": "driver_uid", "role": "driver"}
    service.bootstrap_principal(driver_claims)

    with pytest.raises(ValueError):
        service.bootstrap_role_organization(driver_claims)

    attorney_claims = {"uid": "attorney_uid", "role": "attorney"}
    service.bootstrap_principal(attorney_claims)
    organization, membership, created = service.bootstrap_role_organization(attorney_claims)
    assert created is True
    assert organization.legal_name == "Pending attorney organization"
    assert organization.verification_status == "pending"
    assert membership.role == "firm_admin"


def test_driver_carrier_relationship_requires_membership_and_driver_acceptance():
    db = FakeDb()
    service = PlatformService(db)
    carrier_claims = {"uid": "carrier_uid", "role": "carrier"}
    driver_claims = {"uid": "driver_uid", "role": "driver"}
    carrier, _ = service.bootstrap_principal(carrier_claims)
    driver, _ = service.bootstrap_principal(driver_claims)
    db.collection("carriers").document("carrier_uid").set({"company_name": "Carrier LLC"}, merge=True)
    organization, _, _ = service.bootstrap_role_organization(carrier_claims)

    relationship, created = service.create_driver_relationship_invitation(
        carrier.id,
        organization.id,
        DriverCarrierRelationshipCreate(driver_principal_id=driver.id),
    )
    again, again_created = service.create_driver_relationship_invitation(
        carrier.id,
        organization.id,
        DriverCarrierRelationshipCreate(driver_principal_id=driver.id),
    )

    assert created is True
    assert again_created is False
    assert relationship.id == again.id
    assert relationship.status == RelationshipStatus.INVITED
    assert db.collection("consent_grants").rows == {}

    accepted = service.respond_to_driver_relationship(driver.id, relationship.id, True)
    assert accepted.status == RelationshipStatus.ACTIVE
    assert accepted.responded_at is not None
    assert db.collection("consent_grants").rows == {}


def test_relationship_cannot_be_accepted_by_another_driver_and_can_be_ended():
    db = FakeDb()
    service = PlatformService(db)
    carrier_claims = {"uid": "carrier_uid", "role": "carrier"}
    driver_claims = {"uid": "driver_uid", "role": "driver"}
    other_claims = {"uid": "other_uid", "role": "driver"}
    carrier, _ = service.bootstrap_principal(carrier_claims)
    driver, _ = service.bootstrap_principal(driver_claims)
    other, _ = service.bootstrap_principal(other_claims)
    db.collection("carriers").document("carrier_uid").set({"company_name": "Carrier LLC"}, merge=True)
    organization, _, _ = service.bootstrap_role_organization(carrier_claims)
    relationship, _ = service.create_driver_relationship_invitation(
        carrier.id,
        organization.id,
        DriverCarrierRelationshipCreate(driver_principal_id=driver.id),
    )

    with pytest.raises(PermissionError):
        service.respond_to_driver_relationship(other.id, relationship.id, True)

    service.respond_to_driver_relationship(driver.id, relationship.id, True)
    ended = service.end_driver_relationship(carrier.id, relationship.id, "employment ended")
    assert ended.status == RelationshipStatus.ENDED
    assert ended.response_reason == "employment ended"


def test_safety_consent_requires_active_relationship():
    db = FakeDb()
    service = PlatformService(db)
    body = ConsentGrantCreate(
        subject_principal_id="prn_driver",
        recipient_organization_id="org_carrier",
        purpose="safety_compliance",
        record_categories=["driver_profile"],
        disclosure_version="driver-carrier-safety-v1",
    )

    with pytest.raises(PermissionError):
        service.create_consent("prn_driver", body)
