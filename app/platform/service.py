"""WP-01 platform service with Firestore persistence and pure policy evaluation."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.platform.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    ConsentGrant,
    ConsentGrantCreate,
    ConsentStatus,
    DelegatedAccessGrant,
    DelegatedAccessGrantCreate,
    DelegationStatus,
    DriverCarrierRelationship,
    DriverCarrierRelationshipCreate,
    Membership,
    MembershipCreate,
    MembershipStatus,
    Organization,
    OrganizationCreate,
    Principal,
    PrincipalStatus,
    RelationshipStatus,
    utc_now,
)


def principal_id_for_uid(firebase_uid: str) -> str:
    """Return a stable, non-UID principal identifier for idempotent bootstrap."""
    digest = hashlib.sha256(firebase_uid.encode("utf-8")).hexdigest()[:32]
    return f"prn_{digest}"


def organization_id_for_profile(role: str, profile_id: str) -> str:
    digest = hashlib.sha256(f"{role}:{profile_id}".encode("utf-8")).hexdigest()[:32]
    return f"org_{digest}"


def membership_id_for_principal(organization_id: str, principal_id: str) -> str:
    digest = hashlib.sha256(f"{organization_id}:{principal_id}".encode("utf-8")).hexdigest()[:32]
    return f"mem_{digest}"


def relationship_id_for_parties(organization_id: str, driver_principal_id: str) -> str:
    digest = hashlib.sha256(f"{organization_id}:{driver_principal_id}".encode("utf-8")).hexdigest()[:32]
    return f"rel_{digest}"


def mask_email(value: Optional[str]) -> Optional[str]:
    if not value or "@" not in value:
        return None
    local, domain = value.split("@", 1)
    return f"{local[:1]}***@{domain}"


def mask_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"***-***-{digits[-4:]}" if len(digits) >= 4 else None


def _serialize(model):
    return model.model_dump(mode="json")


def _active_at(start: datetime, end: Optional[datetime], now: datetime) -> bool:
    start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    if start > now:
        return False
    if end is None:
        return True
    end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    return end > now


class PlatformService:
    def __init__(self, db):
        self.db = db

    def _audit(self, event_type: str, actor_id: str, entity_type: str, entity_id: str, payload=None) -> str:
        event_id = f"audit_{uuid.uuid4().hex}"
        self.db.collection("audit_events").document(event_id).set({
            "id": event_id,
            "event_type": event_type,
            "actor_id": actor_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload or {},
            "version": "1.0",
            "created_at": utc_now().isoformat(),
        })
        return event_id

    def bootstrap_principal(self, claims: dict) -> tuple[Principal, bool]:
        uid = claims.get("uid") or claims.get("sub")
        if not uid:
            raise ValueError("Verified token does not contain a user identifier.")
        principal_id = principal_id_for_uid(uid)
        ref = self.db.collection("principals").document(principal_id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            return Principal.model_validate(snapshot.to_dict()), False

        role = claims.get("role") if isinstance(claims.get("role"), str) else None
        role_refs = {role: uid} if role in {"driver", "attorney", "carrier"} else {}
        principal = Principal(
            id=principal_id,
            firebase_uid=uid,
            display_name=claims.get("name"),
            email_masked=mask_email(claims.get("email")),
            phone_masked=mask_phone(claims.get("phone_number")),
            role_profile_refs=role_refs,
        )
        ref.set(_serialize(principal))
        if role:
            profile_collection = {"driver": "drivers", "attorney": "attorneys", "carrier": "carriers"}.get(role)
            if profile_collection:
                self.db.collection(profile_collection).document(uid).set({
                    "principal_id": principal_id,
                    "migration_version": "tip-os-wp01-v1",
                }, merge=True)
        self._audit("identity.principal_bootstrapped", principal_id, "principal", principal_id)
        return principal, True

    def get_principal(self, principal_id: str) -> Optional[Principal]:
        snapshot = self.db.collection("principals").document(principal_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        return Principal.model_validate(snapshot.to_dict())

    def create_organization(self, actor_id: str, body: OrganizationCreate) -> Organization:
        organization = Organization(
            id=f"org_{uuid.uuid4().hex}",
            created_by=actor_id,
            **body.model_dump(),
        )
        self.db.collection("organizations").document(organization.id).set(_serialize(organization))
        self._audit("organization.created", actor_id, "organization", organization.id)
        return organization

    def get_organization(self, organization_id: str) -> Optional[Organization]:
        snapshot = self.db.collection("organizations").document(organization_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        return Organization.model_validate(snapshot.to_dict())

    def bootstrap_role_organization(self, claims: dict) -> tuple[Organization, Membership, bool]:
        uid = claims.get("uid") or claims.get("sub")
        role = claims.get("role")
        if not uid or role not in {"carrier", "attorney"}:
            raise ValueError("Carrier or attorney identity required.")
        principal_id = principal_id_for_uid(uid)
        if self.get_principal(principal_id) is None:
            raise LookupError("Bootstrap canonical identity first.")

        profile_collection = "carriers" if role == "carrier" else "attorneys"
        profile_ref = self.db.collection(profile_collection).document(uid)
        profile_snapshot = profile_ref.get()
        if not getattr(profile_snapshot, "exists", False):
            raise LookupError(f"{role.title()} profile not found.")
        profile = profile_snapshot.to_dict() or {}
        organization_id = organization_id_for_profile(role, uid)
        organization_ref = self.db.collection("organizations").document(organization_id)
        existing = organization_ref.get()
        created = not getattr(existing, "exists", False)

        if created:
            legal_name = (
                profile.get("company_name")
                if role == "carrier"
                else profile.get("firm_name") or profile.get("company_name")
            )
            if not legal_name:
                legal_name = profile.get("full_name") or claims.get("name") or f"Pending {role} organization"
            identifiers = {}
            if role == "carrier":
                if profile.get("dot_number"):
                    identifiers["dot_number"] = str(profile["dot_number"])
                if profile.get("mc_number"):
                    identifiers["mc_number"] = str(profile["mc_number"])
            organization = Organization(
                id=organization_id,
                type="carrier" if role == "carrier" else "law_firm",
                legal_name=legal_name,
                display_name=profile.get("company_name") or profile.get("firm_name"),
                external_identifiers=identifiers,
                created_by=principal_id,
            )
            organization_ref.set(_serialize(organization))
        else:
            organization = Organization.model_validate(existing.to_dict())

        membership_id = membership_id_for_principal(organization_id, principal_id)
        membership_ref = self.db.collection("organization_memberships").document(membership_id)
        membership_snapshot = membership_ref.get()
        if getattr(membership_snapshot, "exists", False):
            membership = Membership.model_validate(membership_snapshot.to_dict())
        else:
            membership = Membership(
                id=membership_id,
                organization_id=organization_id,
                principal_id=principal_id,
                role="carrier_admin" if role == "carrier" else "firm_admin",
                status=MembershipStatus.ACTIVE,
                effective_at=utc_now(),
                created_by=principal_id,
            )
            membership_ref.set(_serialize(membership))

        profile_ref.set({
            "principal_id": principal_id,
            "organization_id": organization_id,
            "membership_id": membership_id,
            "migration_version": "tip-os-wp01-v1",
        }, merge=True)
        if created:
            self._audit(
                "organization.bootstrapped",
                principal_id,
                "organization",
                organization_id,
                {"profile_type": role},
            )
        return organization, membership, created

    def create_membership(self, actor_id: str, organization_id: str, body: MembershipCreate) -> Membership:
        membership = Membership(
            id=f"mem_{uuid.uuid4().hex}",
            organization_id=organization_id,
            created_by=actor_id,
            **body.model_dump(),
        )
        self.db.collection("organization_memberships").document(membership.id).set(_serialize(membership))
        self._audit("membership.created", actor_id, "membership", membership.id, {"organization_id": organization_id})
        return membership

    def list_memberships(self, principal_id: str) -> list[Membership]:
        docs = self.db.collection("organization_memberships").where("principal_id", "==", principal_id).stream()
        return [Membership.model_validate(doc.to_dict()) for doc in docs]

    def create_consent(self, actor_id: str, body: ConsentGrantCreate) -> ConsentGrant:
        if actor_id != body.subject_principal_id:
            raise PermissionError("A user may only grant consent for their own records.")
        if body.purpose == "safety_compliance" and body.recipient_organization_id:
            relationship_id = relationship_id_for_parties(
                body.recipient_organization_id, body.subject_principal_id
            )
            relationship_snapshot = self.db.collection("driver_carrier_relationships").document(
                relationship_id
            ).get()
            relationship = (
                DriverCarrierRelationship.model_validate(relationship_snapshot.to_dict())
                if getattr(relationship_snapshot, "exists", False)
                else None
            )
            if relationship is None or relationship.status != RelationshipStatus.ACTIVE:
                raise PermissionError("An active carrier relationship is required for safety access.")
        for existing in self.list_consents(body.subject_principal_id):
            if (
                existing.status == ConsentStatus.ACTIVE
                and existing.recipient_principal_id == body.recipient_principal_id
                and existing.recipient_organization_id == body.recipient_organization_id
                and existing.purpose == body.purpose
                and existing.disclosure_version == body.disclosure_version
                and set(existing.record_categories) == set(body.record_categories)
                and set(existing.actions) == set(body.actions)
            ):
                return existing
        consent = ConsentGrant(
            id=f"cns_{uuid.uuid4().hex}",
            grantor_principal_id=actor_id,
            **body.model_dump(),
        )
        self.db.collection("consent_grants").document(consent.id).set(_serialize(consent))
        self._audit("consent.granted", actor_id, "consent", consent.id, {"purpose": consent.purpose})
        return consent

    def list_consents(self, subject_principal_id: str) -> list[ConsentGrant]:
        docs = self.db.collection("consent_grants").where("subject_principal_id", "==", subject_principal_id).stream()
        return [ConsentGrant.model_validate(doc.to_dict()) for doc in docs]

    def revoke_consent(self, actor_id: str, consent_id: str, reason: str) -> ConsentGrant:
        ref = self.db.collection("consent_grants").document(consent_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Consent grant not found.")
        consent = ConsentGrant.model_validate(snapshot.to_dict())
        if consent.grantor_principal_id != actor_id:
            raise PermissionError("Only the grantor may revoke this consent.")
        if consent.status == ConsentStatus.REVOKED:
            return consent
        consent.status = ConsentStatus.REVOKED
        consent.revoked_at = utc_now()
        consent.revocation_reason = reason
        consent.updated_at = utc_now()
        ref.set(_serialize(consent))
        self._audit("consent.revoked", actor_id, "consent", consent.id, {"reason": reason})
        return consent

    def create_delegation(
        self, actor_id: str, body: DelegatedAccessGrantCreate
    ) -> DelegatedAccessGrant:
        if self.get_principal(actor_id) is None:
            raise LookupError("Grantor principal not found.")
        if self.get_principal(body.recipient_principal_id) is None:
            raise LookupError("Recipient principal not found.")
        if actor_id == body.recipient_principal_id:
            raise PermissionError("Delegation to self is not allowed.")
        grant = DelegatedAccessGrant(
            id=f"dag_{uuid.uuid4().hex}",
            grantor_principal_id=actor_id,
            subject_principal_id=actor_id,
            **body.model_dump(),
        )
        self.db.collection("delegated_access_grants").document(grant.id).set(_serialize(grant))
        self._audit(
            "delegation.granted", actor_id, "delegated_access_grant", grant.id,
            {"recipient_principal_id": grant.recipient_principal_id, "purpose": grant.purpose},
        )
        return grant

    def list_delegations(self, subject_principal_id: str) -> list[DelegatedAccessGrant]:
        docs = self.db.collection("delegated_access_grants").where(
            "subject_principal_id", "==", subject_principal_id
        ).stream()
        return [DelegatedAccessGrant.model_validate(doc.to_dict()) for doc in docs]

    def revoke_delegation(
        self, actor_id: str, delegation_id: str, reason: str
    ) -> DelegatedAccessGrant:
        ref = self.db.collection("delegated_access_grants").document(delegation_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Delegated access grant not found.")
        grant = DelegatedAccessGrant.model_validate(snapshot.to_dict())
        if grant.grantor_principal_id != actor_id:
            raise PermissionError("Only the grantor may revoke delegated access.")
        if grant.status == DelegationStatus.REVOKED:
            return grant
        grant.status = DelegationStatus.REVOKED
        grant.revoked_at = utc_now()
        grant.revocation_reason = reason
        grant.updated_at = utc_now()
        ref.set(_serialize(grant))
        self._audit("delegation.revoked", actor_id, "delegated_access_grant", grant.id, {"reason": reason})
        return grant

    def create_driver_relationship_invitation(
        self,
        actor_id: str,
        organization_id: str,
        body: DriverCarrierRelationshipCreate,
    ) -> tuple[DriverCarrierRelationship, bool]:
        if self.get_principal(body.driver_principal_id) is None:
            raise LookupError("Driver principal not found.")
        organization = self.get_organization(organization_id)
        if organization is None or organization.type.value != "carrier":
            raise LookupError("Carrier organization not found.")
        memberships = self.list_memberships(actor_id)
        if not any(
            item.organization_id == organization_id
            and item.status == MembershipStatus.ACTIVE
            and item.role in {"carrier_admin", "safety_manager", "fleet_manager"}
            for item in memberships
        ):
            raise PermissionError("Active carrier membership required.")

        relationship_id = relationship_id_for_parties(organization_id, body.driver_principal_id)
        ref = self.db.collection("driver_carrier_relationships").document(relationship_id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            relationship = DriverCarrierRelationship.model_validate(snapshot.to_dict())
            if relationship.status in {RelationshipStatus.INVITED, RelationshipStatus.ACTIVE}:
                return relationship, False

        relationship = DriverCarrierRelationship(
            id=relationship_id,
            driver_principal_id=body.driver_principal_id,
            carrier_organization_id=organization_id,
            invited_by_principal_id=actor_id,
            **body.model_dump(exclude={"driver_principal_id"}),
        )
        ref.set(_serialize(relationship))
        self._audit(
            "relationship.invited",
            actor_id,
            "driver_carrier_relationship",
            relationship.id,
            {"organization_id": organization_id},
        )
        return relationship, True

    def list_driver_relationships(self, driver_principal_id: str) -> list[DriverCarrierRelationship]:
        docs = self.db.collection("driver_carrier_relationships").where(
            "driver_principal_id", "==", driver_principal_id
        ).stream()
        return [DriverCarrierRelationship.model_validate(doc.to_dict()) for doc in docs]

    def list_organization_relationships(self, organization_id: str) -> list[DriverCarrierRelationship]:
        docs = self.db.collection("driver_carrier_relationships").where(
            "carrier_organization_id", "==", organization_id
        ).stream()
        return [DriverCarrierRelationship.model_validate(doc.to_dict()) for doc in docs]

    def respond_to_driver_relationship(
        self,
        actor_id: str,
        relationship_id: str,
        accept: bool,
        reason: Optional[str] = None,
    ) -> DriverCarrierRelationship:
        ref = self.db.collection("driver_carrier_relationships").document(relationship_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Relationship invitation not found.")
        relationship = DriverCarrierRelationship.model_validate(snapshot.to_dict())
        if relationship.driver_principal_id != actor_id:
            raise PermissionError("Only the invited driver may respond.")
        if relationship.status != RelationshipStatus.INVITED:
            return relationship
        relationship.status = RelationshipStatus.ACTIVE if accept else RelationshipStatus.DECLINED
        relationship.responded_at = utc_now()
        relationship.response_reason = reason
        relationship.updated_at = utc_now()
        ref.set(_serialize(relationship))
        self._audit(
            "relationship.accepted" if accept else "relationship.declined",
            actor_id,
            "driver_carrier_relationship",
            relationship.id,
        )
        return relationship

    def end_driver_relationship(
        self,
        actor_id: str,
        relationship_id: str,
        reason: str,
    ) -> DriverCarrierRelationship:
        ref = self.db.collection("driver_carrier_relationships").document(relationship_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Relationship not found.")
        relationship = DriverCarrierRelationship.model_validate(snapshot.to_dict())
        actor_is_driver = relationship.driver_principal_id == actor_id
        actor_is_carrier_admin = any(
            item.organization_id == relationship.carrier_organization_id
            and item.status == MembershipStatus.ACTIVE
            and item.role in {"carrier_admin", "safety_manager"}
            for item in self.list_memberships(actor_id)
        )
        if not actor_is_driver and not actor_is_carrier_admin:
            raise PermissionError("Relationship access denied.")
        if relationship.status == RelationshipStatus.ENDED:
            return relationship
        relationship.status = RelationshipStatus.ENDED
        relationship.ended_at = utc_now()
        relationship.response_reason = reason
        relationship.updated_at = utc_now()
        ref.set(_serialize(relationship))
        self._audit("relationship.ended", actor_id, "driver_carrier_relationship", relationship.id)
        return relationship


def evaluate_authorization(
    actor: Principal,
    request: AuthorizationRequest,
    memberships: Iterable[Membership],
    consents: Iterable[ConsentGrant],
    delegations: Iterable[DelegatedAccessGrant] = (),
    now: Optional[datetime] = None,
) -> AuthorizationDecision:
    """Pure, deny-by-default WP-01 policy evaluation."""
    now = now or utc_now()
    if actor.status != PrincipalStatus.ACTIVE:
        return AuthorizationDecision(allowed=False, reason="principal_not_active")

    if request.subject_principal_id == actor.id:
        return AuthorizationDecision(allowed=True, reason="self_access")

    active_membership = None
    for membership in memberships:
        if membership.principal_id != actor.id or membership.status != MembershipStatus.ACTIVE:
            continue
        if not _active_at(membership.effective_at, membership.expires_at, now):
            continue
        if request.tenant_id and membership.organization_id != request.tenant_id:
            continue
        if request.terminal_id and membership.terminal_ids and request.terminal_id not in membership.terminal_ids:
            continue
        active_membership = membership
        break

    if request.tenant_id and active_membership is None:
        return AuthorizationDecision(allowed=False, reason="active_tenant_membership_required")

    if request.subject_principal_id:
        for grant in delegations:
            if (
                grant.status == DelegationStatus.ACTIVE
                and grant.subject_principal_id == request.subject_principal_id
                and grant.recipient_principal_id == actor.id
                and _active_at(grant.effective_at, grant.expires_at, now)
                and (not request.purpose or grant.purpose == request.purpose)
                and request.action in grant.actions
                and (not request.record_category or request.record_category in grant.record_categories)
                and (
                    not grant.related_resource_type
                    or (
                        grant.related_resource_type == request.resource_type
                        and grant.related_resource_id == request.resource_id
                    )
                )
            ):
                return AuthorizationDecision(
                    allowed=True,
                    reason="active_delegation",
                    membership_id=active_membership.id if active_membership else None,
                    delegation_id=grant.id,
                )
        for consent in consents:
            if consent.status != ConsentStatus.ACTIVE:
                continue
            if consent.subject_principal_id != request.subject_principal_id:
                continue
            if consent.recipient_principal_id != actor.id and consent.recipient_organization_id != request.tenant_id:
                continue
            if consent.expires_at and not _active_at(consent.effective_at, consent.expires_at, now):
                continue
            if request.purpose and consent.purpose != request.purpose:
                continue
            if request.action not in consent.actions:
                continue
            if request.record_category and request.record_category not in consent.record_categories:
                continue
            return AuthorizationDecision(
                allowed=True,
                reason="active_consent",
                membership_id=active_membership.id if active_membership else None,
                consent_id=consent.id,
            )
        return AuthorizationDecision(allowed=False, reason="active_matching_consent_required")

    if active_membership:
        return AuthorizationDecision(allowed=True, reason="active_membership", membership_id=active_membership.id)
    return AuthorizationDecision(allowed=False, reason="no_policy_grant")
